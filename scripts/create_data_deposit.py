import sys
import ckanapi


def create_data_deposit(url, api_key):

    ckan = ckanapi.RemoteCKAN(url, api_key)

    # Create deposit in CKAN
    try:
        ckan.action.organization_create(**{
            'name': 'data-deposit',
            'title': 'Data Deposit',
            'type': 'data-container',
            'country': 'VAR',
            'geographic_area': 'World',
        })
        print('Created data deposit')
    except ckanapi.errors.ValidationError as e:
        print str(e)
        pass

if __name__ == '__main__':

    url = sys.argv[1]
    api_key = sys.argv[2]

    create_data_deposit(url, api_key)
