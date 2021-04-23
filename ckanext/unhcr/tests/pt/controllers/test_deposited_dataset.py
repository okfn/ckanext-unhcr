# -*- coding: utf-8 -*-

import pytest
import mock
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories


ACTIONS = [
    'approve',
    'assign',
    'request_changes',
    'request_review',
    'reject',
    'submit',
    'withdraw',
]


@pytest.mark.usefixtures('unhcr_migrate', 'with_request_context')
class TestDepositedDatasetController(object):

    def setup_class(self):
        core_helpers.reset_db()

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.depadmin = core_factories.User(name='depadmin', id='depadmin')
        self.curator = core_factories.User(name='curator', id='curator')
        self.creator = core_factories.User(name='creator', id='creator')
        self.depositor = core_factories.User(name='depositor', id='depositor')
        self.editor = core_factories.User(name='editor', id='editor')
        self.target_container_admin = core_factories.User(
            name='target_container_admin',
            id='target_container_admin'
        )
        self.target_container_member = core_factories.User(
            name='target_container_member',
            id='target_container_member'
        )
        self.other_container_admin = core_factories.User(
            name='other_container_admin',
            id='other_container_admin'
        )

        app = core_helpers._get_test_app()
        self.deposit = factories.DataContainer(
            users=[
                {'name': 'curator', 'capacity': 'editor'},
                {'name': 'depadmin', 'capacity': 'admin'},
            ],
            name='data-deposit',
            id='data-deposit'
        )
        self.target = factories.DataContainer(
            name='data-target',
            id='data-target',
            users=[
                {'name': 'editor', 'capacity': 'editor'},
                {'name': 'target_container_admin', 'capacity': 'admin'},
                {'name': 'target_container_member', 'capacity': 'member'},
            ],
        )
        container = factories.DataContainer(
            users=[
                {'name': 'other_container_admin', 'capacity': 'admin'},
            ]
        )

    def teardown_class(self):
        core_helpers.reset_db()


    def setup(self):
        self.app = core_helpers._get_test_app()

        self.dataset = factories.DepositedDataset(
            name='dataset',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=self.creator)

    def teardown(self):
        package = model.Package.get(self.dataset['id'])
        model.Session.delete(package)
        model.Session.commit()


    # Helpers

    def patch_dataset(self, patch):
        dataset = self.dataset.copy()
        dataset.update(patch)
        self.dataset = core_helpers.call_action(
            'package_update', {'user': 'sysadmin'}, **dataset)

    def make_request(self, action, dataset_id=None, user=None, **kwargs):
        url = '/deposited-dataset/%s/%s' % (
            dataset_id or self.dataset['id'].encode('ascii'),
            action
        )
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        data = kwargs.pop('data', {})
        with self.app.flask_app.test_request_context():
            resp = self.app.post(url, data=data, extra_environ=env, **kwargs)
        if not dataset_id:
            try:
                self.dataset = core_helpers.call_action(
                    'package_show', {'user': 'sysadmin'}, id=self.dataset['id'])
            except toolkit.ObjectNotFound:
                self.dataset = None

        return resp

    def assert_mail(self, mail, users, subject, texts):
        for index, user in enumerate(users):
            assert mail.call_args_list[index][0][0] == user
            assert mail.call_args_list[index][0][1] == subject
            for text in texts:
                assert text in mail.call_args_list[index][0][2]

    # General

    def test_all_actions_anonymous(self):
        for action in ACTIONS:
            self.make_request(action, status=403)

    def test_all_actions_bad_dataset_id(self):
        for action in ACTIONS:
            self.make_request(action, dataset_id='bad-id', status=403)

    def test_all_actions_bad_dataset_type(self):
        factories.Dataset(name='regular', owner_org='data-target', user=self.creator)
        for action in ACTIONS:
            self.make_request(action, dataset_id='regular', user='sysadmin', status=403)

    # Approve (draft)

    def test_approve_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_approve_draft_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_approve_draft_not_granted(user, 403)

    def check_approve_draft_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        if error:
            assert error in resp.body

    # Approve (submitted)

    @pytest.mark.parametrize("user", ['sysadmin', 'depadmin', 'curator', 'target_container_admin'])
    def test_approve_submitted(self, user):
        self.check_approve_submitted(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_approve_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=200)
        assert self.dataset['type'] == 'dataset'
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been approved'],
        )

    def test_approve_submitted_final_review_requested(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_approve_submitted_final_review_requested(user, 200, "action is not available")

    def check_approve_submitted_final_review_requested(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        assert error in resp.body

    def test_approve_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_approve_submitted_not_valid(user, 200, "action is not available")

    def check_approve_submitted_not_valid(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        assert error in resp.body

    def test_approve_submitted_not_granted(self):
        for user in ['creator']:
            self.check_approve_submitted_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_approve_submitted_not_granted(user, 403)

    def check_approve_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        if error:
            assert error in resp.body

    # Approve (review)

    def test_approve_review_without_curator(self, app):
        self.app = app
        self.check_approve_review_without_curator('creator')

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_approve_review_without_curator(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=200)
        assert self.dataset['type'] == 'dataset'
        assert self.dataset['owner_org'] == 'data-target'
        mail.assert_not_called()

    def test_approve_review_with_curator(self, app):
        self.app = app
        self.check_approve_review_with_curator('creator')

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_approve_review_with_curator(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curator_id': 'curator',
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Approve dataset
        self.make_request('approve', user=user, status=200)
        assert self.dataset['type'] == 'dataset'
        assert self.dataset['owner_org'] == 'data-target'
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been approved'],
        )

    def test_approve_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_approve_review_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_approve_review_not_granted(user, 403)

    def check_approve_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        if error:
            assert error in resp.body

    # Assign (draft)

    def test_assign_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_assign_draft_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_assign_draft_not_granted(user, 403)

    def check_assign_draft_not_granted(self, user, status, error=None):

        # Request changes
        params = {'curator_id': self.curator['id']}
        resp = self.make_request('assign', user=user, data=params, status=status)
        if error:
            assert error in resp.body

    # Assign (submitted)

    @pytest.mark.parametrize("user", ['sysadmin', 'depadmin'])
    def test_assign_submitted(self, user):
        self.check_assign_submitted(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=user, data=params, status=200)
        assert self.dataset['curator_id'] == self.curator['id']
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['A new dataset has been assigned to you for curation'],
        )

    @pytest.mark.parametrize("user", ['sysadmin', 'depadmin'])
    def test_assign_submitted_remove(self, user):
        self.check_assign_submitted_remove(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted_remove(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curator_id': 'curator',
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': ''}
        self.make_request('assign', user=user, data=params, status=200)
        assert self.dataset.get('curator_id') is None
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['You have been removed as Curator of the following dataset'],
        )

    @pytest.mark.parametrize("user", ['sysadmin', 'depadmin'])
    def test_assign_submitted_remove_not_assigned(self, user):
        self.check_assign_submitted_remove_not_assigned(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted_remove_not_assigned(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': ''}
        self.make_request('assign', user=user, data=params, status=200)
        assert self.dataset.get('curator_id') == None
        mail.assert_not_called()

    def test_assign_submitted_bad_curator_id(self):
        for user in ['sysadmin', 'depadmin']:
            self.check_assign_submitted_bad_curator_id(user)

    def check_assign_submitted_bad_curator_id(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.depositor['id']}
        self.make_request('assign', user=user, data=params, status=403)

    def test_assign_submitted_not_granted(self):
        for user in ['curator', 'creator']:
            self.check_assign_submitted_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_assign_submitted_not_granted(user, 403)

    def check_assign_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.curator['id']}
        resp = self.make_request('assign', user=user, data=params, status=status)
        if error:
            assert error in resp.body

    # Assign (review)

    def test_assign_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_assign_review_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_assign_review_not_granted(user, 403)

    def check_assign_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request changes
        params = {'curator_id': self.curator['id']}
        resp = self.make_request('assign', user=user, data=params, status=status)
        if error:
            assert error in resp.body

    # Request Changes (draft)

    def test_request_changes_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_request_changes_draft_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_request_changes_draft_not_granted(user, 403)

    def check_request_changes_draft_not_granted(self, user, status, error=None):

        # Request changes
        resp = self.make_request('request_changes', user=user, status=status)
        if error:
            assert error in resp.body

    # Request Changes (submitted)

    @pytest.mark.parametrize("user", ['sysadmin', 'depadmin', 'curator', 'target_container_admin'])
    def test_request_changes_submitted(self, user):
        self.check_request_changes_submitted(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_request_changes_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=200)
        assert self.dataset['curation_state'] == 'draft'
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['The Reviewer has requested changes on the following dataset'],
        )

    def test_request_changes_submitted_not_granted(self):
        for user in ['creator']:
            self.check_request_changes_submitted_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_request_changes_submitted_not_granted(user, 403)

    def check_request_changes_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        resp = self.make_request('request_changes', user=user, status=status)
        if error:
            assert error in resp.body

    # Request Changes (review)

    def test_request_changes_review(self, app):
        self.app = app
        self.check_request_changes_review('creator')

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_request_changes_review(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curator_id': 'curator',
            'curation_state': 'review',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=200)
        assert self.dataset['curation_state'] == 'submitted'
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['The Reviewer has requested changes on the following dataset'],
        )

    def test_request_changes_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_request_changes_review_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_request_changes_review_not_granted(user, 403)

    def check_request_changes_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request changes
        resp = self.make_request('request_changes', user=user, status=status)
        if error:
            assert error in resp.body

    # Request Review (draft)

    def test_request_review_draft(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_request_review_draft(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_request_review_draft(user, 403)

    def check_request_review_draft(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        if error:
            assert error in resp.body

    # Request Review (submitted)

    @pytest.mark.parametrize("user", ['sysadmin', 'depadmin', 'curator', 'target_container_admin'])
    def test_request_review_submitted(self, user):
        self.check_request_review_submitted(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_request_review_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request review
        self.make_request('request_review', user=user, status=200)
        assert self.dataset['curation_state'] == 'review'
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['As Depositor of this dataset, the Curator assigned to it has requested your final review before publication'],
        )

    def test_request_review_submitted_not_final_review_requested(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_request_review_submitted_not_final_review_requested(user, 200, "action is not available")

    def check_request_review_submitted_not_final_review_requested(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        if error:
            assert error in resp.body

    def test_request_review_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_request_review_submitted_not_valid(user, 200, "action is not available")

    def check_request_review_submitted_not_valid(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        assert error in resp.body

    def test_request_review_submitted_not_granted(self):
        for user in ['creator']:
            self.check_request_review_submitted_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_request_review_submitted_not_granted(user, 403)

    def check_request_review_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        if error:
            assert error in resp.body

    # Request Review (review)

    def test_request_review_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_request_review_review_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_request_review_review_not_granted(user, 403)

    def check_request_review_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        if error:
            assert error in resp.body

    # Reject (draft)

    def test_reject_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_reject_draft_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_reject_draft_not_granted(user, 403)

    def check_reject_draft_not_granted(self, user, status, error=None):

        # Reject dataset
        resp = self.make_request('reject', user=user, status=status)
        if error:
            assert error in resp.body

    # Reject (submitted)

    @pytest.mark.parametrize("user", ['sysadmin', 'depadmin', 'curator', 'target_container_admin'])
    def test_reject_submitted(self, user):
        self.check_reject_submitted(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_reject_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        self.make_request('reject', user=user, status=200)
        assert self.dataset['state'] == 'deleted'
        assert '-rejected-' in self.dataset['name']
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been rejected'],
        )

    def test_reject_submitted_not_granted(self):
        for user in ['creator']:
            self.check_reject_submitted_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_reject_submitted_not_granted(user, 403)

    def check_reject_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        resp = self.make_request('reject', user=user, status=status)
        if error:
            assert error in resp.body

    # Reject (review)

    def test_reject_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_reject_review_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_reject_review_not_granted(user, 403)

    def check_reject_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Reject dataset
        resp = self.make_request('reject', user=user, status=status)
        if error:
            assert error in resp.body

    # Submit (draft)

    def test_submit_draft(self, app):
        self.app = app
        self.check_submit_draft('creator')

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def check_submit_draft(self, user, mail):

        # Submit dataset
        self.make_request('submit', user=user, status=200)

        assert self.dataset['curation_state'] == 'submitted'
        subject = '[UNHCR RIDL] Curation: Test Dataset'
        text = 'A new dataset has been submitted for curation by %s' % self.creator['display_name']
        calls = [call for call in mail.call_args_list if call[0][0].__name__ == 'mail_user_by_id']

        assert calls[0][0][1][0] == 'curator'
        assert calls[0][0][1][1] == subject
        assert text in calls[0][0][1][2]

        assert calls[1][0][1][0] == 'depadmin'
        assert calls[1][0][1][1] == subject
        assert text in calls[1][0][1][2]

    def test_submit_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_submit_draft_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_submit_draft_not_granted(user, 403)

    def check_submit_draft_not_granted(self, user, status, error=None):

        # Submit dataset
        resp = self.make_request('submit', user=user, status=status)
        if error:
            assert error in resp.body

    # Submit (submitted)

    def test_submit_submitted_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_submit_submitted_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_submit_submitted_not_granted(user, 403)

    def check_submit_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Submit dataset
        resp = self.make_request('submit', user=user, status=status)
        if error:
            assert error in resp.body

    # Submit (review)

    def test_submit_reviw_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_submit_review_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_submit_review_not_granted(user, 403)

    def check_submit_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Submit dataset
        resp = self.make_request('submit', user=user, status=status)
        if error:
            assert error in resp.body

    # Withdraw (draft)

    def test_withdraw_draft(self, app):
        self.app = app
        self.check_withdraw_draft('creator')

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_withdraw_draft(self, user, mail):

        # Withdraw dataset
        self.make_request('withdraw', user=user, status=200)
        assert self.dataset['state'] == 'deleted'
        assert '-withdrawn-' in self.dataset['name']
        self.assert_mail(mail,
            users=['curator', 'depadmin'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been withdrawn from curation by %s' % self.creator['display_name']],
        )

    def test_withdraw_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            self.check_withdraw_draft_not_granted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_withdraw_draft_not_granted(user, 403)

    def check_withdraw_draft_not_granted(self, user, status, error=None):

        # Withdraw dataset
        resp = self.make_request('withdraw', user=user, status=status)
        if error:
            assert error in resp.body

    # Withdraw (submitted)

    def test_withdraw_submitted_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_withdraw_submitted(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_withdraw_submitted(user, 403)

    def check_withdraw_submitted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Withdraw dataset
        resp = self.make_request('withdraw', user=user, status=status)
        if error:
            assert error in resp.body

    # Withdraw (review)

    def test_withdraw_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            self.check_withdraw_review(user, 200, "action is not available")
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            self.check_withdraw_review(user, 403)

    def check_withdraw_review(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Withdraw dataset
        resp = self.make_request('withdraw', user=user, status=status)
        if error:
            assert error in resp.body

    # Activities

    def _approve_dataset(self):
        self.patch_dataset({
            'curation_state': 'submitted',
            'unit_of_measurement': 'individual',
            'keywords': ['3', '4'],
            'archived': 'False',
            'data_collector': ['acf'],
            'data_collection_technique': 'f2f',
            'external_access_level': 'open_access',
        })

        self.make_request('approve', user='sysadmin', status=200)

    def test_activites_shown_on_deposited_dataset(self, app):

        env = {'REMOTE_USER': self.creator['name'].encode('ascii')}
        resp = app.get(
            url=toolkit.url_for('deposited-dataset_read', id=self.dataset['id']),
            extra_environ=env,
            status=200,
        )
        assert 'Internal Activity' in resp.body

    @pytest.mark.parametrize("user", ['sysadmin', 'editor', 'target_container_admin'])
    def test_activites_shown_on_normal_dataset(self, user):
        self.check_activities_shown(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_activities_shown(self, user, mail):

        self._approve_dataset()

        env = {'REMOTE_USER': user.encode('ascii')}
        with self.app.flask_app.test_request_context():
            resp = self.app.get(
                url=toolkit.url_for('dataset_read', id=self.dataset['id']),
                extra_environ=env,
                status=200,
            )
        assert 'Internal Activity' in resp.body

    @pytest.mark.parametrize("user", ['depositor', 'curator', 'target_container_member', 'other_container_admin'])
    def test_activites_not_shown_on_normal_dataset(self, user):
        self.check_activities_not_shown(user)

    @mock.patch('ckanext.unhcr.blueprints.deposited_dataset.mailer.mail_user_by_id')
    def check_activities_not_shown(self, user, mail):

        self._approve_dataset()

        env = {'REMOTE_USER': user.encode('ascii')}
        with self.app.flask_app.test_request_context():
            resp = self.app.get(
                url=toolkit.url_for('dataset_read', id=self.dataset['id']),
                extra_environ=env,
                status=200,
            )
        assert 'Internal Activity' not in resp.body

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_activity_created_in_deposited_dataset(self, mail, app):
        self.make_request('submit', user=self.creator['name'], status=200)
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=self.depadmin['name'], data=params)

        env = {'REMOTE_USER': self.curator['name'].encode('ascii')}
        resp = app.get(
            url=toolkit.url_for('deposited-dataset_internal_activity', dataset_id=self.dataset['name']),
            extra_environ=env,
            status=200,
        )
        assert 'deposited dataset' in resp.body
        assert 'submitted dataset' in resp.body
        assert 'assigned' in resp.body
        assert 'as Curator' in resp.body
