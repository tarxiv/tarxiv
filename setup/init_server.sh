#!/bin/bash
# THIS SCRIPT IS MEANT TO INITIALIZE COUCHBASE IN DOCKER COMPOSE ONLY, ACTUAL PRODUCTION SHOULD BE DONE DIRECTLY ON SERVER

# used to start couchbase server - can't get around this as docker compose only allows you to start one command -
# so we have to start couchbase like the standard couchbase Dockerfile would
# https://github.com/couchbase/docker/blob/master/enterprise/couchbase-server/7.0.3/Dockerfile#L82

# UNCOMMENT THESE IF RUNNING AS DOCKER SETUP
echo "starting couchbase server"
/entrypoint.sh couchbase-server &
sleep 20

# track if setup is complete so we don't try to setup again
FILE=/opt/couchbase/setupComplete.txt
if ! [ -f "$FILE" ]; then

  # RUN AFTER STARTING COUCHBASE
  # Initialize cluster
  echo "initializing cluster"
  /opt/couchbase/bin/couchbase-cli cluster-init \
      -c http://$TARXIV_COUCHBASE_HOST:8091 \
      --cluster-username $TARXIV_COUCHBASE_ADMIN_USERNAME \
      --cluster-password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
      --services data,index,query,fts,analytics

  sleep 2
  # Initialize node
  #echo "initializing node"
  /opt/couchbase/bin/couchbase-cli node-init \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD
  sleep 2

  # Create bucket with 2GiB RAM
  echo "creating bucket and scopes and collections"
  /opt/couchbase/bin/couchbase-cli bucket-create \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --bucket-type couchbase --bucket-ramsize ${TARXIV_COUCHBASE_BUCKET_SIZE:-2048}
  sleep 2
  # Create TNS scope
  /opt/couchbase/bin/couchbase-cli collection-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --create-scope tns
  sleep 2
  # Create object collection
  /opt/couchbase/bin/couchbase-cli collection-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --create-collection tns.objects
  sleep 2
  # Create lightcurve collection`
  /opt/couchbase/bin/couchbase-cli collection-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --create-collection tns.lightcurves
  sleep 2

  # Create xmatch scope
  /opt/couchbase/bin/couchbase-cli collection-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --create-scope xmatch
  sleep 2
  # Create hits collection`
  /opt/couchbase/bin/couchbase-cli collection-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --create-collection xmatch.hits
  sleep 2
  # Create alerts collection`
  /opt/couchbase/bin/couchbase-cli collection-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --create-collection xmatch.alerts
  sleep 2
  # Create alerts collection`
  /opt/couchbase/bin/couchbase-cli collection-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --bucket tarxiv --create-collection xmatch.idx
  sleep 2


  # Create indexes
  echo "building indexes"
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "CREATE PRIMARY INDEX ON tarxiv.tns.objects"
  sleep 2
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "CREATE PRIMARY INDEX ON tarxiv.tns.lightcurves"
  sleep 2
  # Indexes for xmatch
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "CREATE PRIMARY INDEX ON tarxiv.xmatch.hits"
  sleep 2
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "CREATE PRIMARY INDEX ON tarxiv.xmatch.alerts"
  sleep 2
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "CREATE PRIMARY INDEX ON tarxiv.xmatch.idx"
  sleep 2
  # Index for sub querys
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "CREATE INDEX detection_idx ON tarxiv.xmatch.hits (ALL ARRAY id.name FOR id IN identifiers END)"
  sleep 2
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "CREATE INDEX update_idx ON tarxiv.xmatch.hits(updated_at)"
  sleep 2


  # Submit initial values counts into idx (hopefully wont have to worry about this in 2030)
  /opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --script "INSERT INTO tarxiv.xmatch.idx (KEY, VALUE)
              VALUES
                (\"2026\", { \"current_idx\": 0}),
                (\"2027\", { \"current_idx\": 0}),
                (\"2028\", { \"current_idx\": 0}),
                (\"2029\", { \"current_idx\": 0}),
                (\"2030\", { \"current_idx\": 0});"
  sleep 2

  # Create user and enable roles
  echo "Assinging user roles"
  /opt/couchbase/bin/couchbase-cli user-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --set \
    --auth-domain local \
    --rbac-username $TARXIV_COUCHBASE_PIPELINE_USERNAME \
    --rbac-password $TARXIV_COUCHBASE_PIPELINE_PASSWORD \
    --roles data_reader[tarxiv],data_writer[tarxiv],query_select[tarxiv],query_delete[tarxiv],query_update[tarxiv]
  sleep 2
  /opt/couchbase/bin/couchbase-cli user-manage \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --set \
    --auth-domain local \
    --rbac-username $TARXIV_COUCHBASE_API_USERNAME \
    --rbac-password $TARXIV_COUCHBASE_API_PASSWORD \
    --roles data_reader[tarxiv],query_select[tarxiv]

  # create file so we know that the cluster is setup and don't run the setup again
  touch $FILE
fi
# docker compose will stop the container from running unless we do this
# known issue and workaround
tail -f /dev/null