#!/bin/bash
# THIS SCRIPT IS MEANT TO INITIALIZE COUCHBASE IN DOCKER COMPOSE ONLY, ACTUAL PRODUCTION SHOULD BE DONE DIRECTLY ON SERVER

# used to start couchbase server - can't get around this as docker compose only allows you to start one command -
# so we have to start couchbase like the standard couchbase Dockerfile would
# https://github.com/couchbase/docker/blob/master/enterprise/couchbase-server/7.0.3/Dockerfile#L82
echo "starting couchbase server"
./entrypoint.sh couchbase-server &
sleep 10

# Initialize node
#echo "initializing node"
#/opt/couchbase/bin/couchbase-cli node-init \
#	-c http://$TARXIV_COUCHBASE_HOST:8091 \
#	--username $TARXIV_COUCHBASE_ADMIN_USERNAME \
#	--password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
#	--node-init-data-path /data/couchbase/data \
#	--node-init-index-path /data/couchbase/indexes \
#	--node-init-analytics-path /data/couchbase/analytics \
#	--node-init-eventing-path /data/couchbase/eventing

# Initialiaze cluster 
echo "initializing cluster"
/opt/couchbase/bin/couchbase-cli cluster-init \
    -c http://$TARXIV_COUCHBASE_HOST:8091 \
    --cluster-username $TARXIV_COUCHBASE_ADMIN_USERNAME \
    --cluster-password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
    --services data,index,query,fts

sleep 2

# Create bucket with 2GiB RAM
echo "creating bucket and scopes and collections"
/opt/couchbase/bin/couchbase-cli bucket-create \
  -c http://$TARXIV_COUCHBASE_HOST:8091 \
  --username $TARXIV_COUCHBASE_ADMIN_USERNAME \
  --password $TARXIV_COUCHBASE_ADMIN_PASSWORD \
  --bucket tarxiv --bucket-type couchbase --bucket-ramsize 2048
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
# Create indexes
echo "building indexes"
/opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
  --script "CREATE PRIMARY INDEX ON tarxiv.tns.objects"
sleep 2
/opt/couchbase/bin/cbq -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD \
  --script "CREATE PRIMARY INDEX ON tarxiv.tns.lightcurves"
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
