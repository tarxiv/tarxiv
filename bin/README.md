# Pipeline and API

To start the TarXiv pipeline, run: 
```commandline
usage: tns-ingest [-h] [--debug] [--alerts | --bulk_missing | --bulk_update | --daily_update]

TarXiv TNS Alert ingestion. Monitor new TNS alerts, and query relevant data into database.'

options:
  -h, --help      show this help message and exit
  --debug         set to enable printing/logging in debug mode
  --alerts        Ingest live TNS alerts from email
  --bulk_missing  Ingest all TNS objects not already in database
  --bulk_update   Update all TNS objects, even if in database
  --daily_update  Update current active TNS objects
```

To start the TarXiv API service, run:
```commandline
usage: start-api [-h] [--debug]

Run TarXiv Flask API

options:
  -h, --help  show this help message and exit
  --debug     set to enable printing/logging in debug mode

```