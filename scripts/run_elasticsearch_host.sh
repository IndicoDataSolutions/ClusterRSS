#!/bin/sh
VERSION=elasticsearch-1.3.4
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"


if [ ! -f $DIR/$VERSION/bin/elasticsearch ]; then
    wget https://download.elasticsearch.org/elasticsearch/elasticsearch/$VERSION.tar.gz
    tar -xf $DIR/$VERSION.tar.gz
fi

$DIR/$VERSION/bin/elasticsearch
