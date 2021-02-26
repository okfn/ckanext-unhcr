import mock
import pytest

from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.tests import factories as core_factories
from ckan.tests.helpers import call_action, call_auth
from ckanext.unhcr.tests import factories


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
