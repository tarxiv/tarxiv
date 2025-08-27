# Listen for new TNS Alerts
from .utils import TarxivModule
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from queue import Queue, Empty
from bs4 import BeautifulSoup
import threading
import signal
import base64
import time
import os
import imaplib
import email
import re

class Gmail(TarxivModule):
    """Module for interfacing with gmail and parsing TNS alerts."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(script_name=script_name,
                         module="gmail",
                         reporting_mode=reporting_mode,
                         debug=debug)

        # Logging
        status = {"status": "connecting to google mail api"}
        self.logger.info(status, extra=status)
        # Get gmail token
        self.creds = None
        # Absolute paths
        token = os.path.join(self.config_dir, self.config["gmail"]["token_name"])
        secrets = os.path.join(self.config_dir, self.config["gmail"]["secrets_file"])
        # The file token.json stores the user's access and refresh tokens
        if os.path.exists(token):
            self.creds = Credentials.from_authorized_user_file(
                token, self.config["gmail"]["scopes"]
            )
        # If there are no (valid) credentials available, let the user log in.
        if not self.creds or not self.creds.valid:
            flow = InstalledAppFlow.from_client_secrets_file(
                secrets, self.config["gmail"]["scopes"]
            )
            self.creds = flow.run_local_server(port=0)
        else:
            self.creds.refresh(Request())
        # Write new token
        with open(token, "w") as f:
            f.write(self.creds.to_json())
        # Connect to service
        self.service = build("gmail", "v1", credentials=self.creds)
        # Connect to email
        status = {"status": "connection sucess"}
        self.logger.info(status, extra=status)

        # Create thread value
        self.t = None
        # Create internal queue
        self.q = Queue()
        # Create stop flag for monitoring
        self.stop_event = threading.Event()
        # Signals
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def poll(self, timeout=1):
        """Once we have began monitoring notices, poll the queue for new messages and alerts

        :param timeout, seconds; int
        :return: poll result tuple containing the original message and a list of tns object names; (message, alerts)
                 if there is nothing in the queue then poll will return None after the timeout has expired.
        """
        try:
            result = self.q.get(block=True, timeout=timeout)
        except Empty:
            result = None

        return result

    def parse_message(self, msg):
        """Parse a gmail message for tns object names

        :param msg: gmail message object
        :return: list of tns object names
        """
        # Result stays non of message is not structured properly or not from TNS
        result = None

        # Pull message from gmail
        headers = msg["payload"]["headers"]
        for hdr in headers:
            # Only process emails from TNS
            if hdr["name"] == "From" and self.config["tns"]["email"] in hdr["value"]:
                # Decode and parse message body for TNS onj names
                data = msg["payload"]["body"]["data"]
                byte_code = base64.urlsafe_b64decode(data)
                text = byte_code.decode("utf-8")
                soup = BeautifulSoup(text, features="html.parser")
                obj_list = [a.text for a in soup.find_all("a", href=True) if a.text]
                result = obj_list

        return result

    def mark_read(self, message):
        """Marks message as read in gmail, so it won't show up again in our monitoring stream

        :param message: gmail message object
        :return: void
        """
        # Mark as read
        self.service.users().messages().modify(
            userId="me", id=message["id"], body={"removeLabelIds": ["UNREAD"]}
        ).execute()
        # Log
        status = {"action": "message_read", "id": message["id"]}
        self.logger.info(status, extra=status)

    def monitor_notices(self):
        """Starts thread to monitor gmail account for tns alerts:

        :return: void
        """
        self.t = threading.Thread(target=self._monitoring_thread, daemon=True)
        self.t.start()
        # Log
        status = {"status": "starting monitoring thread"}
        self.logger.info(status, extra=status)

    def stop_monitoring(self):
        """Kill monitoring thread.

        :return: void
        """
        if self.t is not None:
            # Set the stop event (should kill the thread)
            self.stop_event.set()
            self.t.join()
        # Log
        status = {"status": "stopping monitoring thread"}
        self.logger.info(status, extra=status)

    def _monitoring_thread(self):
        """Open a gmail service object and continuously monitor gmail for new messages.

        Each new message is parsed of tns object alerts and results are submitted to local queue.
        Also refresh the token every 30 minutes.

        :return: void
        """
        # Connect to service
        service = build("gmail", "v1", credentials=self.creds)
        last_refresh = time.time()
        while not self.stop_event.is_set():
            now = time.time()
            if now - last_refresh >= (30 * 60):
                status = {"status": "refreshing token"}
                self.logger.info(status, extra=status)
                self.creds.refresh(Request())
                service = build("gmail", "v1", credentials=self.creds)
                last_refresh = now

            # Call the Gmail API
            status = {"status": "checking_messages"}
            self.logger.info(status, extra=status)
            time.sleep(self.config["gmail"]["polling_interval"])
            results = (
                service.users()
                .messages()
                .list(userId="me", labelIds=["INBOX"], q="is:unread")
                .execute()
            )
            messages = results.get("messages", [])

            if not messages:
                continue

            for message in messages:
                try:
                    # Read full message
                    time.sleep(self.config["gmail"]["polling_interval"])
                    msg = (
                        service.users()
                        .messages()
                        .get(userId="me", id=message["id"])
                        .execute()
                    )
                except HttpError:
                    # Rate limit, wait 10 seconds and try again
                    status = {"status": "rate_limited, sleeping 12 seconds"}
                    self.logger.warn(status, extra=status)
                    time.sleep(self.config["gmail"]["polling_interval"] * 3)
                    msg = (
                        service.users()
                        .messages()
                        .get(userId="me", id=message["id"])
                        .execute()
                    )

                # Parse message for tns alerts
                alerts = self.parse_message(msg)

                if alerts is None:
                    self.mark_read(message)
                    continue
                # Log
                status = {"status": "recieved alerts", "objects": alerts}
                self.logger.debug(status, extra=status)

                # Submit to queue for processing
                self.q.put((message, alerts))

    def _signal_handler(self, sig, frame):
        status = {"status": "received exit signal", "signal": str(sig), "frame": str(frame)}
        self.logger.info(status, extra=status)
        self.stop_monitoring()
        os._exit(1)



class IMAP(TarxivModule):
    """Module for interfacing with an IMAP email server and parsing TNS alerts."""

    def __init__(self, script_name, reporting_mode=7, debug=False):
        """Create module, authenticate with IMAP server and establish connection."""
        super().__init__(
            script_name=script_name,
            module="imap",
            reporting_mode=reporting_mode,
            debug=debug
        )

        # Logging
        self.logger.info({"status": "connecting to IMAP server"})

        # IMAP connection
        self.conn = None
        try:
            self.conn = imaplib.IMAP4_SSL(self.config["imap"]["server"])
            self.conn.login(
                self.config["imap"]["username"], self.config["imap"]["password"]
            )
            self.conn.select("inbox")
            self.logger.info({"status": "connection success"})
        except Exception as e:
            self.logger.error({"status": "connection failed", "error": str(e)})
            raise

        # Create thread value
        self.t = None
        # Create internal queue
        self.q = Queue()
        # Create stop flag for monitoring
        self.stop_event = threading.Event()
        # Signals
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def poll(self, timeout=1):
        """Once we have began monitoring notices, poll the queue for new messages and alerts

        :param timeout, seconds; int
        :return: poll result tuple containing the original message id and a list of tns object names; (message_id, alerts)
                 if there is nothing in the queue then poll will return None after the timeout has expired.
        """
        try:
            result = self.q.get(block=True, timeout=timeout)
        except Empty:
            result = None, None

        return result

    def parse_message(self, msg_bytes):
        """Parse a raw email message for tns object names

        :param msg_bytes: raw email message as bytes
        :return: list of tns object names
        """
        alerts = []
        msg = email.message_from_bytes(msg_bytes)

        # Only process emails from TNS
        if self.config["tns"]["email"] in msg.get("From", ""):
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if "text/html" in content_type:
                        body = part.get_payload(decode=True).decode()
                        break
                    elif "text/plain" in content_type:
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or 'utf-8'
                        if payload:
                            body = payload.decode(charset, errors='replace')
                            break  # Prefer text/plain

            else:
                body = msg.get_payload(decode=True).decode()

            if body:
                soup = BeautifulSoup(body, features="html.parser")
                # find all a tags with a href
                alerts.extend([a.text for a in soup.find_all("a", href=True) if a.text])
                # if no a tags, search for transient names in the text
                if not alerts:
                    alerts.extend(re.findall(r'\b(20\d{2}[a-z]{2,3})\b', body))

        return alerts

    def mark_read(self, message_id, verbose=False):
        """Marks message as read in IMAP server, so it won't show up again in our monitoring stream

        :param message_id: message uid (bytes)
        :return: void
        """
        self.conn.uid("STORE", message_id, "+FLAGS.SILENT", r"(\Seen)")
        status = {"action": "message_read", "id": message_id.decode()}
        if verbose:
            self.logger.info(status)
        else:
            self.logger.debug(status)

    def mark_unread(self, message_id, verbose=False):
        """Marks message as unread in IMAP server, so it will show up again in our monitoring stream

        :param message_id: message uid (bytes)
        :return: void
        """
        self.conn.uid("STORE", message_id, "-FLAGS.SILENT", r"(\Seen)")
        status = {"action": "message_unread", "id": message_id.decode()}
        if verbose:
            self.logger.info(status)
        else:
            self.logger.debug(status)

    def monitor_notices(self):
        """Starts thread to monitor IMAP account for tns alerts:

        :return: void
        """
        self.t = threading.Thread(target=self._monitoring_thread, daemon=True)
        self.t.start()
        self.logger.info({"status": "starting monitoring thread"})

    def stop_monitoring(self):
        """Kill monitoring thread.

        :return: void
        """
        if self.t is not None:
            self.stop_event.set()
            self.t.join()
        if self.conn:
            self.conn.logout()
        self.logger.info({"status": "stopping monitoring thread"})

    def _monitoring_thread(self):
        """Continuously monitor IMAP inbox for new messages.

        Each new message is parsed of tns object alerts and results are submitted to local queue.
        """
        while not self.stop_event.is_set():
            try:
                self.conn.select("inbox")
                # Search unread by UID
                typ, data = self.conn.uid("SEARCH", None, "UNSEEN")
                if typ != "OK":
                    self.logger.error({"status": "error searching inbox"})
                    time.sleep(self.config["imap"]["polling_interval"])
                    continue

                uids = data[0].split()
                if not uids:
                    time.sleep(self.config["imap"]["polling_interval"])
                    continue

                for uid in uids:
                    # Fetch by UID without setting \Seen
                    typ, msg_data = self.conn.uid("FETCH", uid, "(BODY.PEEK[])")
                    if typ != "OK":
                        self.logger.debug({"status": "error fetching message", "id": uid, "error": str(msg_data)})
                        continue

                    raw_email = msg_data[0][1]
                    alerts = self.parse_message(raw_email)

                    # Treat empty list as "no alerts"
                    if not alerts:
                        self.mark_read(uid)
                        continue
                    else:
                        self.mark_unread(uid)

                    self.logger.debug({"status": "received alerts", "objects": alerts})
                    self.q.put((uid.decode(), alerts))

                time.sleep(self.config["imap"]["polling_interval"])

            except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                self.logger.warning({"status": "connection error, reconnecting", "error": str(e)})
                try:
                    self.conn = imaplib.IMAP4_SSL(self.config["imap"]["server"])
                    self.conn.login(self.config["imap"]["username"], self.config["imap"]["password"])
                except Exception as recon_e:
                    self.logger.error({"status": "reconnection failed", "error": str(recon_e)})
                    self.stop_event.set()  # Stop if we can't reconnect
            except Exception as e:
                self.logger.error({"status": "unexpected error in monitoring thread", "error": str(e)})
                time.sleep(self.config["imap"]["polling_interval"] * 2)


    def _signal_handler(self, sig, frame):
        status = {"status": "received exit signal", "signal": str(sig), "frame": str(frame)}
        self.logger.info(status, extra=status)
        self.stop_monitoring()
        os._exit(1)
