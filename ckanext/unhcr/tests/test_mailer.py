import mock
from nose.plugins.attrib import attr
from ckan import model
from ckanext.unhcr.tests import factories
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals
from ckan.tests.helpers import call_action, FunctionalTestBase
from ckanext.unhcr.mailer import mail_data_container_request_to_sysadmins
from ckanext.unhcr.mailer import mail_data_container_update_to_user
from ckanext.unhcr.tests import base


# Without jinja2 mocking it can't find a template in the test mode
class TestMailer(base.FunctionalTestBase):

    context = {'model': model, 'ignore_auth': True}

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_mail_data_container_request_to_sysadmins(self, mock_render_jinja2, mock_mail_user):
        sysadmin1 = core_factories.Sysadmin()
        sysadmin2 = core_factories.Sysadmin()
        data_container = factories.DataContainer()
        mail_data_container_request_to_sysadmins(self.context, data_container)
        assert_equals(mock_mail_user.call_count, 2)
        assert_equals(mock_render_jinja2.call_args[0][0], 'emails/data_container_request.txt')

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_mail_data_container_update_to_user_on_approval(self, mock_render_jinja2, mock_mail_user):
        user = core_factories.User()
        data_container = factories.DataContainer(users=[user])
        mail_data_container_update_to_user(self.context, data_container, event='approval')
        assert_equals(mock_mail_user.call_count, 1)
        assert_equals(mock_render_jinja2.call_args[0][0], 'emails/data_container_approval.txt')

    @mock.patch('ckanext.unhcr.mailer.mail_user')
    @mock.patch('ckanext.unhcr.mailer.render_jinja2')
    def test_mail_data_container_update_to_user_on_rejection(self, mock_render_jinja2, mock_mail_user):
        user = core_factories.User()
        data_container = factories.DataContainer(users=[user])
        mail_data_container_update_to_user(self.context, data_container, event='rejection')
        assert_equals(mock_mail_user.call_count, 1)
        assert_equals(mock_render_jinja2.call_args[0][0], 'emails/data_container_rejection.txt')
