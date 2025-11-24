####################################################################################
# Sample Script that will allow users to monitor tarxiv events via hopskotch alerts
####################################################################################

from hop.auth import Auth
from hop import Stream
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
        pprint.pprint(message.content)




