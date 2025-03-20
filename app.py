from flask import Flask, render_template, request
import os
import email
from email import policy

app = Flask(__name__)

EMAIL_BACKUP_DIR = "Backup"

@app.route("/")
def index():
    if not os.path.exists(EMAIL_BACKUP_DIR):
        return "No email backups found.", 404
    
    folders = [f for f in os.listdir(EMAIL_BACKUP_DIR) if os.path.isdir(os.path.join(EMAIL_BACKUP_DIR, f))]
    return render_template("index.html", folders=folders)

@app.route("/folder/<folder>")
def folder_view(folder):
    folder_path = os.path.join(EMAIL_BACKUP_DIR, folder)
    if not os.path.exists(folder_path):
        return "Folder not found", 404
    
    emails = [f for f in os.listdir(folder_path) if f.endswith(".eml")]
    return render_template("folder.html", folder=folder, emails=emails)

@app.route("/email/<folder>/<email_file>")
def email_view(folder, email_file):
    email_path = os.path.join(EMAIL_BACKUP_DIR, folder, email_file)
    if not os.path.exists(email_path):
        return "Email not found", 404
    
    with open(email_path, "rb") as f:
        msg = email.message_from_binary_file(f, policy=policy.default)
    

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
    
    return render_template("email.html", subject=subject, sender=sender, recipient=recipient, date=date, body=body)

if __name__ == "__main__":
    app.run(debug=True)
