# -*- coding: utf-8 -*-

from operator import itemgetter
from slugify import slugify
from sqlalchemy import select, func, desc
import ckan.model as model
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr.models import TimeSeriesMetric


def _get_timeseries_metric(field):
    sql = select([
        func.date(TimeSeriesMetric.timestamp).label('date'),
        getattr(TimeSeriesMetric, field)
    ]).order_by(
        TimeSeriesMetric.timestamp
    )
    result = model.Session.execute(sql).fetchall()
    dates = {}
    for row in result:
        # De-dupe on date. As long as we've ordered our query by timestamp,
        # we'll take the last value recorded on each date
        dates[row['date']] = row[field]
    return dates


def get_datasets_by_date(context):
    title = 'Total number of Datasets'
    data_dict = {
        'q': '*:*',
        'fq': "-type:deposited-dataset",
        'rows': 0,
        'include_private': True,
    }
    packages = toolkit.get_action('package_search')(context, data_dict)
    dates = _get_timeseries_metric('datasets_count')

    return {
        'type': 'timeseries_graph',
        'short_title': 'Datasets',
        'title': title,
        'id': slugify(title),
        'total': packages['count'],
        'data': [
            ['x'] + [str(date) for date in dates.keys()],
            ['Datasets'] + [count for count in dates.values()],
        ],
    }

def get_datasets_by_downloads(context):
    activity_table = model.meta.metadata.tables['activity']
    resource_table = model.meta.metadata.tables['resource']
    package_table = model.meta.metadata.tables['package']
    join_obj = activity_table.join(
        resource_table, resource_table.c.id==activity_table.c.object_id
    ).join(
        package_table, package_table.c.id==resource_table.c.package_id
    )

    sql = select([
        model.Package, func.count(model.Package.id).label('count')
    ]).select_from(
        join_obj
    ).where(
        model.Activity.activity_type == 'download resource'
    ).group_by(
        model.Package.id
    ).order_by(
        desc('count')
    ).limit(10)

    result = model.Session.execute(sql).fetchall()

    data = []
    for row in result:
        data.append({
            'display_name': row['title'],
            'link': toolkit.url_for('dataset_read', id=row['name']),
            'count': row['count'],
        })

    title = 'Datasets (by downloads)'
    return {
        'type': 'freq_table',
        'title': title,
        'id': slugify(title),
        'headers': ['Dataset', 'Downloads'],
        'data': data,
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
        'headers': ['Data Container', 'Datasets'],
        'data': data,
    }

def get_containers_by_date(context):
    title = 'Total number of Containers'
    dates = _get_timeseries_metric('containers_count')

    return {
        'type': 'timeseries_graph',
        'short_title': 'Containers',
        'title': title,
        'total': dates.values()[-1],
        'id': slugify(title),
        'data': [
            ['x'] + [str(date) for date in dates.keys()],
            ['Datasets'] + [count for count in dates.values()],
        ],
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

    title = 'Users (by datasets created)'
    return {
        'type': 'freq_table',
        'short_title': 'Users',
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

def get_users_by_downloads(context):
    activity_table = model.meta.metadata.tables['activity']
    user_table = model.meta.metadata.tables['user']
    join_obj = activity_table.join(
        user_table, user_table.c.id==activity_table.c.user_id
    )

    sql = select([
        model.User, func.count(model.User.id).label('count')
    ]).select_from(
        join_obj
    ).where(
        model.Activity.activity_type == 'download resource'
    ).group_by(
        model.User.id
    ).order_by(
        desc('count')
    ).limit(10)

    result = model.Session.execute(sql).fetchall()

    data = []
    for row in result:
        data.append({
            'display_name': row['fullname'] if row['fullname'] else row['name'],
            'count': row['count'],
            'link': toolkit.url_for('user.read', id=row['id']),
        })

    title = 'Users (by downloads)'
    return {
        'type': 'freq_table',
        'title': title,
        'id': slugify(title),
        'headers': ['User', 'Downloads'],
        'data': data,
    }
