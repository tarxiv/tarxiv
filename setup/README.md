# Setup Instructions

This directory contains the Docker configurations for the services required by the TarXiv pipeline and API. To start-up the services, run the following commands:

```commandline
docker compose up setup_elasticsearch
docker compose up -d elasticsearch logstash kibana couchbase
```

The second command will take about one minute to correctly start-up the Couchbase daemon.

You can access the Couchbase web interface at http://[$TARXIV_COUCHBASE_HOST]:8091/.