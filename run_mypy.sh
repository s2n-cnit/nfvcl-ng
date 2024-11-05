#!/bin/bash
cd src || exit
poetry run mypy --config-file ../mypy.ini nfvcl
