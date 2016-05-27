set_backup() {
  curl -XPUT 'http://localhost:9200/_snapshot/my_backup' -d '{
      "type": "fs",
      "settings": {
          "location": "'$1'",
          "compress": true
      }
  }'
}

snapshot() {
  url='http://localhost:9200/_snapshot/my_backup/'
  url+=$1
  url+="?wait_for_completion=true"
  curl -XPUT $url
}

status() {
  curl -XGET "http://localhost:9200/_snapshot/my_backup/"$1"/_status"
}

restore() {
  curl -XPOST "http://localhost:9200/_snapshot/my_backup/"$1"/_restore"
}

count() {
  curl -XGET "http://localhost:9200/indico-cluster-data/_count"
}

download() {
  aws s3 cp s3://corpii/finance/backups
}
