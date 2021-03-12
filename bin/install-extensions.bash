#!/bin/bash
set -euo pipefail


git clone https://github.com/ckan/ckanext-scheming
(cd ckanext-scheming && python setup.py develop)

git clone https://github.com/okfn/ckanext-hierarchy
(cd ckanext-hierarchy && python setup.py develop)

git clone https://github.com/okfn/ckanext-collaborators
(cd ckanext-collaborators && python setup.py develop)

git clone https://github.com/keitaroinc/ckanext-s3filestore
(cd ckanext-s3filestore && git checkout ckan-2.8 && python setup.py develop && pip install -r requirements.txt)
