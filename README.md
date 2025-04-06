# Email Backup System

A fast and efficient email backup system that allows users to backup their emails locally with a web interface.

## New Features & Updates (2024)

- ⚡ **Performance Improvements**
  - Batch processing of emails
  - Asynchronous file operations
  - In-memory caching for recent backups
  - Optimized IMAP connections
  
- 🔒 **Security Enhancements**
  - Updated SSL/TLS handling
  - Improved session management
  - Enhanced password security
  
- 💻 **UI Improvements**
  - Real-time backup progress
  - Better error handling
  - Responsive design updates

## Requirements

- Python 3.8+
- Redis (optional, for caching)
- Modern web browser

## Installation

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your SMTP settings in the environment file
4. Run the application:
   ```bash
   python backup_email.py
   ```

## Configuration

Update the following environment variables:
- `SMTP_SERVER`: Your SMTP server address
- `SMTP_PORT`: SMTP port (default: 465)
- `IMAP_SERVER`: IMAP server address
- `IMAP_PORT`: IMAP port (default: 993)

## Features

- 📧 Email backup with folder structure preservation
- 🔍 Search functionality
- 📁 Folder organization
- 🔒 Secure authentication
- 💨 Fast batch processing
- 📊 Progress tracking

## Performance Tips

1. Use batch processing for large mailboxes
2. Enable Redis caching for better performance
3. Regular cleanup of old backups
4. Use the recommended batch size settings

## Security

- All connections use SSL/TLS
- Passwords are never stored
- Session management with secure tokens
- Rate limiting on login attempts

## Contributing

Feel free to submit issues and enhancement requests!

## License

MIT License

## Author

Created by PG Mohd Azhan Fikri