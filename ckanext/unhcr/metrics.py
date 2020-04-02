# -*- coding: utf-8 -*-

from operator import itemgetter
from slugify import slugify
from sqlalchemy import select
import ckan.model as model
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr.models import TimeSeriesMetric


def get_datasets_by_date(context):
    title = 'Total number of Datasets'
    data_dict = {
        'q': '*:*',
        'fq': "-type:deposited-dataset",
        'rows': 0,
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(context, data_dict)

    sql = select([TimeSeriesMetric])
    result = model.Session.execute(sql).fetchall()

    return {
        'type': 'timeseries_graph',
        'short_title': 'Datasets',
        'title': title,
        'id': slugify(title),
        'total': packages['count'],
        'data': [
            ['x'] + [str(row['timestamp']) for row in result],
            ['Datasets'] + [row['datasets_count'] for row in result],
        ],
    }


def get_containers(context):
    data_dict = {
        'q': '*:*',
        'fq': "-type:deposited-dataset",
        'rows': 0,
        'facet.field': ['organization'],
        'facet.limit': 10,
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(context, data_dict)

    organizations = toolkit.get_action('organization_list')(
        context,
        { 'type': 'data-container' }
    )

    data = sorted(
        packages['search_facets']['organization']['items'],
        key=itemgetter('count'),
        reverse=True,
    )
    for row in data:
        row['link'] = toolkit.url_for('data-container_read', id=row['name'])

    title = 'Data Containers'
    return {
        'type': 'freq_table',
        'title': title,
        'id': slugify(title),
        'total': len(organizations),
        'headers': ['Data Container', 'Datasets'],
        'data': data,
    }

def get_tags(context):
    data_dict = {
        'q': '*:*',
        'fq': "-type:deposited-dataset",
        'rows': 0,
        'facet.field': ['tags'],
        'facet.limit': 10,
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(context, data_dict)

    data = sorted(
        packages['search_facets']['tags']['items'],
        key=itemgetter('count'),
        reverse=True,
    )
    for row in data:
        row['link'] = toolkit.url_for('dataset', tags=row['name'])

    title = 'Tags'
    return {
        'type': 'freq_table',
        'title': title,
        'id': slugify(title),
        'headers': ['Tag', 'Datasets'],
        'data': data,
    }

def get_users(context):
    users = toolkit.get_action('user_list')(context, {})
    users = sorted(
        users,
        key=itemgetter('number_created_packages'),
        reverse=True,
    )

    title = 'Users'
    return {
        'type': 'freq_table',
        'title': title,
        'id': slugify(title),
        'total': len(users),
        'headers': ['User', 'Datasets Created'],
        'data': [
            {
                'display_name': user['display_name'],
                'count': user['number_created_packages'],
                'link': toolkit.url_for('user.read', id=user['id']),
            }
            for user in users[:10]
        ]
    }
