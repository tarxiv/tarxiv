MAIL_DIR="./mailu/mail/me@example.net/new/"

cat > "${MAIL_DIR}/$(date +%s).test.mail" <<'EOF'
From: test-sender@example.org
To: me@example.net
Subject: Manual Test Email 1

This is a test email placed directly into your inbox.
If you can see this, the IMAP server (Dovecot) is working correctly.
EOF