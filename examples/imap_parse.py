# First connect to Gmail client and read messages
from tarxiv.alerts import IMAP, Gmail

txv_imap = IMAP("imap", reporting_mode=1, debug=True)

# Fetch emails from the inbox
# Start the monitoring tread and poll a message
try:
    txv_imap.monitor_notices()
    message, alerts = txv_imap.poll(timeout=1)
finally:
    # Stop monitoring for the rest of the test
    txv_imap.stop_monitoring()

if message is None or alerts is None:
    print("No new messages or alerts found.")
    exit(0)
else:
    print(f"Message: {message}")
    print(f"Alerts: {alerts}")
