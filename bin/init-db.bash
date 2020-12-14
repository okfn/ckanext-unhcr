#!/bin/bash
set -euo pipefail


paster --plugin=ckan db init -c ./test.ini
paster --plugin=ckanext-unhcr unhcr init-db -c ./test.ini
paster --plugin=ckanext-collaborators collaborators init-db -c ./test.ini
