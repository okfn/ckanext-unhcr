import os
import sys
import json
import ckanapi
import sqlalchemy
from ckanext.unhcr import helpers


def migrate_data_collectors():
    engine = sqlalchemy.create_engine(os.environ['CKAN_SQLALCHEMY_URL'])

    # Index legacy collectors
    collectors = {}
    for collector in json.load(open(__file__.replace('py', 'json'))):
        collectors[collector['value']] = collector['label']

    # It doesn't work because of validation
    # Update datasets
    #  ckan = ckanapi.RemoteCKAN(url, api_key)
    #  datasets = ckan.action.package_list()
    #  for dataset in datasets:
        #  labels = []
        #  dataset = ckan.action.package_show(id=dataset)
        #  for value in helpers.normalize_list(dataset.get('data_collector')):
            #  label = collectors.get(value, value)
            #  labels.append(label)
        #  value = ','.join(labels)
        #  dataset['data_collector'] = value
        #  ckan.action.package_update(**dataset)

    # So we use direct database calls
    # We use string interpolation because it's an internal script
    for table in ['package_extra', 'package_extra_revision']:
        rows = engine.execute("select * from %s where key = 'data_collector'" % table)
        for row in rows:
            value = row.value
            try:
                labels = []
                for value in json.loads(row.value):
                    label = collectors.get(value, value)
                    labels.append(label)
                value = ','.join(labels)
            except Exception:
                continue
            engine.execute("update %s set value = '%s' where id = '%s' and key = 'data_collector'" % (table, value, row.id))
            print('Updated dataset "%s" in the table "%s"' % (row.package_id, table))

    # Notify about finishing
    print('Migration is finished')
    print('Do not forget to rebuild the index: "paster --plugin=ckan search-index --config=production.ini rebuild"')


if __name__ == '__main__':
    migrate_data_collectors()
