# -*- coding: utf-8 -*-

import datetime
import pytest
from ckan.plugins import toolkit
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories
from ckanext.unhcr import utils


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestUtils(object):

    def test_normalize_list(self):
        value = ['name1', 'name2']
        assert utils.normalize_list(value) == value
        assert utils.normalize_list('{name1,name2}') == value
        assert utils.normalize_list('') == []

    def test_resource_is_blocked_no_task_status(self):
        user = core_factories.User()
        dataset = factories.Dataset()
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )

        assert not utils.resource_is_blocked(
            {'user': user['name']},
            resource['id']
        )

    def test_resource_is_blocked_task_status_ok(self):
        user = core_factories.User()
        dataset = factories.Dataset()
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )
        toolkit.get_action('task_status_update')(
            {
                'ignore_auth': True,
                # task_status_update wants a user object
                # for no reason, even with 'ignore_auth': True
                # give it an empty string to keep it happy
                'user': ''
            },
            {
                'entity_id': resource['id'],
                'entity_type': 'resource',
                'task_type': 'clamav',
                'last_updated': str(datetime.datetime.utcnow()),
                'state': 'complete',
                'key': 'clamav',
                'value': '{"data": {"status_code": 0}}',
                'error': 'null',
            }
        )

        assert not utils.resource_is_blocked(
            {'user': user['name']},
            resource['id']
        )

    def test_resource_is_blocked_task_status_infected(self):
        user = core_factories.User()
        dataset = factories.Dataset()
        resource = factories.Resource(
            package_id=dataset['id'],
            url_type='upload',
        )
        toolkit.get_action('task_status_update')(
            {
                'ignore_auth': True,
                # task_status_update wants a user object
                # for no reason, even with 'ignore_auth': True
                # give it an empty string to keep it happy
                'user': ''
            },
            {
                'entity_id': resource['id'],
                'entity_type': 'resource',
                'task_type': 'clamav',
                'last_updated': str(datetime.datetime.utcnow()),
                'state': 'complete',
                'key': 'clamav',
                'value': '{"data": {"status_code": 1}}',
                'error': 'null',
            }
        )

        assert utils.resource_is_blocked(
            {'user': user['name']},
            resource['id']
        )
