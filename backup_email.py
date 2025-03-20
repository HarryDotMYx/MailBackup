from imapclient import IMAPClient
import os
import email
import re
import time
from tqdm import tqdm
from email.header import decode_header


IMAP_SERVER = os.getenv("IMAP_SERVER", "")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
FOLDER_SAVE = "email_backup"
BATCH_SIZE = 50 


def sanitize_filename(subject):
    decoded_parts = decode_header(subject)
    subject = "".join(
        part.decode(encoding or "utf-8", errors="ignore") if isinstance(part, bytes) else part
        for part, encoding in decoded_parts
    )
    subject = subject.replace("\r", "").replace("\n", "").replace("=", "")
    subject = re.sub(r'[\\/*?:"<>|]', "", subject.strip().replace(" ", "_"))
    return subject[:100] if subject else "no_subject"


os.makedirs(FOLDER_SAVE, exist_ok=True)

try:
    print("🔗 Connecting to IMAP server...")
    with IMAPClient(IMAP_SERVER, timeout=15, ssl=True) as client:  
        client.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        
        
        FOLDER_LIST = [folder[-1] for folder in client.list_folders()]

        for folder_name in FOLDER_LIST:
            print(f"\n📂 Scanning folder: {folder_name}...")
            client.select_folder(folder_name, readonly=True)
            
            messages = client.search(['ALL'])
            
            if not messages:
                print(f"⚠️ No emails found in {folder_name}. Skipping...")
                continue
            
            folder_path = os.path.join(FOLDER_SAVE, folder_name.replace(" ", "_").lower())
            os.makedirs(folder_path, exist_ok=True)
            
          
            for i in range(0, len(messages), BATCH_SIZE):
                batch = messages[i : i + BATCH_SIZE]
                
                for msgid, data in tqdm(client.fetch(batch, ['RFC822']).items(), desc=f"Backing up {folder_name}", unit="email"):
                    raw_email = data[b'RFC822']
                    email_message = email.message_from_bytes(raw_email)
                    
                    subject = email_message["Subject"] or f"no_subject_{msgid}"
                    subject = sanitize_filename(subject)
                    
                    filename = os.path.join(folder_path, f"{subject}.eml")
                    
                    with open(filename, "wb") as f:
                        f.write(raw_email)
                    
                    time.sleep(0.02)  

        print("\n🎉 Semua email telah di-backup dengan berjaya!")

except Exception as e:
    print(f"❌ Error: {e}")
