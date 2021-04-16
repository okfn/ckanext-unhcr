# -*- coding: utf-8 -*-

import pytest
from ckan import model
from ckan.plugins import toolkit
import ckan.lib.navl.dictization_functions as df
from ckan.tests.helpers import call_action
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories
from ckanext.unhcr import validators


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestDataDepositValidators(object):

    def test_deposited_dataset_owner_org(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        result = validators.deposited_dataset_owner_org('data-deposit', {})
        assert result == 'data-deposit'

    def test_deposited_dataset_owner_org_invalid(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        assert(
            toolkit.Invalid ==
            validators.deposited_dataset_owner_org, 'data-target', {}
        )

    def test_deposited_dataset_owner_org_dest(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        user = core_factories.User()
        result = validators.deposited_dataset_owner_org_dest(
            'data-target',
            {'user': user['name']}
        )
        assert result == 'data-target'

    def test_deposited_dataset_owner_org_dest_invalid_data_deposit(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        user = core_factories.User()
        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_owner_org_dest(
                'data-deposit',
                {'user': user['name']}
            )

    def test_deposited_dataset_owner_org_dest_invalid_not_existent(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target')
        user = core_factories.User()
        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_owner_org_dest(
                'not-existent',
                {'user': user['name']}
            )

    def test_deposited_dataset_owner_org_dest_not_visible_external(self):
        deposit = factories.DataContainer(id='data-deposit')
        target = factories.DataContainer(id='data-target', visible_external=False)
        internal_user = core_factories.User()
        external_user = factories.ExternalUser()

        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_owner_org_dest(
                'data-target',
                {'user': external_user['name']}
            )

        assert (
            validators.deposited_dataset_owner_org_dest(
                "data-target",
                {"user": internal_user["name"]},
            )
            == "data-target"
        )

    def test_deposited_dataset_curation_state(self):
        assert validators.deposited_dataset_curation_state('draft', {}) == 'draft'
        assert validators.deposited_dataset_curation_state('submitted', {}) == 'submitted'
        assert validators.deposited_dataset_curation_state('review', {}) == 'review'

    def test_deposited_dataset_curation_state_invalid(self):
        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_curation_state( 'invalid', {})


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestPrivateDatasetValidators(object):


    def test_always_false_if_not_sysadmin(self):
        normal_user = core_factories.User()
        sysadmin_user = core_factories.Sysadmin()

        tests = [
            # User, value provided, value expected
            (normal_user['name'], True, False),
            (normal_user['name'], False, False),
            (normal_user['name'], None, False),
            (sysadmin_user['name'], False, False),
            (sysadmin_user['name'], True, True),
            (sysadmin_user['name'], None, False),
        ]

        for test in tests:
            returned = validators.always_false_if_not_sysadmin(
                test[1], {'user': test[0]})

            assert (
                returned == test[2]
            ), "User: {}, provided: {}, expected: {}, returned: {}".format(
                test[0], test[1], test[2], returned
            )

    def test_visibility_validator_restricted_false(self):
        tests = [
            ({'private': True, 'visibility': 'private'}, True),
            ({'private': False, 'visibility': 'private'}, True),
            ({'private': True, 'visibility': 'restricted'}, False),
            ({'private': False, 'visibility': 'restricted'}, False),
            ({'private': True, 'visibility': 'public'}, False),
            ({'private': False, 'visibility': 'public'}, False),
        ]

        for test in tests:
            key = ('visibility',)
            data = df.flatten_dict(test[0])
            validators.visibility_validator(key, data, {}, {})
            assert (
                data[('private',)] == test[1]
            ), 'Data: {}, expected: {}, returned: {}'.format(
                test[0], test[1], data[('private',)]
            )

    def test_visibility_validator_invalid_value(self):
        key = ('visibility',)
        data = {'private': True, 'visibility': 'unknown'}
        data = df.flatten_dict(data)
        with pytest.raises(toolkit.Invalid):
            validators.visibility_validator(key, data, {}, {})

    def test_visibility_validator_set_correct_value(self):
        tests = [
            ({'visibility': 'private'}, 'restricted'),
            ({'visibility': 'restricted'}, 'restricted'),
            ({'visibility': 'public'}, 'public'),
        ]

        for test in tests:
            key = ('visibility',)
            data = df.flatten_dict(test[0])
            validators.visibility_validator(key, data, {}, {})
            assert(
                data[('visibility',)] == test[1]
            ), 'Data: {}, expected: {}, returned: {}'.format(
                test[0], test[1], data[('private',)]
            )


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestOwnerOrgValidator(object):

    def test_owner_org_validator_org_member_save_to_owner_org(self):
        container_member = core_factories.User()
        data_container = factories.DataContainer(
            users=[{'name': container_member['name'], 'capacity': 'admin'}]
        )
        dataset = factories.Dataset(
            owner_org=data_container['id'],
            visibility='private'
        )

        context = {
            'user': container_member['name'],
            'package': model.package.Package.get(dataset['id']),
            'model': model,
        }
        data = {
            'owner_org': data_container['id']
        }

        result = validators.owner_org_validator('owner_org', data, {}, context)

        # container_member should be allowed to save dataset in data_container
        assert None == result

    def test_owner_org_validator_org_member_move_dataset(self):
        user = core_factories.User()
        data_container1 = factories.DataContainer(
            users=[{'name': user['name'], 'capacity': 'admin'}]
        )
        data_container2 = factories.DataContainer(
            users=[{'name': user['name'], 'capacity': 'admin'}]
        )
        data_container3 = factories.DataContainer()
        dataset = factories.Dataset(
            owner_org=data_container1['id'],
            visibility='private'
        )

        context = {
            'user': user['name'],
            'package': model.package.Package.get(dataset['id']),
            'model': model,
        }

        # user should be allowed to move dataset from data_container1 to
        # data_container2 because they are in both groups
        assert None == validators.owner_org_validator(
            'owner_org', {'owner_org': data_container2['id']}, {}, context
        )
        # ..but not data_container3, because they are not in that one
        with pytest.raises(toolkit.Invalid):
            validators.owner_org_validator(
                'owner_org', {'owner_org': data_container3['id']}, {}, context
            )

    def test_owner_org_validator_dataset_collaborator_can_save_to_owner_org(self):
        user = core_factories.User()
        data_container = factories.DataContainer()
        dataset = factories.Dataset(
            owner_org=data_container['id'],
            visibility='private'
        )
        call_action(
            'package_collaborator_create',
            id=dataset['id'],
            user_id=user['id'],
            capacity='member',
        )

        context = {
            'user': user['name'],
            'package': model.package.Package.get(dataset['id']),
            'model': model,
        }
        data = {
            'owner_org': data_container['id']
        }

        result = validators.owner_org_validator('owner_org', data, {}, context)

        # user should be allowed to save dataset in data_container even though
        # they are not a member of it because they are a collborator on dataset
        assert None == result

    def test_owner_org_validator_dataset_collaborator_move_dataset(self):
        user = core_factories.User()
        data_container1 = factories.DataContainer()
        data_container2 = factories.DataContainer(
            users=[{'name': user['name'], 'capacity': 'admin'}]
        )
        data_container3 = factories.DataContainer()
        dataset = factories.Dataset(
            owner_org=data_container1['id'],
            visibility='private'
        )
        call_action(
            'package_collaborator_create',
            id=dataset['id'],
            user_id=user['id'],
            capacity='member',
        )

        context = {
            'user': user['name'],
            'package': model.package.Package.get(dataset['id']),
            'model': model,
        }

        # user should not be allowed to move dataset to another container
        # regardless of whether they are a member of the target container
        for container in [data_container2, data_container3]:
            with pytest.raises(toolkit.Invalid):
                validators.owner_org_validator(
                    'owner_org',
                    {'owner_org': container['id']},
                    {},
                    context,
                )


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestDepositedDatasetCurationIdValidator(object):

    def setup(self):
        self.depadmin = core_factories.User()
        self.curator = core_factories.User()
        self.target_container_admin = core_factories.User()
        self.target_container_member = core_factories.User()
        self.other_container_admin = core_factories.User()

        deposit = factories.DataContainer(
            id='data-deposit',
            users=[
                {'name': self.depadmin['name'], 'capacity': 'admin'},
                {'name': self.curator['name'], 'capacity': 'editor'},
            ]
        )
        target = factories.DataContainer(
            users=[
                {'name': self.target_container_admin['name'], 'capacity': 'admin'},
                {'name': self.target_container_member['name'], 'capacity': 'member'},
            ]
        )
        container = factories.DataContainer(
            users=[
                {'name': self.other_container_admin['name'], 'capacity': 'admin'},
            ]
        )

        dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id']
        )
        self.package = model.Package.get(dataset['id'])

    def test_deposited_dataset_curation_id_no_package_in_context_valid(self):
        assert (
            self.depadmin['name'] ==
            validators.deposited_dataset_curator_id(self.depadmin['name'], {})
        )
        assert (
            self.curator['name'] ==
            validators.deposited_dataset_curator_id(self.curator['name'], {})
        )

    def test_deposited_dataset_curation_id_no_package_in_context_invalid(self):
        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_curator_id(
                self.target_container_admin['name'],
                {},
            )
        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_curator_id(
                self.target_container_member['name'],
                {},
            )
        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_curator_id(
                self.other_container_admin['name'],
                {},
            )

    def test_deposited_dataset_curation_id_with_package_in_context_valid(self):
        context = {'package': self.package, 'user': self.depadmin['name']}

        assert (
            self.depadmin['name'] ==
            validators.deposited_dataset_curator_id(self.depadmin['name'], context)
        )
        assert (
            self.curator['name'] ==
            validators.deposited_dataset_curator_id(self.curator['name'], context)
        )
        assert (
            self.target_container_admin['name'] ==
            validators.deposited_dataset_curator_id(self.target_container_admin['name'], context)
        )

    def test_deposited_dataset_curation_id_with_package_in_context_invalid(self):
        context = {'package': self.package, 'user': self.depadmin['name']}

        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_curator_id(
                self.target_container_member['name'],
                context,
            )
        with pytest.raises(toolkit.Invalid):
            validators.deposited_dataset_curator_id(
                self.other_container_admin['name'],
                context,
            )
