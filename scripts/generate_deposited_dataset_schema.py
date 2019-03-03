import json
from collections import OrderedDict


# Module API

INPUT_JSON = 'ckanext/unhcr/schemas/dataset.json'
OUTPUT_JSON = 'ckanext/unhcr/schemas/deposited_dataset.json'

def generate_deposited_dataset_schema():

    # Read `dataset` schema
    with open(INPUT_JSON) as file:
        schema = OrderedDict(json.load(file))

    # Update dataset type
    schema['dataset_type'] = 'deposited-dataset'

    # Remove dataset required flags
    for field in schema['dataset_fields'] + schema['resource_fields']:
        if field['field_name'] not in ['title']:
            field['required'] = False

    # Remove resource required flags
    for field in schema['resource_fields'] + schema['resource_fields']:
        if field['field_name'] not in ['type']:
            field['required'] = False

    # Handle organization fields
    for index, field in enumerate(list(schema['dataset_fields'])):
        if field['field_name'] == 'owner_org':

            # owner_org
            field['form_snippet'] = None
            field['display_snippet'] = None
            field['validators'] = 'deposited_dataset_owner_org'
            field['required'] = True

            # owner_org_dest
            schema['dataset_fields'].insert(index + 1, {
                'field_name': 'owner_org_dest',
                'label': 'Data Container',
                'form_snippet': 'owner_org_dest.html',
                'display_snippet': 'owner_org_dest.html',
                'validators': 'deposited_dataset_owner_org_dest',
                'required': True,
            })

    # Write `deposited-dataset` schema tweaking order
    with open(OUTPUT_JSON, 'w') as file:
        schema['dataset_fields'] = schema.pop('dataset_fields')
        schema['resource_fields'] = schema.pop('resource_fields')
        json.dump(schema, file, indent=4)

    print('Schema for the `deposited-dataset` type has been generated')


# Main script

if __name__ == '__main__':
    generate_deposited_dataset_schema()
