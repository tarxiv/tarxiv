import imaplib
import email
from email.header import decode_header

def clean_text(text):
    # Clean text for safe printing
    return "".join(c if c.isprintable() else "?" for c in text)

# imap_host = 'mailu.local.test'
# imap_user = 'me@example.net'
# imap_password = 'password'
imap_host = 'imap.gmail.com'
imap_user = 'jacks.super.secret.santa@gmail.com'
imap_password = 'vgcyurlbnhyjrtum'

# t@rxiv_EMAIL
# tarxiv.service@gmail.com

# Connect to the IMAP server
imap = imaplib.IMAP4_SSL(imap_host)

# Log in
imap.login(imap_user, imap_password)

# Select inbox
imap.select('INBOX')

# Search for all emails in the inbox
status, messages = imap.search(None, '(UNSEEN)')  # Fetch only unread emails

# Fetch emails by their IDs
for num in messages[0].split():
    status, data = imap.fetch(num, '(RFC822)')
    msg = email.message_from_bytes(data[0][1])

    # Decode email subject
    subject, encoding = decode_header(msg['Subject'])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding or 'utf-8')

    print(f'Subject: {subject}')

    body = None

    if msg.is_multipart():
        # Iterate over email parts
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # Skip attachments
            if "attachment" in content_disposition:
                continue

            # Fetch text/plain first; fallback to text/html
            if content_type == "text/plain":
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or 'utf-8'
                if payload:
                    body = payload.decode(charset, errors='replace')
                    break  # Prefer text/plain
        else:
            # If no text/plain part found, fallback to text/html
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/html" and "attachment" not in content_disposition:
                    payload = part.get_payload(decode=True)
                    charset = part.get_content_charset() or 'utf-8'
                    if payload:
                        body = payload.decode(charset, errors='replace')
                        break
    else:
        # Non-multipart message
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or 'utf-8'
        if payload:
            body = payload.decode(charset, errors='replace')

    if body:
        print(f'Body:\n{clean_text(body)}\n{"-" * 50}')
    else:
        print("No readable body found.\n" + "-" * 50)

    # Mark the message as read
    imap.store(num, '+FLAGS', '\\Seen')

# Logout
imap.logout()
