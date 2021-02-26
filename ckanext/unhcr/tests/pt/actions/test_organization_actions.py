# -*- coding: utf-8 -*-

import pytest
from ckan.plugins import toolkit
from ckan.tests.helpers import call_action
from ckantoolkit.tests import factories as core_factories
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


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestOrganizationMemberCreate(object):

    def test_internal_user(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        internal_user = core_factories.User()
        container = factories.DataContainer()

        toolkit.get_action("organization_member_create")(
            {'user': sysadmin['name']},
            {
                'id': container['id'],
                'username': internal_user['name'],
                'role': 'member',
            }
        )

        org_list = toolkit.get_action("organization_list_for_user")(
            {'user': sysadmin['name']},
            {'id': internal_user['id']}
        )
        assert container['id'] == org_list[0]['id']
        assert 'member' == org_list[0]['capacity']

    def test_external_user(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        external_user = factories.ExternalUser()
        container = factories.DataContainer()

        action = toolkit.get_action("organization_member_create")
        with pytest.raises(toolkit.ValidationError):
            action(
                {'user': sysadmin['name']},
                {
                    'id': container['id'],
                    'username': external_user['name'],
                    'role': 'member',
                }
            )
