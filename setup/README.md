# Setup Instructions

This directory contains the Docker configurations for the services required by the TarXiv pipeline and API. To start-up the services, run the following commands:

```commandline
docker compose run setup_elasticsearch
docker compose up  elasticsearch logstash kibana couchbase
```

The second command will take about one minute to correctly start-up the Couchbase daemon.

###### You can access the Couchbase web interface at http://locahost:8091/.

# Local development setup

If you are looking to run a local development version of the system you should be able to just use the example environment variables in the `.env.sample` file, simply by copying it to the setup directory and renaming it to .env, i.e. 

```commandline
cp .env.sample .env
```

After this, running the above docker compose commands _should_ work. 
We have encountered several instances where more memory is required (up to 12GB should work), usually on Mac where docker runs in a virtualised environment.
You may also need to pre-create the directories in `.data` for each of the microservices so they have appropriate permissions:

```commandline
mkdir -p .data/elastic .data/couchbase .data/redis
```

## Populating with test data

There is a db_utils tool in the scripts directory which should allow you to load in the example dataset found in this directory (`example_dataset.json`). You should be able to run the following command:

```commandline
python ../scripts/db_utils.py -l -f example_dataset.json
```

but only if the following caveats are true:
- You have set up your `tarxiv` config file correctly
- You have couchbase running with docker compose
- You have set up a virtual environment, or similar, with the necessary dependencies to run `tarxiv`

