import os
import nose
import pylons
from ckan import model
from ckan.plugins import toolkit
from paste.registry import Registry
from nose.plugins.attrib import attr
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals, assert_in
from ckan.tests.helpers import call_action
from ckanext.unhcr.helpers import get_linked_datasets_for_form, get_linked_datasets_for_display
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import base, factories
from ckanext.unhcr import helpers


class TestHelpers(base.FunctionalTestBase):

    # Pending Requests

    def test_get_pending_requests_total(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        pending_container1 = factories.DataContainer(
            name='container1',
            id='container1',
            state='approval_needed',
        )
        pending_container2 = factories.DataContainer(
            name='container2',
            id='container2',
            state='approval_needed',
        )
        container3 = factories.DataContainer()
        dataset1 = factories.Dataset(
            owner_org=container3["id"], visibility="private"
        )
        requesting_user = core_factories.User()
        model.Session.add(
            AccessRequest(
                user_id=requesting_user["id"],
                object_id=container3["id"],
                object_type="organization",
                message="",
                role="member",
            )
        )
        model.Session.add(
            AccessRequest(
                user_id=requesting_user["id"],
                object_id=dataset1["id"],
                object_type="package",
                message="",
                role="member",
            )
        )
        model.Session.commit()

        # sysadmin can see/approve all 4 requests:
        # 2 x new container
        # 1 x container access
        # 1 x new dataset
        context = {'model': model, 'user': 'sysadmin'}
        count = helpers.get_pending_requests_total(context=context)
        assert_equals(count, 4)

        # but user can't see/approve any of them
        user = core_factories.User(name='user', id='user')
        context = {'model': model, 'user': 'user'}
        count = helpers.get_pending_requests_total(context=context)
        assert_equals(count, 0)

    def test_get_pending_requests_total_empty(self):
        sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        context = {'model': model, 'user': 'sysadmin'}
        count = helpers.get_pending_requests_total(context=context)
        assert_equals(count, 0)


class TestDepositedDatasetHelpers(base.FunctionalTestBase):

    def setup(self):
        super(TestDepositedDatasetHelpers, self).setup()

        self.depadmin = core_factories.User()
        self.curator = core_factories.User()
        self.target_container_admin = core_factories.User()
        self.target_container_member = core_factories.User()
        self.other_container_admin = core_factories.User()
        self.depositor = core_factories.User()

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

        self.draft_dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            creator_user_id=self.depositor['id'],
            user=self.depositor,
            curation_state='draft',
        )
        self.submitted_dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            creator_user_id=self.depositor['id'],
            user=self.depositor,
            curation_state='submitted',
        )
        self.review_dataset = factories.DepositedDataset(
            owner_org=deposit['id'],
            owner_org_dest=target['id'],
            creator_user_id=self.depositor['id'],
            user=self.depositor,
            curation_state='review',
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_admin(self):
        assert_equals(
            'admin',
            helpers.get_deposited_dataset_user_curation_role(
                self.depadmin['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_curator(self):
        assert_equals(
            'curator',
            helpers.get_deposited_dataset_user_curation_role(
                self.curator['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_container_admin(self):
        assert_equals(
            'container admin',
            helpers.get_deposited_dataset_user_curation_role(
                self.target_container_admin['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_depositor(self):
        assert_equals(
            'depositor',
            helpers.get_deposited_dataset_user_curation_role(
                self.depositor['id'],
                self.draft_dataset,
            )
        )

    def test_get_deposited_dataset_user_curation_role_with_dataset_user(self):
        for user in [self.target_container_member, self.other_container_admin]:
            assert_equals(
                'user',
                helpers.get_deposited_dataset_user_curation_role(
                    user['id'],
                    self.draft_dataset,
                )
            )

    def test_get_deposited_dataset_user_curation_role_without_dataset_admin(self):
        assert_equals(
            'admin',
            helpers.get_deposited_dataset_user_curation_role(self.depadmin['id'])
        )

    def test_get_deposited_dataset_user_curation_role_without_dataset_curator(self):
        assert_equals(
            'curator',
            helpers.get_deposited_dataset_user_curation_role(self.curator['id'])
        )

    def test_get_deposited_dataset_user_curation_role_without_dataset_container_admin(self):
        for user in [self.target_container_admin, self.other_container_admin]:
            assert_equals(
                'container admin',
                helpers.get_deposited_dataset_user_curation_role(user['id'])
            )

    def test_get_deposited_dataset_user_curation_role_without_dataset_depositor(self):
        for user in [self.target_container_member, self.depositor]:
            assert_equals(
                'depositor',
                helpers.get_deposited_dataset_user_curation_role(user['id'])
            )

    def test_get_deposited_dataset_user_curation_status_admin_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.depadmin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_admin_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.depadmin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals(['edit', 'reject', 'assign', 'request_changes'], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_admin_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.depadmin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_curator_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.curator['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('curator', status['role'])

    def test_get_deposited_dataset_user_curation_status_curator_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.curator['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals(['edit', 'reject', 'request_changes'], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('curator', status['role'])

    def test_get_deposited_dataset_user_curation_status_curator_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.curator['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('curator', status['role'])

    def test_get_deposited_dataset_user_curation_status_container_admin_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.target_container_admin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('container admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_container_admin_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.target_container_admin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals(['edit', 'reject', 'request_changes'], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('container admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_container_admin_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.target_container_admin['id'],
        )

        assert_equals(False, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('container admin', status['role'])

    def test_get_deposited_dataset_user_curation_status_depositor_draft(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.draft_dataset,
            self.depositor['id'],
        )

        assert_equals(True, status['is_depositor'])
        assert_equals(['edit', 'submit', 'withdraw'], status['actions'])
        assert_equals('draft', status['state'])
        assert_equals('depositor', status['role'])

    def test_get_deposited_dataset_user_curation_status_depositor_submitted(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.submitted_dataset,
            self.depositor['id'],
        )

        assert_equals(True, status['is_depositor'])
        assert_equals([], status['actions'])
        assert_equals('submitted', status['state'])
        assert_equals('depositor', status['role'])

    def test_get_deposited_dataset_user_curation_status_depositor_review(self):
        status = helpers.get_deposited_dataset_user_curation_status(
            self.review_dataset,
            self.depositor['id'],
        )

        assert_equals(True, status['is_depositor'])
        assert_equals(['request_changes'], status['actions'])
        assert_equals('review', status['state'])
        assert_equals('depositor', status['role'])

    def test_get_deposited_dataset_user_curation_status_user_draft(self):
        for user in [self.target_container_member, self.other_container_admin]:
            status = helpers.get_deposited_dataset_user_curation_status(
                self.draft_dataset,
                user['id'],
            )

            assert_equals(False, status['is_depositor'])
            assert_equals([], status['actions'])
            assert_equals('draft', status['state'])
            assert_equals('user', status['role'])

    def test_get_deposited_dataset_user_curation_status_user_submitted(self):
        for user in [self.target_container_member, self.other_container_admin]:
            status = helpers.get_deposited_dataset_user_curation_status(
                self.submitted_dataset,
                user['id'],
            )

            assert_equals(False, status['is_depositor'])
            assert_equals([], status['actions'])
            assert_equals('submitted', status['state'])
            assert_equals('user', status['role'])

    def test_get_deposited_dataset_user_curation_status_user_review(self):
        for user in [self.target_container_member, self.other_container_admin]:
            status = helpers.get_deposited_dataset_user_curation_status(
                self.review_dataset,
                user['id'],
            )

            assert_equals(False, status['is_depositor'])
            assert_equals([], status['actions'])
            assert_equals('review', status['state'])
            assert_equals('user', status['role'])

    def test_get_data_curation_users_no_container_admin(self):
        curators = helpers.get_data_curation_users({})
        curator_names = [
            curator['name'] for curator in curators
            # Added to org by ckan
            if not curator['sysadmin']
        ]
        assert_equals(len(curator_names), 2)
        assert_in(self.depadmin['name'], curator_names)
        assert_in(self.curator['name'], curator_names)

    def test_get_data_curation_users_with_container_admin(self):
        curators = helpers.get_data_curation_users(self.draft_dataset)
        curator_names = [
            curator['name'] for curator in curators
            # Added to org by ckan
            if not curator['sysadmin']
        ]
        assert_equals(len(curator_names), 3)
        assert_in(self.depadmin['name'], curator_names)
        assert_in(self.curator['name'], curator_names)
        assert_in(self.target_container_admin['name'], curator_names)
