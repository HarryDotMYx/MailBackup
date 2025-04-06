from flask import Flask, render_template, request, session, redirect, url_for, flash, jsonify, Response
from imapclient import IMAPClient
import os
import email
import re
import time
import asyncio
import aiofiles
from tqdm import tqdm
from email.header import decode_header
from functools import wraps
import imaplib
import email.utils
import ssl
import unicodedata
from cachetools import TTLCache, LRUCache
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('email_backup.log'),
        logging.StreamHandler()
    ]
)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 24 hours

# Configuration
BACKUP_ROOT = "backup"
BATCH_SIZE = 150  # Increased for better performance
SMTP_SERVER = "SMTP_Server"
SMTP_PORT = 465
IMAP_SERVER = "SMTP_Server"
IMAP_PORT = 993
MAX_RETRIES = 3
BACKUP_RETENTION_DAYS = 30

# Enhanced caching system
email_cache = TTLCache(maxsize=2000, ttl=7200)  # 2 hours
folder_cache = TTLCache(maxsize=200, ttl=600)    # 10 minutes
metadata_cache = LRUCache(maxsize=1000)          # For email metadata

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
    if isinstance(subject, bytes):
        try:
            subject = subject.decode('utf-8')
        except UnicodeDecodeError:
            subject = subject.decode('latin-1')
    
    decoded_parts = decode_header(str(subject))
    subject = "".join(
        part.decode(encoding or "utf-8", errors="ignore") if isinstance(part, bytes) else str(part)
        for part, encoding in decoded_parts
    )
    
    subject = unicodedata.normalize('NFKD', subject).encode('ASCII', 'ignore').decode('ASCII')
    subject = re.sub(r'[\\/*?:"<>|]', "", subject.strip())
    subject = re.sub(r'\s+', "_", subject)
    
    return subject[:50] if subject else "no_subject"

def sanitize_folder_name(folder):
    folder = unicodedata.normalize('NFKD', str(folder)).encode('ASCII', 'ignore').decode('ASCII')
    folder = re.sub(r'[\\/*?:"<>|]', "", folder.strip())
    folder = re.sub(r'\s+', "_", folder)
    return folder

async def save_email_async(email_path, email_body, metadata=None):
    try:
        async with aiofiles.open(email_path, 'wb') as f:
            await f.write(email_body)
        
        if metadata:
            metadata_path = f"{email_path}.meta"
            async with aiofiles.open(metadata_path, 'w') as f:
                await f.write(json.dumps(metadata))
        
        return True
    except Exception as e:
        logging.error(f"Error saving email: {str(e)}")
        return False

async def process_email_batch(client, messages, folder_path, progress_callback=None):
    tasks = []
    total = len(messages)
    completed = 0

    for msg_id, message_data in messages.items():
        try:
            email_body = message_data[b'RFC822']
            msg = email.message_from_bytes(email_body)
            
            subject = msg.get('subject', 'No Subject')
            date_str = msg.get('date', '')
            
            try:
                date_tuple = email.utils.parsedate_tz(date_str)
                date = time.strftime('%Y%m%d_%H%M%S', date_tuple[:9])
            except:
                date = time.strftime('%Y%m%d_%H%M%S')
            
            safe_subject = sanitize_filename(subject)
            filename = f"{date}_{safe_subject}.eml"
            file_path = os.path.join(folder_path, filename)
            
            if file_path not in email_cache:
                metadata = {
                    'subject': subject,
                    'date': date_str,
                    'from': msg.get('from', ''),
                    'to': msg.get('to', ''),
                    'size': len(email_body),
                    'backup_date': datetime.now().isoformat()
                }
                
                task = save_email_async(file_path, email_body, metadata)
                tasks.append(task)
                email_cache[file_path] = True
            
            completed += 1
            if progress_callback:
                progress_callback(completed, total)
                
        except Exception as e:
            logging.error(f"Error processing email: {str(e)}")
            continue
    
    results = await asyncio.gather(*tasks)
    return results.count(True)

