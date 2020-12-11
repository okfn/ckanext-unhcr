#!/bin/bash
set -euo pipefail


for dir in ./bin/patches/*; do \
    for file in $(find "$dir"/*.patch | sort -g); do \
        abspath=$(readlink -f "$file");
        echo "$0: Applying patch $abspath";
        (cd /srv/app/src/ckan && git apply "$abspath" --verbose);
    done ; \
done
