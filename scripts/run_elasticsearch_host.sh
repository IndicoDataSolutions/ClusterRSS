#!/bin/sh
VERSION=elasticsearch-2.3.3
DIR=$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )


if [ ! -f $DIR/$VERSION/bin/elasticsearch ]; then
    wget https://download.elasticsearch.org/elasticsearch/elasticsearch/$VERSION.tar.gz -O $DIR/$VERSION.tar.gz
    tar -xf $DIR/$VERSION.tar.gz -C $DIR
    cd $VERSION
    sudo bin/plugin install cloud-aws
fi

ES_HEAP_SIZE=4g $DIR/$VERSION/bin/elasticsearch
