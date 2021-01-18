import sys
import csv
import ckanapi
from slugify import slugify

INPUT_CSV = 'scripts/initial_data_container_list_feb_2018.csv'


def create_data_containers(url, api_key):

    ckan = ckanapi.RemoteCKAN(url, api_key)

    done = []
    orgs = []

    with open(INPUT_CSV, 'rb') as csv_file:
        reader = csv.reader(csv_file)
        # Skip headers
        next(reader, None)
        for row in reader:

            # Save root level containers
            if row[0] not in done:
                done.append(row[0])

                orgs.append({
                    'name': slugify(row[0]),
                    'title': row[0],
                    'type': 'data-container',
                    'geographic_area': row[0],
                    # TODO: replace by real values
                    'country': 'VAR',
                    'visible_external': True,
                })

            # Save 1st level containers
            if row[1].strip() and row[1] not in done:
                done.append(row[1])

                orgs.append({
                    'name': slugify(row[1]),
                    'title': row[1],
                    'type': 'data-container',
                    'geographic_area': row[1],
                    # TODO: replace by real values
                    'country': 'VAR',
                    'groups': [{'name': slugify(row[0])}],
                    'visible_external': True,
                })

            # Save 2nd level containers
            if row[2].strip() and row[2] not in done:
                done.append(row[2])

                orgs.append({
                    'name': slugify(row[2]),
                    'title': row[2],
                    'type': 'data-container',
                    'geographic_area': row[2],
                    # TODO: replace by real values
                    'country': 'VAR',
                    'groups': [{'name': slugify(row[1])}],
                    'visible_external': True,
                })

    # Create orgs in CKAN
    for org in orgs:
        try:
            ckan.call_action('organization_create', org, requests_kwargs={'verify': False})
            print 'Created data container {}'.format(org['name'])
        except ckanapi.errors.ValidationError as e:
            print str(e)
            pass

if __name__ == '__main__':

    url = sys.argv[1]
    api_key = sys.argv[2]

    create_data_containers(url, api_key)
