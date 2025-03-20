from flask import Flask, render_template, request, session, redirect, url_for, flash
from imapclient import IMAPClient
import os
import email
import re
import time
from tqdm import tqdm
from email.header import decode_header
from functools import wraps
import imaplib
import email.utils
import ssl
import unicodedata

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Secure secret key for sessions

BACKUP_ROOT = "backup"
BATCH_SIZE = 50
SMTP_SERVER = "smtp11.mschosting.com"
SMTP_PORT = 465  # SSL port
IMAP_SERVER = "smtp11.mschosting.com"  # Updated IMAP server
IMAP_PORT = 993  # Standard IMAP SSL port

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def get_username_from_email(email_address):
    return email_address.split('@')[0]

def sanitize_filename(subject):
    # Decode email subject
    decoded_parts = decode_header(subject)
    subject = "".join(
        part.decode(encoding or "utf-8", errors="ignore") if isinstance(part, bytes) else part
        for part, encoding in decoded_parts
    )
    
    # Normalize Unicode characters
    subject = unicodedata.normalize('NFKD', subject).encode('ASCII', 'ignore').decode('ASCII')
    
    # Remove invalid filename characters and whitespace
    subject = re.sub(r'[\\/*?:"<>|]', "", subject.strip())
    subject = re.sub(r'\s+', "_", subject)
    
    # Ensure the filename isn't too long
    return subject[:50] if subject else "no_subject"

def sanitize_folder_name(folder):
    # Remove any special characters and normalize Unicode
    folder = unicodedata.normalize('NFKD', folder).encode('ASCII', 'ignore').decode('ASCII')
    folder = re.sub(r'[\\/*?:"<>|]', "", folder.strip())
    folder = re.sub(r'\s+', "_", folder)
    return folder

def backup_emails(email_account, email_password, user_folder):
    results = []
    
    try:
        # Create SSL context with certificate verification
        ssl_context = ssl.create_default_context()
        
        # Connect to IMAP server with SSL context
        with IMAPClient(IMAP_SERVER, port=IMAP_PORT, ssl_context=ssl_context) as client:
            client.login(email_account, email_password)
            
            # List all folders
            folders = client.list_folders()
            
            for flags, delimiter, folder_name in folders:
                try:
                    # Sanitize folder name for filesystem
                    safe_folder_name = sanitize_folder_name(folder_name)
                    folder_path = os.path.join(user_folder, safe_folder_name)
                    os.makedirs(folder_path, exist_ok=True)
                    
                    # Select the folder
                    client.select_folder(folder_name)
                    messages = client.search(['ALL'])
                    
                    if messages:
                        for msg_id, message_data in client.fetch(messages, ['RFC822']).items():
                            try:
                                email_body = message_data[b'RFC822']
                                msg = email.message_from_bytes(email_body)
                                
                                # Get email details
                                subject = msg.get('subject', 'No Subject')
                                date_str = msg.get('date', '')
                                
                                # Generate timestamp
                                if date_str:
                                    try:
                                        date_tuple = email.utils.parsedate_tz(date_str)
                                        date = time.strftime('%Y%m%d_%H%M%S', date_tuple[:9])
                                    except:
                                        date = time.strftime('%Y%m%d_%H%M%S')
                                else:
                                    date = time.strftime('%Y%m%d_%H%M%S')
                                
                                # Create safe filename
                                safe_subject = sanitize_filename(subject)
                                filename = f"{date}_{safe_subject}.eml"
                                file_path = os.path.join(folder_path, filename)
                                
                                # Save email
                                with open(file_path, 'wb') as f:
                                    f.write(email_body)
                                
                            except Exception as e:
                                results.append(f"⚠️ Error saving email in {folder_name}: {str(e)}")
                                continue
                        
                        results.append(f"✅ Backed up {len(messages)} emails from {folder_name}")
                    else:
                        results.append(f"ℹ️ No emails found in {folder_name}")
                        
                except Exception as e:
                    results.append(f"⚠️ Error processing folder {folder_name}: {str(e)}")
                    continue
            
        return results
    except Exception as e:
        results.append(f"❌ Backup failed: {str(e)}")
        return results

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_account = request.form['email']
        email_password = request.form['password']
        
        try:
            # Create SSL context
            ssl_context = ssl.create_default_context()
            
            # First verify SMTP credentials
            import smtplib
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl_context) as server:
                server.login(email_account, email_password)
                
                # If SMTP login successful, store credentials
                session['logged_in'] = True
                session['email_account'] = email_account
                session['email_password'] = email_password
                
                # Create user backup folder
                username = get_username_from_email(email_account)
                user_folder = os.path.join(BACKUP_ROOT, username)
                os.makedirs(user_folder, exist_ok=True)
                session['user_folder'] = user_folder
                
                flash('Successfully logged in! Starting email backup...', 'success')
                return redirect(url_for('backup'))
        except Exception as e:
            flash(f'Login failed: {str(e)}', 'error')
            
    return render_template('login.html', smtp_server=SMTP_SERVER)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/backup')
@login_required
def backup():
    try:
        username = get_username_from_email(session['email_account'])
        user_folder = os.path.join(BACKUP_ROOT, username)
        
        # Perform email backup
        backup_results = backup_emails(
            session['email_account'],
            session['email_password'],
            user_folder
        )
        
        return render_template('backup_results.html', 
                             results=backup_results,
                             user_folder=user_folder)
    except Exception as e:
        flash(f'Backup failed: {str(e)}', 'error')
        return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    username = get_username_from_email(session['email_account'])
    user_folder = os.path.join(BACKUP_ROOT, username)
    
    if not os.path.exists(user_folder):
        return "No email backups found.", 404
    
    folders = [f for f in os.listdir(user_folder) if os.path.isdir(os.path.join(user_folder, f))]
    return render_template("index.html", folders=folders)

@app.route('/folder/<folder>')
@login_required
def folder_view(folder):
    username = get_username_from_email(session['email_account'])
    folder_path = os.path.join(BACKUP_ROOT, username, folder)
    
    if not os.path.exists(folder_path):
        return "Folder not found", 404
    
    emails = [f for f in os.listdir(folder_path) if f.endswith(".eml")]
    return render_template("folder.html", folder=folder, emails=emails)

@app.route('/email/<folder>/<email_file>')
@login_required
def email_view(folder, email_file):
    username = get_username_from_email(session['email_account'])
    email_path = os.path.join(BACKUP_ROOT, username, folder, email_file)
    
    if not os.path.exists(email_path):
        return "Email not found", 404
    
    with open(email_path, "rb") as f:
        msg = email.message_from_binary_file(f)
    
    subject = msg["subject"] or "(No Subject)"
    sender = msg["from"] or "Unknown Sender"
    recipient = msg["to"] or "Unknown Recipient"
    date = msg["date"] or "Unknown Date"
    
    body = ""
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
            break
        elif part.get_content_type() == "text/plain":
            body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
    
    return render_template("email.html", 
                         subject=subject, 
                         sender=sender, 
                         recipient=recipient, 
                         date=date, 
                         body=body)

if __name__ == "__main__":
    app.run(debug=True)