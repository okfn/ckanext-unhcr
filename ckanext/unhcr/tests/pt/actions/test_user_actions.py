# -*- coding: utf-8 -*-

import pytest
from ckan import model
from ckan.plugins import toolkit
from ckan.tests.helpers import call_action
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestUserActions(object):

    def test_user_create_no_duplicate_emails(self):
        user1 = core_factories.User(email='alice@unhcr.org')

        with pytest.raises(toolkit.ValidationError) as e:
            call_action(
                'user_create',
                {},
                email='alice@unhcr.org',
                name='alice',
                password='8charactersorlonger',
            )

        assert (
            e.value.error_dict['email'][0] ==
            "The email address 'alice@unhcr.org' already belongs to a registered user."
        )

        call_action(
            'user_create',
            {},
            email='bob@unhcr.org',
            name='bob',
            password='8charactersorlonger',
        )

    def test_user_list(self):
        sysadmin = core_factories.Sysadmin()
        external_user = factories.ExternalUser()
        internal_user = core_factories.User()
        default_user = toolkit.get_action('get_site_user')({ 'ignore_auth': True })

        action = toolkit.get_action('user_list')
        context = {'user': sysadmin['name']}
        users = action(context, {})
        assert (1 == len(
            [
                u for u in users
                if u['external']
                and u['name'] != default_user['name']
            ])
        )
        assert (2 == len(
            [
                u for u in users
                if not u['external']
                and u['name'] != default_user['name']
            ])
        )

    def test_user_show(self):
        sysadmin = core_factories.Sysadmin()
        external_user = factories.ExternalUser()
        internal_user = core_factories.User()

        action = toolkit.get_action('user_show')
        context = {'user': sysadmin['name']}
        assert action(context, {'id': external_user['id']})['external']
        assert not action(context, {'id': internal_user['id']})['external']

    def test_unhcr_plugin_extras_empty(self):
        user = core_factories.User()
        context = {'user': user['name']}
        user = toolkit.get_action('user_show')(context, {'id': user['id']})
        assert None is user['expiry_date']
        assert '' == user['focal_point']

    def test_unhcr_plugin_extras_with_data(self):
        user = factories.ExternalUser(focal_point='Alice')
        context = {'user': user['name']}
        user = toolkit.get_action('user_show')(context, {'id': user['id']})
        assert 'expiry_date' in user
        assert 'Alice' == user['focal_point']


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestUserAutocomplete(object):

    def test_user_autocomplete(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        factories.ExternalUser(
            fullname='Alice External',
            email='alice@externaluser.com',
        )
        core_factories.User(fullname='Bob Internal')
        core_factories.User(fullname='Carlos Internal')
        core_factories.User(fullname='David Internal')

        action = toolkit.get_action('user_autocomplete')
        context = {'user': sysadmin['name']}

        result = action(context, {'q': 'alic'})
        assert 0 == len(result)

        result = action(context, {'q': 'alic', 'include_external': True})
        assert 'Alice External' == result[0]['fullname']

        result = action(context, {'q': 'nal'})
        fullnames = [r['fullname'] for r in result]
        assert 'Bob Internal' in fullnames
        assert 'Carlos Internal' in fullnames
        assert 'David Internal' in fullnames

        result = action(context, {'q': 'foobar'})
        assert 0 == len(result)


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestUpdateSysadmin(object):

    def test_sysadmin_not_authorized(self):
        user1 = core_factories.User()
        user2 = core_factories.User()
        action = toolkit.get_action("user_update_sysadmin")
        with pytest.raises(toolkit.NotAuthorized):
            action(
                {"user": user1["name"]},
                {'id': user1["name"], 'is_sysadmin': True}
            )
        with pytest.raises(toolkit.NotAuthorized):
            action(
                {"user": user2["name"]},
                {'id': user1["name"], 'is_sysadmin': True}
            )

    def test_sysadmin_invalid_user(self):
        user = core_factories.Sysadmin()
        action = toolkit.get_action("user_update_sysadmin")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
                {"user": user["name"]},
                {'id': "fred", 'is_sysadmin': True}
            )

    def test_sysadmin_promote_success(self):
        admin = core_factories.Sysadmin()

        # create a normal user
        user = core_factories.User()

        # promote them
        action = toolkit.get_action("user_update_sysadmin")
        action({'user': admin['name']}, {'id': user['name'], 'is_sysadmin': True})

        # now they are a sysadmin
        userobj = model.User.get(user['id'])
        assert True == userobj.sysadmin

    def test_sysadmin_revoke_success(self):
        admin = core_factories.Sysadmin()

        # create another sysadmin
        user = core_factories.Sysadmin(fullname='Bob')

        # revoke their status
        action = toolkit.get_action("user_update_sysadmin")
        action({'user': admin['name']}, {'id': user['name'], 'is_sysadmin': False})

        # now they are not a sysadmin any more
        userobj = model.User.get(user['id'])
        assert False == userobj.sysadmin


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestExternalUserUpdateState(object):

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
        with pytest.raises(toolkit.NotAuthorized):
            action(
                {"user": self.container1_admin["name"]},
                {'id': target_user['id'], 'state': model.State.ACTIVE}
            )

    def test_target_user_is_not_pending(self):
        target_user = factories.ExternalUser()
        action = toolkit.get_action("external_user_update_state")
        with pytest.raises(toolkit.NotAuthorized):
            action(
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
        with pytest.raises(toolkit.NotAuthorized):
            action(
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
        with pytest.raises(toolkit.NotAuthorized):
            action(
                {"user": requesting_user["name"]},
                {'id': target_user['id'], 'state': model.State.ACTIVE}
            )

    def test_no_access_request(self):
        target_user = factories.ExternalUser(state=model.State.PENDING)
        action = toolkit.get_action("external_user_update_state")
        with pytest.raises(toolkit.NotAuthorized):
            action(
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
        with pytest.raises(toolkit.ValidationError):
            action(
                {"user": self.container1_admin["name"]},
                {'id': target_user['id'], 'state': 'foobar'}
            )

    def test_user_not_found(self):
        action = toolkit.get_action("external_user_update_state")
        with pytest.raises(toolkit.ObjectNotFound):
            action(
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
        assert model.State.ACTIVE == user['state']
