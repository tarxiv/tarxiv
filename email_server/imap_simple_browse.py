import imaplib
import email

M = imaplib.IMAP4_SSL('mailu.local.test')
M.login('me@example.net', 'password')
M.select('INBOX')

# Full-text search: bodies and headers
status, data = M.search(None, '(TEXT "invoice")')
if status == 'OK':
    for num in data[0].split():
        status2, msg_data = M.fetch(num, '(RFC822)')
        msg = email.message_from_bytes(msg_data[0][1])
        print(msg['Subject'], msg.get_payload(decode=True)[:200])
M.logout()
