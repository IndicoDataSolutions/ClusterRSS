set_backup() {
  curl -XPUT 'http://localhost:9200/_snapshot/my_backup' -d '{
      "type": "fs",
      "settings": {
          "location": "'$1'",
          "compress": true
      }
  }'
}

s3_backup() {
  curl -XPUT 'http://localhost:9200/_snapshot/my_backup' -d '{
      "type": "s3",
      "settings": {
          "bucket": "themeextraction-backup",
          "region": "us-west-2"
      }
  }'
}

snapshot() {
  url='http://localhost:9200/_snapshot/my_backup/'
  url+=$1
  url+="?wait_for_completion=true"
  curl -XPUT $url
}

delete_snapshot() {
  url='http://localhost:9200/_snapshot/my_backup/'
  url+=$1
  url+="?wait_for_completion=true"
  curl -XDELETE $url
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
