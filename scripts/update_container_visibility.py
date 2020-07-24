# -*- coding: utf-8 -*-

import sys
import csv
import ckanapi
from slugify import slugify

INPUT_CSV = 'scripts/update_container_visibility_aug2020.csv'

def update_data_containers(url, api_key):

    ckan = ckanapi.RemoteCKAN(url, api_key)

    with open(INPUT_CSV, 'rb') as csv_file:
        reader = csv.reader(csv_file)
        # Skip headers
        next(reader, None)
        for row in reader:
            try:
                visible_external = True if row[1] == 'Yes' else False
                ckan.call_action(
                    'organization_patch',
                    { 'id': row[0], 'visible_external': visible_external },
                    requests_kwargs={'verify': False}
                )
                print(u"updated '{}' ✅".format(row[0]))
            except (ckanapi.errors.ValidationError, ckanapi.errors.NotFound) as e:
                print(u"failed to update '{}' ❌".format(row[0]))
                print(str(e))
                pass


if __name__ == '__main__':

    url = sys.argv[1]
    api_key = sys.argv[2]

    update_data_containers(url, api_key)
