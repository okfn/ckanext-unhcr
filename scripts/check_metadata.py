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


def _fix_file_type(datasets):
    update = []
    for dataset in datasets:
        for resource in dataset.get('resources', []):
            if not resource.get('file_type'):

                file_type = 'other'
                if 'report' in resource.get('name', '').lower():
                    file_type = 'report'
                if 'questionnaire' in resource.get('name', '').lower():
                    file_type = 'questionnaire'

                resource['file_type'] = file_type
                if dataset['id'] not in update:
                    update.append(dataset['id'])
            elif resource['file_type'] == 'sampling_methodo':
                resource['file_type'] = 'sampling_methodology'
                if dataset['id'] not in update:
                    update.append(dataset['id'])
    return update


def _fix_broken_urls(datasets, url, api_key):
    update = []
    for dataset in datasets:
        for resource in dataset.get('resources', []):
            if resource.get('url_type') != 'upload':
                params = {'id': dataset['creator_user_id']}
                user_url = '{}/api/action/user_show?{}'.format(url.rstrip('/'), urlencode(params))
                user = _get_json(user_url, api_key)['result']

                if not resource['url']:
                    print('Missing URL,"{}","{}","{}",{},"{}",{},{},{}'.format(user['fullname'], user['email'],dataset['title'].encode('utf8'),resource['package_id'],'https://ridl.unhcr.org/dataset/{}'.format(dataset['name']),resource['name'].encode('utf8'),resource['id'],'https://ridl.unhcr.org/dataset/{}/resource/{}'.format(dataset['name'], resource['id']) ))
		elif resource.get('url_type') is None and resource['url'].startswith('http:'):
                    print('Wrong URL,"{}","{}","{}",{},"{}",{},{},{}'.format(user['fullname'], user['email'],dataset['title'].encode('utf8'),resource['package_id'],'https://ridl.unhcr.org/dataset/{}'.format(dataset['name']),resource['name'].encode('utf8'),resource['id'],'https://ridl.unhcr.org/dataset/{}/resource/{}'.format(dataset['name'], resource['id']) ))
                    #resource['url_type'] = 'upload'
                    #resource['url'] = resource['url'].replace('http://', '')
                    #update.append(dataset['id'])
    return update


def update_datasets(url, api_key, action):

    params = {'q': '*:*', 'fq': 'dataset_type:dataset','include_private': True, 'rows': 1000}
    search_url = '{}/api/action/package_search?{}'.format(
        url.rstrip('/'), urlencode(params))
    query = _get_json(search_url, api_key)
    count = query['result']['count']
    datasets = query['result']['results']
    cnt = 0
    update = []
    errors = []

    if action == 'fix_file_type':
        update = _fix_file_type(datasets)
    elif action == 'fix_broken_urls':
        update = _fix_broken_urls(datasets, url, api_key)
    else:
        print('Unknown action: {}'.format(action))
        sys.exit(1)

    update_url = '{}/api/action/package_update'.format(url)

    for dataset in datasets:
        if dataset['id'] in update:
            result = _post_json(update_url, dataset, api_key)
            if not result['success']:
                print('Error updating dataset "{}"'.format(dataset['name']))
                errors.append((dataset['name'], result['error']))
                continue

            print('Updated dataset "{}"'.format(result['result']['title'].decode('utf8')))
            cnt += 1

    print('Done. Updated {} datasets'.format(cnt))
    if errors:
        print('The following datasets could not be updated:\n\n')
        for error in errors:
            print('{}: {}'.format(error[0], error[1]))






# Internal

def _get_json(url, api_key):
    try:
        res = requests.get(url, headers={'Authorization': api_key}, verify=False)
        return res.json()
    except requests.HTTPError as e:
        print('HTTP Error ({}): {}'.format(e, url))
        sys.exit(1)


def _post_json(url, data, api_key):
    try:
        res = requests.post(url, json=data, headers={'Authorization': api_key}, verify=False)
        return res.json()
    except requests.HTTPError as e:
        print('HTTP Error ({}): {}'.format(e, url))
        sys.exit(1)


# Main

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='Migrate private datasets to the restricted model (public metadada / private downloads)')
    parser.add_argument('url', help='URL for the CKAN site to update')
    parser.add_argument('api_key', help='Sysadmin API key on that site')
    parser.add_argument('action', help='Action to perform. Available actions are fix_file_type, fix_broken_urls')

    args = parser.parse_args()
    update_datasets(args.url, args.api_key, args.action)
