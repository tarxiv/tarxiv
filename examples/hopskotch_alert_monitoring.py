####################################################################################
# Sample Script that will allow users to monitor tarxiv events via hopskotch alerts
####################################################################################

from hop.auth import Auth
from hop import Stream
import datetime
import argparse
import pprint

parser = argparse.ArgumentParser("hopskotch_alert_monitoring")
parser.add_argument("username", type=str, help="hopskotch username")
parser.add_argument("password", type=str, help="hopskotch password")
args = parser.parse_args()

auth = Auth(args.username, args.password)
stream = Stream(auth)

# This will block until new messages are received and run until killed (like while True:)
with stream.open("kafka://kafka.scimma.org/tarxiv.tns", "r") as s:
    for message in s:
        # Here your can submit the alert for further processing
        alert = message.content
        pprint.pprint(alert)

        # Get current date
        local_time = datetime.datetime.now()
        utc_time = local_time.astimezone(datetime.timezone.utc)
        # Time filter
        date_limit = utc_time - datetime.timedelta(days=5)

        # Now we can filter
        filter_dict = {
            "redshift": [{"source": "any", "value": 0.01, "operator": "<"}],
            "discovery_date": [{"source": "tns", "date_limit": date_limit}],
            "discovery_source": [
                {
                    "source": "tns",
                    "value": ["GOTO", "ASAS-SN", "ZTF", "LSST"],
                    "operator": "IN",
                }
            ],
            "latest_detection": [
                {
                    "source": "atlas",
                    "date_limit": date_limit,
                    "value": "18.5",
                    "operator": "<",
                    "filter": "c",
                },
                {
                    "source": "asas-sn",
                    "date_limit": date_limit,
                    "value": "17.5",
                    "operator": "<",
                    "filter": "g",
                },
                {"source": "any", "mag_rate": 0.05},
            ],
        }
