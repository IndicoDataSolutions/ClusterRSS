DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )

# Stop Elasticsearch
sudo kill -9 $(ps aux | grep elasticsearch | awk '{print $2}')
python -c "from cluster import ESConnection; es = ESConnection('localhost:9200', index='indico-cluster-data'); es.delete()"

rm -rf $DIR/backup
aws s3 cp --recursive s3://corpii/finance/backup $DIR/backup

curl -XPUT 'http://localhost:9200/_snapshot/my_backup' -d '{
    "type": "fs",
    "settings": {
        "location": "'$DIR'/backup",
        "compress": true
    }
}'


snapshot=$(awk '/./{line=$0} END{print line}' $DIR/backup/history.txt | awk '{print $1}')
curl -XPOST "http://localhost:9200/_snapshot/my_backup/"$snapshot"/_restore"
