# -*- coding: utf-8 -*-

import pytest
import mock
from ckan import model
from ckan.plugins import toolkit
from ckan.tests.helpers import call_action, call_auth
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


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestPendingRequestsList(object):

    def test_container_request_list(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        container1 = factories.DataContainer(
            name='container1',
            id='container1',
            state='approval_needed',
        )
        container2 = factories.DataContainer(
            name='container2',
            id='container2',
            state='approval_needed',
        )
        context = {'model': model, 'user': 'sysadmin'}
        requests = toolkit.get_action("container_request_list")(
            context, {'all_fields': False}
        )
        assert requests['count'] == 2
        assert requests['containers'] == [container1['id'], container2['id']]

    def test_container_request_list_all_fields(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        container1 = factories.DataContainer(
            name='container1',
            id='container1',
            state='approval_needed',
        )
        context = {'model': model, 'user': 'sysadmin'}
        requests = toolkit.get_action("container_request_list")(
            context, {'all_fields': True}
        )
        assert requests['count'] == 1
        assert requests['containers'][0]['name'] == 'container1'

    def test_container_request_list_empty(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        context = {'model': model, 'user': 'sysadmin'}
        requests = toolkit.get_action("container_request_list")(
            context, {'all_fields': True}
        )
        assert requests['count'] == 0
        assert requests['containers'] == []

    def test_container_request_list_not_authorized(self):
        user = core_factories.User(name='user', id='user')
        context = {'model': model, 'user': 'user'}
        with pytest.raises(toolkit.NotAuthorized):
            toolkit.get_action("container_request_list")(
                context, {'all_fields': True}
            )


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestRequestDataContainer(object):

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_create_data_container_by_sysadmin(self, mock_render_jinja2, mock_mail_user):
        sysadmin = core_factories.Sysadmin()
        context = _create_context(sysadmin)
        org_dict = _create_org_dict(sysadmin)
        call_action('organization_create', context, **org_dict)
        data_container = call_action('organization_show', context, id='data-container')
        assert data_container['state'] == 'active'

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_request_data_container_by_user_approved(self, mock_render_jinja2, mock_mail_user, app):

        # Request data container
        user = core_factories.User()
        context = _create_context(user)
        org_dict = _create_org_dict(user)
        call_action('organization_create', context, **org_dict)
        data_container = call_action('organization_show', context, id='data-container')
        assert data_container['state'] == 'approval_needed'

        # Approve data container
        sysadmin = core_factories.Sysadmin()
        endpoint = '/data-container/{0}/approve'.format(data_container['id'])
        environ = {'REMOTE_USER': str(sysadmin['name'])}
        response = app.get(endpoint, extra_environ=environ)
        data_container = call_action('organization_show', context, id='data-container')
        assert data_container['state'] == 'active'

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_request_data_container_by_user_rejected(self, mock_render_jinja2, mock_mail_user, app):

        # Request data container
        user = core_factories.User()
        context = _create_context(user)
        org_dict = _create_org_dict(user)
        call_action('organization_create', context, **org_dict)
        data_container = call_action('organization_show', context, id='data-container')
        assert data_container['state'] == 'approval_needed'

        # Approve data container
        sysadmin = core_factories.Sysadmin()
        endpoint = '/data-container/{0}/reject'.format(data_container['id'])
        environ = {'REMOTE_USER': str(sysadmin['name'])}
        response = app.get(endpoint, extra_environ=environ)
        with pytest.raises(toolkit.ObjectNotFound):
            call_action('organization_show', context, id='data-container')

    def test_request_data_container_not_allowed_root_parent(self):
        user = core_factories.User()
        context = _create_context(user)
        org_dict = _create_org_dict(user)
        with pytest.raises(toolkit.NotAuthorized):
            call_auth('organization_create', context, **org_dict)

    def test_request_data_container_not_allowed_not_owned_parent(self):
        user = core_factories.User()
        parent_data_container = factories.DataContainer()
        context = _create_context(user)
        org_dict = _create_org_dict(user, groups=[{'name': parent_data_container['name']}])
        with pytest.raises(toolkit.NotAuthorized):
            call_auth('organization_create', context, **org_dict)

    def test_request_data_container_allowed_parent(self):
        user = core_factories.User()
        parent_data_container = factories.DataContainer(
            users=[{'capacity': 'admin', 'name': user['name']}])
        context = _create_context(user)
        org_dict = _create_org_dict(user, groups=[{'name': parent_data_container['name']}])
        assert call_auth('organization_create', context, **org_dict) == True


# Helpers

def _create_context(user):
    return {'model': model, 'user': user['name']}


def _create_org_dict(user, groups=[]):
    return {
        'status': u'ok',
        'name': u'data-container',
        'title': u'data-container',
        'country': u'RSA',
        'notes': u'',
        'groups': groups,
        'geographic_area': u'southern_africa',
        'users': [{'capacity': 'admin', 'name': user['name']}],
        'save': u'',
        'type': 'data-container',
        'tag_string': u'',
        'population': u'',
        'visible_external': True
    }
