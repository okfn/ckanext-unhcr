# -*- coding: utf-8 -*-

import pytest
from ckan.plugins import toolkit
from ckan.tests.helpers import call_action
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestOrganizationActions(object):
    def setup(self):
        factories.DataContainer(name='za', title='South Africa')
        factories.DataContainer(name='so', title='Somalia')
        factories.DataContainer(name='tz', title='Tanzania')
        factories.DataContainer(name='cg', title='Congo', state='deleted')

    def test_organization_list_organization_list_all_fields_no_params(self):
        orgs = call_action(
            'organization_list_all_fields',
            {'ignore_auth': True},
        )
        assert len(orgs) == 3
        assert [org['name'] for org in orgs] == ['so', 'za', 'tz']
        for org in orgs:
            assert 'country' in org
            assert type(org['country']) == list
            assert 'visible_external' in org
            assert type(org['visible_external']) == bool
            assert org['display_name'] == org['title']

    def test_organization_list_organization_list_all_fields_order_by_valid(self):
        orgs = call_action(
            'organization_list_all_fields',
            {'ignore_auth': True},
            **{'order_by': 'name'}
        )
        assert [org['name'] for org in orgs] == ['so', 'tz', 'za']

    def test_organization_list_organization_list_all_fields_order_by_invalid(self):
        with pytest.raises(toolkit.Invalid) as e:
            call_action(
                'organization_list_all_fields',
                {'ignore_auth': True},
                **{'order_by': 'foobar'}
            )
