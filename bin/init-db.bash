#!/bin/bash
set -euo pipefail

ckan -c ./test.ini db init
ckan -c ./test.ini unhcr init-db
