import datetime
import json
import mock
import re
import responses
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers, factories as core_factories
from nose.tools import assert_raises, assert_equals, assert_true, assert_false, nottest
from ckanext.unhcr.tests import base, factories, mocks
from ckanext.unhcr import helpers
from ckanext.unhcr.activity import log_download_activity

assert_in = core_helpers.assert_in


class TestExternalUserUpdateState(base.FunctionalTestBase):

    def setup(self):
        self.container1_admin = core_factories.User()
        self.container1 = factories.DataContainer(
            users=[{"name": self.container1_admin["name"], "capacity": "admin"}]
        )

    def test_target_user_is_internal(self):
        target_user = core_factories.User(
            state=model.State.PENDING,
        )
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_target_user_is_not_pending(self):
        target_user = factories.ExternalUser()
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_requesting_user_is_not_container_admin(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )
        requesting_user = core_factories.User()

        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": requesting_user["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_requesting_user_is_not_admin_of_required_container(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        requesting_user = core_factories.User()
        container2 = factories.DataContainer(
            users=[{"name": requesting_user["name"], "capacity": "admin"}]
        )
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )

        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": requesting_user["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_no_access_request(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.NotAuthorized,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

    def test_invalid_state(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )

        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.ValidationError,
            action,
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': 'foobar'}
        )

    def test_user_not_found(self):
        action = toolkit.get_action("external_user_update_state")
        assert_raises(
            toolkit.ObjectNotFound,
            action,
            {"user": self.container1_admin["name"]},
            {'id': 'does-not-exist', 'state': model.State.ACTIVE}
        )

    def test_success(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        access_request_data_dict = {
            'object_id': target_user['id'],
            'object_type': 'user',
            'message': 'asdf',
            'role': 'member',
            'data': {'default_containers': [self.container1['id']]}
        }
        toolkit.get_action(u'access_request_create')(
            {'user': target_user['id'], 'ignore_auth': True},
            access_request_data_dict
        )

        action = toolkit.get_action("external_user_update_state")
        action(
            {"user": self.container1_admin["name"]},
            {'id': target_user['id'], 'state': model.State.ACTIVE}
        )

        user = toolkit.get_action("user_show")(
            {"ignore_auth": True}, {"id": target_user['id']}
        )
        assert_equals(model.State.ACTIVE, user['state'])
