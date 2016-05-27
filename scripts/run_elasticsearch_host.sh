#!/bin/sh
VERSION=elasticsearch-1.3.4
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )


if [ ! -f $DIR/$VERSION/bin/elasticsearch ]; then
    wget https://download.elasticsearch.org/elasticsearch/elasticsearch/$VERSION.tar.gz -O $DIR/$VERSION.tar.gz
    tar -xf $DIR/$VERSION.tar.gz -C $DIR
    cd VERSION
    bin/plugin install elasticsearch/elasticsearch-cloud-aws/2.7.1
fi

ES_HEAP_SIZE=4g $DIR/$VERSION/bin/elasticsearch