def backup_emails(email_account, email_password, user_folder):
    results = []
    
    try:
        ssl_context = ssl.create_default_context()
        
        with IMAPClient(IMAP_SERVER, port=IMAP_PORT, ssl_context=ssl_context) as client:
            client.login(email_account, email_password)
            
            folders = client.list_folders()
            total_folders = len(folders)
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                for index, (flags, delimiter, folder_name) in enumerate(folders, 1):
                    try:
                        safe_folder_name = sanitize_folder_name(folder_name)
                        folder_path = os.path.join(user_folder, safe_folder_name)
                        os.makedirs(folder_path, exist_ok=True)
                        
                        if folder_path in folder_cache:
                            results.append(f"📁 Skipped {folder_name} (cached)")
                            continue
                        
                        client.select_folder(folder_name)
                        messages = client.search(['ALL'])
                        
                        if messages:
                            total_processed = 0
                            for i in range(0, len(messages), BATCH_SIZE):
                                batch = messages[i:i + BATCH_SIZE]
                                message_batch = client.fetch(batch, ['RFC822'])
                                
                                def progress_callback(completed, total):
                                    nonlocal total_processed
                                    total_processed = completed
                                
                                processed = asyncio.run(
                                    process_email_batch(
                                        client, 
                                        message_batch, 
                                        folder_path,
                                        progress_callback
                                    )
                                )
                            
                            results.append(f"✅ Backed up {total_processed} emails from {folder_name}")
                            folder_cache[folder_path] = True
                        else:
                            results.append(f"ℹ️ No emails in {folder_name}")
                            
                    except Exception as e:
                        results.append(f"⚠️ Error in {folder_name}: {str(e)}")
                        continue
            
        return results
    except Exception as e:
        logging.error(f"Backup failed: {str(e)}")
        results.append(f"❌ Backup failed: {str(e)}")
        return results

@app.route('/api/backup-progress')
@login_required
def backup_progress():
    username = get_username_from_email(session['email_account'])
    user_folder = os.path.join(BACKUP_ROOT, username)
    
    total_emails = 0
    processed_emails = 0
    
    for folder in os.listdir(user_folder):
        folder_path = os.path.join(user_folder, folder)
        if os.path.isdir(folder_path):
            emails = [f for f in os.listdir(folder_path) if f.endswith('.eml')]
            total_emails += len(emails)
            processed_emails += len([e for e in emails if os.path.join(folder_path, e) in email_cache])
    
    return jsonify({
        'total': total_emails,
        'processed': processed_emails,
        'percentage': (processed_emails / total_emails * 100) if total_emails > 0 else 0
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email_account = request.form['email']
        email_password = request.form['password']
        
        try:
            ssl_context = ssl.create_default_context()
            
            import smtplib
            with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=ssl_context) as server:
                server.login(email_account, email_password)
                
                session.permanent = True
                session['logged_in'] = True
                session['email_account'] = email_account
                session['email_password'] = email_password
                
                username = get_username_from_email(email_account)
                user_folder = os.path.join(BACKUP_ROOT, username)
                os.makedirs(user_folder, exist_ok=True)
                session['user_folder'] = user_folder
                
                flash('Successfully logged in! Starting email backup...', 'success')
                return redirect(url_for('backup'))
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
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
        
        backup_results = backup_emails(
            session['email_account'],
            session['email_password'],
            user_folder
        )
        
        return render_template('backup_results.html', 
                             results=backup_results,
                             user_folder=user_folder)
    except Exception as e:
        logging.error(f"Backup failed: {str(e)}")
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
    
    # Try to get from cache first
    if email_path in metadata_cache:
        metadata = metadata_cache[email_path]
        return render_template("email.html", **metadata)
    
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
    
    metadata = {
        'subject': subject,
        'sender': sender,
        'recipient': recipient,
        'date': date,
        'body': body
    }
    metadata_cache[email_path] = metadata
    
    return render_template("email.html", **metadata)

if __name__ == "__main__":
    app.run(debug=True)