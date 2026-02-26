from tarxiv.utils import TarxivModule
from confluent_kafka import Consumer, Producer
from fink_client.consumer import AlertConsumer
from astropy.time import Time
import traceback
import json
import os

class LSSTListener(TarxivModule):

    def __init__(self, script_name, reporting_mode, debug=False):
        """Read in data for survey sources from config directory"""
        super().__init__(
            script_name=script_name,
            module="lsst_alerts",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Create consumer (24 hour timeout)
        self.consumer = Consumer({
            'bootstrap.servers': self.config["lasair"]["kafka_endpoint"],
            'group.id': self.config["lasair"]["kafka_group_id"],
            'auto.offset.reset': 'smallest',
            'enable.auto.commit': False,  # Manual commit
            'enable.auto.offset.store': True,  # Manual store/commit
            'max.poll.interval.ms': 3600000,
            'session.timeout.ms': 1800000,
            'heartbeat.interval.ms': 30000,
            'request.timeout.ms': 30000,
            'enable.partition.eof': False})
        self.consumer.subscribe([self.config["lasair"]["kafka_topic"]])
        # Producer for sending to xmatch service
        conf = {'bootstrap.servers': os.environ["TARXIV_KAFKA_HOST"],
                'queue.buffering.max.messages': 1000,
                'queue.buffering.max.ms': 5000,
                'batch.num.messages': 16,
                'client.id': self.module}
        self.producer = Producer(conf)

    def ingest_alerts(self):
        while not self.stop_event.is_set():
            try:
                # Get message
                msg = self.consumer.poll()
                # Ignore empty
                if msg is None:
                    continue
                # Error
                elif msg.error():
                    status = {"status": "kafka consumer error",
                              "error_text": msg.error().str()}
                    self.logger.error(status, extra=status)
                else:
                    payload = json.loads(msg.value().decode("utf-8"))
                    # Now we submit to the spark processing thread
                    detection = {
                        "obj_id": payload["diaObjectId"],
                        "ra_deg": payload["ra"],
                        "dec_deg": payload["decl"],
                        "timestamp": Time(payload["lastDiaSourceMjdTai"], format="mjd").isot,
                        "source": "lsst"
                    }
                    # Now send to xmatch kafka sink
                    self.producer.produce(
                        topic=self.config["xmatch_ingest_topic"],
                        value=json.dumps(detection).encode("utf-8"),
                        callback=self.producer_error
                    )
                    self.producer.poll(0)
                    # Debug message
                    status = {"status": "forwarded message", "payload": detection}
                    self.logger.debug(status, extra=status)

            except Exception as e:
                status = {
                    "status": "listener error",
                    "error_text": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(status, extra=status)

        # Flush producer
        self.producer.flush()

    def producer_error(self, err, payload):
            # Aux method for acknowledging payload receipt
            if err is not None:
                status = {"status": "kafka producer error",
                          "payload": payload,}
                self.logger.error(status, extra=status)


class ZTFListener(TarxivModule):

    def __init__(self, script_name, reporting_mode, debug=False):
        """Read in data for survey sources from config directory"""
        super().__init__(
            script_name=script_name,
            module="ztf_alerts",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        # Initial config
        conf = {
            "bootstrap.servers": self.config["ztf"]["kafka_endpoint"],
            "group.id": self.config["ztf"]["kafka_group_id"],

        }
        # Make on consumer for each of these topics
        self.consumer = AlertConsumer(survey="ztf", topics=self.config["ztf"]["kafka_topics"], config=conf)

        # Producer for sending to xmatch service
        conf = {'bootstrap.servers': os.environ["TARXIV_KAFKA_HOST"],
                'queue.buffering.max.messages': 1000,
                'queue.buffering.max.ms': 5000,
                'batch.num.messages': 16,
                'client.id': self.module}
        self.producer = Producer(conf)

    def ingest_alerts(self):
        while not self.stop_event.is_set():
            try:
                # Get message
                topic, alert, _ = self.consumer.poll()
                # Assume that Fink client handles errors is
                # Ignore empty
                if topic is None:
                    continue
                # Error
                else:
                    # Now we submit to the spark processing thread
                    detection = {
                        "obj_id": alert["objectId"],
                        "ra_deg": alert['candidate']["ra"],
                        "dec_deg": alert['candidate']["dec"],
                        "timestamp": Time(alert['candidate']["jd"], format="jd").isot,
                        "source": "ztf"
                    }
                    # Now send to xmatch kafka sink
                    self.producer.produce(
                        topic=self.config["xmatch_ingest_topic"],
                        value=json.dumps(detection).encode("utf-8"),
                        callback=self.producer_error
                    )
                    self.producer.poll(0)
                    # Debug message
                    status = {"status": "forwarded message", "payload": detection}
                    self.logger.debug(status, extra=status)

            except Exception as e:
                status = {
                    "status": "listener error",
                    "error_text": str(e),
                    "traceback": traceback.format_exc()
                }
                self.logger.error(status, extra=status)
        # Flush producer
        self.producer.flush()

    def producer_error(self, err, payload):
        # Aux method for acknowledging payload receipt
        if err is not None:
            status = {"status": "kafka producer error",
                      "payload": payload, }
            self.logger.error(status, extra=status)
