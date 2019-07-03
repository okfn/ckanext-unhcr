"""
This is a script for migrating existing private datasets to
the new restricted type (public metadata / private downloads).

"""
import sys
import argparse
import requests
from urllib import urlencode
import json


# Public

def update_datasets(url, api_key):

    params = {'q': '-visibility:[* TO *]', 'include_private': True, 'rows': 1000}
    search_url = '{}/api/action/package_search?{}'.format(
        url.rstrip('/'), urlencode(params))
    query = _get_json(search_url, api_key)
    count = query['result']['count']

    if count == 0:
        print('No datasets without an existing "visibility" flag were found.\n'
              'If you have private datasets that need to be converted, \n'
              'make sure you are using a sysadmin API key.')
        sys.exit(0)

    datasets = query['result']['results']

    patch_url = '{}/api/action/package_patch'.format(url)

    cnt = 0
    errors = []
    for dataset in datasets:
        data = {'id': dataset['id'],
                'private': False,
                'visibility': 'restricted' if dataset['private'] else 'public'}

        result = _post_json(patch_url, data, api_key)
        if not result['success']:
            if result['error'].get('notes') == ['Missing value']:
                # Try again with some default description
                data['notes'] = 'Please change me'
                result = _post_json(patch_url, data, api_key)
            if not result['success']:
                print('Error updating dataset "{}"'.format(dataset['name']))
                errors.append((dataset['name'], result['error']))
                continue
        assert result['result']['private'] == False

        print('Updated dataset "{}"'.format(result['result']['title']))
        cnt += 1

    print('Done. Updated {} datasets'.format(cnt))
    if errors:
        print('The following datasets could not be updated:\n\n')
        for error in errors:
            print('{}: {}'.format(error[0], error[1]))


# Internal

def _get_json(url, api_key):
    try:
        res = requests.get(url, headers={'Authorization': api_key})
        return res.json()
    except requests.HTTPError as e:
        print('HTTP Error ({}): {}'.format(e, url))
        sys.exit(1)


def _post_json(url, data, api_key):
    try:
        res = requests.post(url, json=data, headers={'Authorization': api_key})
        return res.json()
    except requests.HTTPError as e:
        print('HTTP Error ({}): {}'.format(e, url))
        sys.exit(1)


# Main

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Migrate private datasets to the restricted model (public metadada / private downloads)')
    parser.add_argument('url', help='URL for the CKAN site to update')
    parser.add_argument('api_key', help='Sysadmin API key on that site')

    args = parser.parse_args()
    update_datasets(args.url, args.api_key)
