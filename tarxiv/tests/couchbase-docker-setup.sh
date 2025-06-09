#!/bin/bash

# Install docker
sudo dnf install docker -y
# Change permissions to docker socket file and restart
sudo chown root:$USER /var/run/docker.sock

# Start couchbase container 
docker run -d --name tarxiv-base -p 8091-8096:8091-8096 -p 11210-11211:11210-11211 couchbase
# Initialize cluster 
docker exec -it tarxiv-base \
  couchbase-cli cluster-init \
    -c http://127.0.0.1:8091 \
    --cluster-username $COUCHBASE_ADMIN_USER \
    --cluster-password $COUCHBASE_ADMIN_PASS \
    --services data,index,query,fts,analytics
# Create bucket with 2GiB RAM
docker exec -it tarxiv-base \
  couchbase-cli bucket-create \
    -c http://127.0.0.1:8091 \
    --username $COUCHBASE_ADMIN_USER \
    --password $COUCHBASE_ADMIN_PASS \
    --bucket tarxiv --bucket-type couchbase --bucket-ramsize 2048
# Create TNS scope
docker exec -it tarxiv-base \
  couchbase-cli collection-manage \
    -c http://127.0.0.1:8091 \
    --username $COUCHBASE_ADMIN_USER \
    --password $COUCHBASE_ADMIN_PASS \
    --bucket tarxiv --create-scope tns
# Create object collection
docker exec -it tarxiv-base \
  couchbase-cli collection-manage \
    -c http://127.0.0.1:8091 \
    --username $COUCHBASE_ADMIN_USER \
    --password $COUCHBASE_ADMIN_PASS \
    --bucket tarxiv --create-collection tns.objects
# Create lightcurve collection
docker exec -it tarxiv-base \
  couchbase-cli collection-manage \
    -c http://127.0.0.1:8091 \
    --username $COUCHBASE_ADMIN_USER \
    --password $COUCHBASE_ADMIN_PASS \
    --bucket tarxiv --create-collection tns.lightcurves
# Create indexes
docker exec -it tarxiv-base \
  cbq -u $COUCHBASE_ADMIN_USER -p $COUCHBASE_ADMIN_PASS \
    --script "CREATE PRIMARY INDEX ON tarxiv.tns.objects"
docker exec -it tarxiv-base \
  cbq -u $COUCHBASE_ADMIN_USER -p $COUCHBASE_ADMIN_PASS \
    --script "CREATE PRIMARY INDEX ON tarxiv.tns.lightcurves"
# Create user and enable roles
docker exec -it tarxiv-base \
  couchbase-cli user-manage \
    -c http://127.0.0.1:8091 \
    --cluster-username $COUCHBASE_ADMIN_USER \
    --cluster-password $COUCHBASE_ADMIN_PASS \
    --set \
    --rbac-username $COUCHBASE_PIPELINE_USER \
    --rbac-password $COUCHBASE_PIPELINE_PASS \
    --roles data_reader[tarxiv],data_writer[tarxiv],query_select[tarxiv],query_delete[tarxiv],query_update[tarxiv]
docker exec -it tarxiv-base \
  couchbase-cli user-manage \
    -c http://127.0.0.1:8091 \
    --cluster-username $COUCHBASE_ADMIN_USER \
    --cluster-password $COUCHBASE_ADMIN_PASS \
    --set \
    --rbac-username $COUCHBASE_API_USER \
    --rbac-password $COUCHBASE_API_PASS \
    --roles data_reader[tarxiv],query_select[tarxiv]
