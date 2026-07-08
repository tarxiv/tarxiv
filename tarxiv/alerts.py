# Listen for new TNS Alerts
from .utils import TarxivModule

from confluent_kafka import Producer
from bs4 import BeautifulSoup
import threading
import imaplib
import socket
import signal
import email
import time
import re
import os


class IMAP(TarxivModule):
    """Module for interfacing with an IMAP email server and parsing TNS alerts."""

    def __init__(self, script_name, reporting_mode=7, debug=False):
        """Create module, authenticate with IMAP server and establish connection."""
        super().__init__(
            script_name=script_name,
            module="imap",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Logging
        self.logger.info({"status": "connecting to IMAP server"})

        # IMAP connection
        self.conn = None
        self.imap_user = os.getenv("TARXIV_IMAP_USERNAME", "")
        self.imap_pass = os.getenv("TARXIV_IMAP_PASSWORD", "")
        self.kafka_host = os.getenv("TARXIV_KAFKA_HOST", "localhost")
        try:
            self.conn = imaplib.IMAP4_SSL(self.config["imap"]["server"])
            self.conn.login(self.imap_user, self.imap_pass)
            self.conn.select("inbox")
            self.logger.info({"status": "connection success"})
        except Exception as e:
            self.logger.error({"status": "connection failed", "error": str(e)})
            raise

        # Get kafka configuration
        conf = {
            "bootstrap.servers": self.kafka_host + ":9092",
            "delivery.timeout.ms": 10000,
            "queue.buffering.max.messages": 1000000,
            "queue.buffering.max.ms": 5000,
            "batch.num.messages": 100,
            "client.id": socket.gethostname(),
        }
        self.producer = Producer(conf)

        # Create stop flag for monitoring
        self.stop_event = threading.Event()
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def signal_handler(self, sig, frame):
        status = {
            "status": "received exit signal, wait to finish processing",
            "signal": str(sig),
            "frame": str(frame),
        }
        self.stop_event.set()
        self.logger.info(status, extra=status)

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
                        charset = part.get_content_charset() or "utf-8"
                        if payload:
                            body = payload.decode(charset, errors="replace")
                            break  # Prefer text/plain

            else:
                body = msg.get_payload(decode=True).decode()

            if body:
                soup = BeautifulSoup(body, features="html.parser")
                # find all a tags with a href
                alerts.extend([a.text for a in soup.find_all("a", href=True) if a.text])
                # if no a tags, search for transient names in the text
                if not alerts:
                    alerts.extend(re.findall(r"\b(20\d{2}[a-z]{2,3})\b", body))

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
                        self.logger.debug({
                            "status": "error fetching message",
                            "id": uid,
                            "error": str(msg_data),
                        })
                        continue

                    raw_email = msg_data[0][1]
                    alerts = self.parse_message(raw_email)

                    # Treat empty list as "no alerts"
                    if not alerts:
                        self.mark_read(uid)
                        continue

                    # Show alerts
                    status = {"status": "received alerts", "objects": alerts}
                    self.logger.info(status, extra=status)
                    # Now submit what we have
                    for tns_obj_id in alerts:
                        self.producer.produce(
                            topic="internal_tns_alerts",
                            value=tns_obj_id,
                            callback=self.acked,
                        )
                    # Mark read, when submitted all alerts
                    self.mark_read(uid)

                # sLEEP
                time.sleep(self.config["imap"]["polling_interval"])

            except (imaplib.IMAP4.abort, imaplib.IMAP4.error) as e:
                status = {"status": "connection error, reconnecting", "error": str(e)}
                self.logger.warning(status, extra=status)
                try:
                    self.conn = imaplib.IMAP4_SSL(self.config["imap"]["server"])
                    self.conn.login(self.imap_user, self.imap_pass)
                except Exception as recon_e:
                    status = {"status": "reconnection failed", "error": str(recon_e)}
                    self.logger.error(status, extra=status)
                    self.stop_event.set()  # Stop if we can't reconnect
            except Exception as e:
                status = {
                    "status": "unexpected error in monitoring thread",
                    "error": str(e),
                }
                self.logger.error(status, extra=status)
                time.sleep(self.config["imap"]["polling_interval"] * 2)

        # Finished monitoring logout
        self.conn.logout()

    def acked(self, err, msg):
        if err is not None:
            status = {"status": "failed kafka publish", "msg": msg}
            self.logger.error(status, extra=status)
