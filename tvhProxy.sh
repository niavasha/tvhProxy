#!/bin/bash

DIR=$(dirname $0)
cd $DIR 

source .venv/bin/activate
python tvhProxy.py
