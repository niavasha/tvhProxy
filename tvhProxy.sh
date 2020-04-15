#!/bin/bash
if [ -f .env ] ; then 
    source .env
fi

DIR=$(dirname $0)
cd $DIR 

source .venv/bin/activate
python tvhProxy.py
