#!/usr/bin/env bash
FILE=$2
if test ! -f "$FILE"; then
  wget -O $2 $1
fi
