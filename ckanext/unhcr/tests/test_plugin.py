import mock

import pylons
from paste.registry import Registry
from nose.plugins.attrib import attr

from ckan import model
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr.tests import base, factories
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals
from ckan.tests.helpers import call_action, call_auth


# Tests

class TestRequestDataContainer(base.FunctionalTestBase):

    @classmethod
    def setup_class(cls):

        # Hack because the hierarchy extension uses c in some methods
        # that are called outside the context of a web request
        c = pylons.util.AttribSafeContextObj()
        registry = Registry()
        registry.prepare()
        registry.register(pylons.c, c)

        super(TestRequestDataContainer, cls).setup_class()

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_create_data_container_by_sysadmin(self, mock_render_jinja2, mock_mail_user):
        sysadmin = core_factories.Sysadmin()
        context = _create_context(sysadmin)
        org_dict = _create_org_dict(sysadmin)
        call_action('organization_create', context, **org_dict)
        data_container = call_action('organization_show', context, id='data-container')
        assert_equals(data_container['state'], 'active')

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_request_data_container_by_user_approved(self, mock_render_jinja2, mock_mail_user):

        # Request data container
        user = core_factories.User()
        context = _create_context(user)
        org_dict = _create_org_dict(user)
        call_action('organization_create', context, **org_dict)
        data_container = call_action('organization_show', context, id='data-container')
        assert_equals(data_container['state'], 'approval_needed')

        # Approve data container
        app = self._get_test_app()
        sysadmin = core_factories.Sysadmin()
        endpoint = '/data-container/{0}/approve'.format(data_container['id'])
        environ = {'REMOTE_USER': str(sysadmin['name'])}
        response = app.get(endpoint, extra_environ=environ)
        data_container = call_action('organization_show', context, id='data-container')
        assert_equals(data_container['state'], 'active')

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_request_data_container_by_user_rejected(self, mock_render_jinja2, mock_mail_user):

        # Request data container
        user = core_factories.User()
        context = _create_context(user)
        org_dict = _create_org_dict(user)
        call_action('organization_create', context, **org_dict)
        data_container = call_action('organization_show', context, id='data-container')
        assert_equals(data_container['state'], 'approval_needed')

        # Approve data container
        app = self._get_test_app()
        sysadmin = core_factories.Sysadmin()
        endpoint = '/data-container/{0}/reject'.format(data_container['id'])
        environ = {'REMOTE_USER': str(sysadmin['name'])}
        response = app.get(endpoint, extra_environ=environ)
        assert_raises(toolkit.ObjectNotFound, call_action, 'organization_show', context, id='data-container')

    def test_request_data_container_not_allowed_root_parent(self):
        user = core_factories.User()
        context = _create_context(user)
        org_dict = _create_org_dict(user)
        assert_raises(toolkit.NotAuthorized, call_auth, 'organization_create', context, **org_dict)

    def test_request_data_container_not_allowed_not_owned_parent(self):
        user = core_factories.User()
        parent_data_container = factories.DataContainer()
        context = _create_context(user)
        org_dict = _create_org_dict(user, groups=[{'name': parent_data_container['name']}])
        assert_raises(toolkit.NotAuthorized, call_auth, 'organization_create', context, **org_dict)

    def test_request_data_container_allowed_parent(self):
        user = core_factories.User()
        parent_data_container = factories.DataContainer(
            users=[{'capacity': 'admin', 'name': user['name']}])
        context = _create_context(user)
        org_dict = _create_org_dict(user, groups=[{'name': parent_data_container['name']}])
        assert_equals(call_auth('organization_create', context, **org_dict), True)


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
    }
