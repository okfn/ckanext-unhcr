import datetime
from ckan.plugins import toolkit
from ckan.tests import factories as core_factories
from nose.plugins.attrib import attr
from nose.tools import assert_raises, assert_equals
from ckanext.unhcr.tests import base, factories
from ckanext.unhcr import utils


class TestUtils(base.FunctionalTestBase):

    # Misc

    def test_normalize_list(self):
        value = ['name1', 'name2']
        assert_equals(utils.normalize_list(value), value)
        assert_equals(utils.normalize_list('{name1,name2}'), value)
        assert_equals(utils.normalize_list(''), [])

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
            {'ignore_auth': True},
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
            {'ignore_auth': True},
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
