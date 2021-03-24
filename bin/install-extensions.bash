#!/bin/bash
set -euo pipefail


git clone --depth 1 --branch release-2.1.0 https://github.com/ckan/ckanext-scheming
(cd ckanext-scheming && python setup.py develop)

git clone --depth 1 --branch v0.2.2 https://github.com/okfn/ckanext-hierarchy
(cd ckanext-hierarchy && python setup.py develop)

git clone --depth 1 --branch 0.0.9 https://github.com/okfn/ckanext-collaborators
(cd ckanext-collaborators && python setup.py develop)

git clone --depth 1 --branch ckan-2.8 https://github.com/keitaroinc/ckanext-s3filestore
(cd ckanext-s3filestore && python setup.py develop && pip install -r requirements.txt)
