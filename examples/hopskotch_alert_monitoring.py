####################################################################################
# Sample Script that will allow users to monitor tarxiv events via hopskotch alerts
####################################################################################
from fontTools.misc.psOperators import ps_string
from hop.auth import Auth
from hop import Stream
import datetime
import operator
import argparse
import pprint

parser = argparse.ArgumentParser("hopskotch_alert_monitoring")
parser.add_argument("username", type=str, help="hopskotch username")
parser.add_argument("password", type=str, help="hopskotch password")
args = parser.parse_args()

auth = Auth(args.username, args.password)
stream = Stream(auth)


def check_message(message, condition_dict):
    """
    Check if this message matches the filter criteria.

    :param message: tarxiv tns message; dict
    :param filter_dict: defined set of filters; dict
    :return: bool
    """
    is_true = True

    for field_name, condition_list in condition_dict.items():
        # Check if this field is in the message
        if field_name not in message.keys():
            is_true = False
            break
        # If the field is in the message, then we check it
        for condition in condition_list:
            if condition["source"] == "any":
                is_true &= any(
                    check_field(field, condition) for field in message[field_name]
                )
            elif condition["source"] == "all":
                is_true &= all(
                    check_field(field, condition) for field in message[field_name]
                )
            else:
                is_true &= all(
                    check_field(field, condition)
                    for field in message[field_name]
                    if field["source"] == condition["source"]
                )
    return is_true


def check_field(message_field, condition):
    is_true = True
    # First check if we have valid filters
    if len({"date_limit", "value", "mag_rate", "filter"} - set(condition.keys())) == 4:
        is_true = False

    # Date limits
    if "date_limit" in condition.keys():
        date = datetime.datetime.fromisoformat(message_field["value"])
        is_true &= condition["operator"](message_field["value"], date)

    # Check list comparison (usually looking for one of several discovery sources)
    if "value" in condition.keys() and type(condition["value"]) is list:
        is_true &= message_field["value"] in condition["value"]

    # Check normal value comparison
    if "value" in condition.keys() and type(condition["value"]) is not list:
        is_true &= condition["operator"](message_field["value"], condition["value"])

    # Check mag rates
    if "mag_rate" in condition.keys():
        is_true &= condition["operator"](message_field["value"], condition["mag_rate"])

    # Check filter specific mag checks (latest detections and non detections)
    if "filter" in condition.keys():
        is_true &= condition["filter"] == message_field["filter"]

    return is_true


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
            "redshift": [
                {"source": "any", "value": 0.01, "operator": operator.lt},
            ],
            "discovery_date": [
                {"source": "tns", "date_limit": date_limit, "operator": operator.gt},
            ],
            "discovery_source": [
                {"source": "tns", "value": ["GOTO", "ASAS-SN", "ZTF", "Rubin"]}
            ],
            "latest_detection": [
                {
                    "source": "atlas",
                    "value": 18.5,
                    "operator": operator.lt,
                    "filter": "c",
                },
                {
                    "source": "asas-sn",
                    "value": 17.5,
                    "operator": operator.lt,
                    "filter": "g",
                },
                {"source": "atlas", "date_limit": date_limit, "operator": operator.gt},
                {
                    "source": "asas-sn",
                    "date_limit": date_limit,
                    "operator": operator.gt,
                },
                {"source": "any", "mag_rate": 0.05, "operator": operator.gt},
            ],
        }
