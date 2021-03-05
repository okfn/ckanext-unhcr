import nose
import mock
from nose.plugins.attrib import attr
from sqlalchemy import and_, select
from ckan.lib.helpers import url_for
from ckan.lib.search import index_for
from ckan.logic import NotFound
import ckan.model as model
from ckan.plugins import toolkit
from nose.tools import assert_raises, assert_equals, nottest
from ckan.tests import helpers as core_helpers, factories as core_factories
from ckanext.unhcr.models import AccessRequest
from ckanext.unhcr.tests import base, factories, mocks

assert_in = core_helpers.assert_in
assert_not_in = core_helpers.assert_not_in

# TODO: optimize testing speed
class TestDepositedDatasetController(base.FunctionalTestBase):

    ACTIONS = [
        'approve',
        'assign',
        'request_changes',
        'request_review',
        'reject',
        'submit',
        'withdraw',
    ]

    # Config

    def setup(self):
        super(TestDepositedDatasetController, self).setup()

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

        # Containers
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

        # Dataset
        self.dataset = factories.DepositedDataset(
            name='dataset',
            owner_org='data-deposit',
            owner_org_dest='data-target',
            user=self.creator)

    # Helpers

    def patch_dataset(self, patch):
        dataset = self.dataset.copy()
        dataset.update(patch)
        self.dataset = core_helpers.call_action(
            'package_update', {'user': 'sysadmin'}, **dataset)

    def make_request(self, action, dataset_id=None, user=None, **kwargs):
        url = '/deposited-dataset/%s/%s' % (dataset_id or self.dataset['id'], action)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        if not dataset_id:
            try:
                self.dataset = core_helpers.call_action(
                    'package_show', {'user': 'sysadmin'}, id=self.dataset['id'])
            except toolkit.ObjectNotFound:
                self.dataset = None

        if resp.status_int in [301, 302]:
            return resp.follow(extra_environ=env, status=200)

        return resp

    def assert_mail(self, mail, users, subject, texts):
        for index, user in enumerate(users):
            assert_equals(mail.call_args_list[index][0][0], user)
            assert_equals(mail.call_args_list[index][0][1], subject)
            for text in texts:
                assert_in(text, mail.call_args_list[index][0][2])

    # General

    def test_all_actions_anonimous(self):
        for action in self.ACTIONS:
            self.make_request(action, status=403)

    def test_all_actions_bad_dataset_id(self):
        for action in self.ACTIONS:
            self.make_request(action, dataset_id='bad-id', status=403)

    def test_all_actions_bad_dataset_type(self):
        factories.Dataset(name='regular', owner_org='data-target', user=self.creator)
        for action in self.ACTIONS:
            self.make_request(action, dataset_id='regular', user='sysadmin', status=403)

    # Approve (draft)

    def test_approve_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_approve_draft_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_approve_draft_not_granted, user, 403

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
            assert_in(error, resp.body)

    # Approve (submitted)

    def test_approve_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_approve_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
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
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been approved'],
        )

    def test_approve_submitted_final_review_requested(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_approve_submitted_final_review_requested, user, 302, "action is not available"

    def check_approve_submitted_final_review_requested(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    def test_approve_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_approve_submitted_not_valid, user, 302, "action is not available"

    def check_approve_submitted_not_valid(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    def test_approve_submitted_not_granted(self):
        for user in ['creator']:
            yield self.check_approve_submitted_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_approve_submitted_not_granted, user, 403

    def check_approve_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Approve (review)

    def test_approve_review_without_curator(self):
        for user in ['creator']:
            yield self.check_approve_review_without_curator, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
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
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')
        assert_equals(self.dataset['owner_org'], 'data-target')
        mail.assert_not_called()

    def test_approve_review_with_curator(self):
        for user in ['creator']:
            yield self.check_approve_review_with_curator, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
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
        self.make_request('approve', user=user, status=302)
        assert_equals(self.dataset['type'], 'dataset')
        assert_equals(self.dataset['owner_org'], 'data-target')
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been approved'],
        )

    def test_approve_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_approve_review_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_approve_review_not_granted, user, 403

    def check_approve_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Approve dataset
        resp = self.make_request('approve', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Assign (draft)

    def test_assign_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_assign_draft_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_assign_draft_not_granted, user, 403

    def check_assign_draft_not_granted(self, user, status, error=None):

        # Request changes
        params = {'curator_id': self.curator['id']}
        resp = self.make_request('assign', user=user, params=params, status=status)
        if error:
            assert_in(error, resp.body)

    # Assign (submitted)

    def test_assign_submitted(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset['curator_id'], self.curator['id'])
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['A new dataset has been assigned to you for curation'],
        )

    def test_assign_submitted_remove(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted_remove, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted_remove(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curator_id': 'curator',
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': ''}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset.get('curator_id'), None)
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['You have been removed as Curator of the following dataset'],
        )

    def test_assign_submitted_remove_not_assigned(self):
        for user in ['sysadmin', 'depadmin']:
            yield self.check_assign_submitted_remove_not_assigned, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_assign_submitted_remove_not_assigned(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': ''}
        self.make_request('assign', user=user, params=params, status=302)
        assert_equals(self.dataset.get('curator_id'), None)
        mail.assert_not_called()

    # TODO: it breaks sessions for all following tests
    #  def test_assign_submitted_bad_curator_id(self):
        #  for user in ['sysadmin', 'depadmin']:
            #  yield self.check_assign_submitted_bad_curator_id, user

    def check_assign_submitted_bad_curator_id(self, user):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.depositor['id']}
        self.make_request('assign', user=user, params=params, status=403)

    def test_assign_submitted_not_granted(self):
        for user in ['curator', 'creator']:
            yield self.check_assign_submitted_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_assign_submitted_not_granted, user, 403

    def check_assign_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Assign curator
        params = {'curator_id': self.curator['id']}
        resp = self.make_request('assign', user=user, params=params, status=status)
        if error:
            assert_in(error, resp.body)

    # Assign (review)

    def test_assign_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_assign_review_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_assign_review_not_granted, user, 403

    def check_assign_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request changes
        params = {'curator_id': self.curator['id']}
        resp = self.make_request('assign', user=user, params=params, status=status)
        if error:
            assert_in(error, resp.body)

    # Request Changes (draft)

    def test_request_changes_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_request_changes_draft_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_request_changes_draft_not_granted, user, 403

    def check_request_changes_draft_not_granted(self, user, status, error=None):

        # Request changes
        resp = self.make_request('request_changes', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Request Changes (submitted)

    def test_request_changes_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_request_changes_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_request_changes_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        self.make_request('request_changes', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'draft')
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['The Reviewer has requested changes on the following dataset'],
        )

    def test_request_changes_submitted_not_granted(self):
        for user in ['creator']:
            yield self.check_request_changes_submitted_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_request_changes_submitted_not_granted, user, 403

    def check_request_changes_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Request changes
        resp = self.make_request('request_changes', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Request Changes (review)

    def test_request_changes_review(self):
        for user in ['creator']:
            yield self.check_request_changes_review, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
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
        self.make_request('request_changes', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'submitted')
        self.assert_mail(mail,
            users=['curator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['The Reviewer has requested changes on the following dataset'],
        )

    def test_request_changes_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_request_changes_review_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_request_changes_review_not_granted, user, 403

    def check_request_changes_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request changes
        resp = self.make_request('request_changes', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Request Review (draft)

    def test_request_review_draft(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_request_review_draft, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_request_review_draft, user, 403

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
            assert_in(error, resp.body)

    # Request Review (submitted)

    def test_request_review_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_request_review_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
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
        self.make_request('request_review', user=user, status=302)
        assert_equals(self.dataset['curation_state'], 'review')
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['As Depositor of this dataset, the Curator assigned to it has requested your final review before publication'],
        )

    def test_request_review_submitted_not_final_review_requested(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_request_review_submitted_not_final_review_requested, user, 302, "action is not available"

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
            assert_in(error, resp.body)

    def test_request_review_submitted_not_valid(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_request_review_submitted_not_valid, user, 302, "action is not available"

    def check_request_review_submitted_not_valid(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    def test_request_review_submitted_not_granted(self):
        for user in ['creator']:
            yield self.check_request_review_submitted_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_request_review_submitted_not_granted, user, 403

    def check_request_review_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_final_review': 'True',
            'curation_state': 'submitted',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Request Review (review)

    def test_request_review_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_request_review_review_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_request_review_review_not_granted, user, 403

    def check_request_review_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Request review
        resp = self.make_request('request_review', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Reject (draft)

    def test_reject_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_reject_draft_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_reject_draft_not_granted, user, 403

    def check_reject_draft_not_granted(self, user, status, error=None):

        # Reject dataset
        resp = self.make_request('reject', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Reject (submitted)

    def test_reject_submitted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_reject_submitted, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_reject_submitted(self, user, mail):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        self.make_request('reject', user=user, status=302)
        assert_equals(self.dataset['state'], 'deleted')
        assert_in('-rejected-', self.dataset['name'])
        self.assert_mail(mail,
            users=['creator'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been rejected'],
        )

    def test_reject_submitted_not_granted(self):
        for user in ['creator']:
            yield self.check_reject_submitted_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_reject_submitted_not_granted, user, 403

    def check_reject_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Reject dataset
        resp = self.make_request('reject', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Reject (review)

    def test_reject_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_reject_review_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_reject_review_not_granted, user, 403

    def check_reject_review_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Reject dataset
        resp = self.make_request('reject', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Submit (draft)

    def test_submit_draft(self):
        for user in ['creator']:
            yield self.check_submit_draft, user

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def check_submit_draft(self, user, mail):

        # Submit dataset
        self.make_request('submit', user=user, status=302)

        assert_equals(self.dataset['curation_state'], 'submitted')
        subject = '[UNHCR RIDL] Curation: Test Dataset'
        text = 'A new dataset has been submitted for curation by %s' % self.creator['display_name']
        calls = [call for call in mail.call_args_list if call[0][0].__name__ == 'mail_user_by_id']

        assert_equals(calls[0][0][1][0], 'curator')
        assert_equals(calls[0][0][1][1], subject)
        assert_in(text, calls[0][0][1][2])

        assert_equals(calls[1][0][1][0], 'depadmin')
        assert_equals(calls[1][0][1][1], subject)
        assert_in(text, calls[1][0][1][2])

    def test_submit_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_submit_draft_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_submit_draft_not_granted, user, 403

    def check_submit_draft_not_granted(self, user, status, error=None):

        # Submit dataset
        resp = self.make_request('submit', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Submit (submitted)

    def test_submit_submitted_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_submit_submitted_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_submit_submitted_not_granted, user, 403

    def check_submit_submitted_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Submit dataset
        resp = self.make_request('submit', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Submit (review)

    def test_submit_reviw_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_submit_reviw_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_submit_reviw_not_granted, user, 403

    def check_submit_reviw_not_granted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'review',
        })

        # Submit dataset
        resp = self.make_request('submit', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Withdraw (draft)

    def test_withdraw_draft(self):
        for user in ['creator']:
            yield self.check_withdraw_draft, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_withdraw_draft(self, user, mail):

        # Withdraw dataset
        self.make_request('withdraw', user=user, status=302)
        assert_equals(self.dataset['state'], 'deleted')
        assert_in('-withdrawn-', self.dataset['name'])
        self.assert_mail(mail,
            users=['curator', 'depadmin'],
            subject='[UNHCR RIDL] Curation: Test Dataset',
            texts=['This dataset has been withdrawn from curation by %s' % self.creator['display_name']],
        )

    def test_withdraw_draft_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'target_container_admin']:
            yield self.check_withdraw_draft_not_granted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_withdraw_draft_not_granted, user, 403

    def check_withdraw_draft_not_granted(self, user, status, error=None):

        # Withdraw dataset
        resp = self.make_request('withdraw', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Withdraw (submitted)

    def test_withdraw_submitted_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_withdraw_submitted, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_withdraw_submitted, user, 403

    def check_withdraw_submitted(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Withdraw dataset
        resp = self.make_request('withdraw', user=user, status=status)
        if error:
            assert_in(error, resp.body)

    # Withdraw (review)

    def test_withdraw_review_not_granted(self):
        for user in ['sysadmin', 'depadmin', 'curator', 'creator', 'target_container_admin']:
            yield self.check_withdraw_review, user, 302, "action is not available"
        for user in ['depositor', 'target_container_member', 'other_container_admin']:
            yield self.check_withdraw_review, user, 403

    def check_withdraw_review(self, user, status, error=None):

        # Prepare dataset
        self.patch_dataset({
            'curation_state': 'submitted',
        })

        # Withdraw dataset
        resp = self.make_request('withdraw', user=user, status=status)
        if error:
            assert_in(error, resp.body)

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

        self.make_request('approve', user='sysadmin', status=302)

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def test_activites_shown_on_deposited_dataset(self, mail):

        env = {'REMOTE_USER': self.creator['name'].encode('ascii')}
        resp = self.app.get(
            url=url_for('deposited-dataset_read', id=self.dataset['id']), extra_environ=env)
        assert_in('Internal Activity', resp.body)

    def test_activites_shown_on_normal_dataset(self):
        for user in ['sysadmin', 'editor', 'target_container_admin']:
            yield self.check_activities_shown, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_activities_shown(self, user, mail):

        self._approve_dataset()

        env = {'REMOTE_USER': user.encode('ascii')}
        resp = self.app.get(
            url=url_for('dataset_read', id=self.dataset['id']), extra_environ=env)

        assert_in('Internal Activity', resp.body)

    def test_activites_not_shown_on_normal_dataset(self):

        for user in ['depositor', 'curator', 'target_container_member', 'other_container_admin']:
            yield self.check_activities_not_shown, user

    @mock.patch('ckanext.unhcr.controllers.deposited_dataset.mailer.mail_user_by_id')
    def check_activities_not_shown(self, user, mail):

        self._approve_dataset()

        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(
            url=url_for('dataset_read', id=self.dataset['id']), extra_environ=env)

        assert_not_in('Internal Activity', resp.body)

    @mock.patch('ckan.plugins.toolkit.enqueue_job')
    def test_activity_created_in_deposited_dataset(self, mail):


        self.make_request('submit', user=self.creator['name'], status=302)
        params = {'curator_id': self.curator['id']}
        self.make_request('assign', user=self.depadmin['name'], params=params)

        env = {'REMOTE_USER': self.curator['name'].encode('ascii')}
        resp = self.app.get(
            url=url_for('deposited-dataset_internal_activity', dataset_id=self.dataset['name']), extra_environ=env)

        assert_in('deposited dataset', resp.body)
        assert_in('submitted dataset', resp.body)
        assert_in('assigned', resp.body)
        assert_in('as Curator', resp.body)


class TestUserController(base.FunctionalTestBase):

    def test_sysadmin_not_authorized(self):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        self.app.post('/user/sysadmin', {}, extra_environ=env, status=403)

    def test_sysadmin_invalid_user(self):
        user = core_factories.Sysadmin()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        self.app.post(
            '/user/sysadmin',
            {'id': 'fred', 'status': '1' },
            extra_environ=env,
            status=404
        )

    def test_sysadmin_promote_success(self):
        admin = core_factories.Sysadmin()
        env = {'REMOTE_USER': admin['name'].encode('ascii')}

        # create a normal user
        user = core_factories.User(fullname='Alice')

        # promote them
        resp = self.app.post(
            '/user/sysadmin',
            {'id': user['id'], 'status': '1' },
            extra_environ=env,
            status=302
        )
        resp2 = resp.follow(extra_environ=env, status=200)
        assert_in(
            'Promoted Alice to sysadmin',
            resp2.body
        )

        # now they are a sysadmin
        userobj = model.User.get(user['id'])
        assert_equals(True, userobj.sysadmin)

    def test_sysadmin_revoke_success(self):
        admin = core_factories.Sysadmin()
        env = {'REMOTE_USER': admin['name'].encode('ascii')}

        # create another sysadmin
        user = core_factories.Sysadmin(fullname='Bob')

        # revoke their status
        resp = self.app.post(
            '/user/sysadmin',
            {'id': user['id'], 'status': '0' },
            extra_environ=env,
            status=302
        )
        resp2 = resp.follow(extra_environ=env, status=200)
        assert_in(
            'Revoked sysadmin permission from Bob',
            resp2.body
        )

        # now they are not a sysadmin any more
        userobj = model.User.get(user['id'])
        assert_equals(False, userobj.sysadmin)


class TestAdminController(base.FunctionalTestBase):
    def test_index_sysadmin(self):
        user = core_factories.Sysadmin()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        self.app.get('/ckan-admin', extra_environ=env, status=200)

    def test_index_not_authorized(self):
        user = core_factories.User()
        env = {'REMOTE_USER': user['name'].encode('ascii')}
        self.app.get('/ckan-admin', extra_environ=env, status=403)


class TestExtendedPackageController(base.FunctionalTestBase):

    # Config

    def setup(self):
        super(TestExtendedPackageController, self).setup()

        # Users
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')
        self.user1 = core_factories.User(name='user1', id='user1')
        self.user2 = core_factories.User(name='user2', id='user2')
        self.user3 = core_factories.User(name='user3', id='user3')

        # Containers
        self.container1 = factories.DataContainer(
            name='container1',
            id='container1',
            users=[
                {'name': 'user1', 'capacity': 'admin'},
            ],
        )
        self.container2 = factories.DataContainer(
            name='container2',
            id='container2',
            users=[
                {'name': 'user2', 'capacity': 'admin'},
            ],
        )

        # Datasets
        self.dataset1 = factories.Dataset(
            name='dataset1',
            title='Test Dataset 1',
            owner_org='container1',
            data_collection_technique = 'f2f',
            sampling_procedure = 'nonprobability',
            operational_purpose_of_data = 'cartography',
            user=self.user1,
            visibility='private',
        )

        # Resources
        self.resource1 = factories.Resource(
            name='resource1',
            package_id='dataset1',
            url_type='upload',
            upload=mocks.FakeFileStorage(),
            url = "http://fakeurl/test.txt",
        )

    # Helpers

    def make_dataset_request(self, dataset_id=None, user=None, **kwargs):
        url = '/dataset/copy/%s' % dataset_id
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_resource_copy_request(self, dataset_id=None, resource_id=None, user=None, **kwargs):
        url = '/dataset/%s/resource_copy/%s' % (dataset_id, resource_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_resource_download_request(self, dataset_id, resource_id, user=None, **kwargs):
        url = toolkit.url_for(
            controller='package',
            action='resource_download',
            id=dataset_id,
            resource_id=resource_id
        )
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def make_request_access_request(self, dataset_id, user, message, **kwargs):
        url = '/dataset/{}/request_access'.format(dataset_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.post(
            url,
            {'message': message},
            extra_environ=env,
            **kwargs
        )
        return resp

    # Dataset

    def test_dataset_copy(self):
        resp = self.make_dataset_request(dataset_id='dataset1', user='user1')
        assert_in('action="/dataset/new"', resp.body)
        #  assert_in('dataset1-copy', resp.body)
        assert_in('f2f', resp.body)
        assert_in('nonprobability', resp.body)
        assert_in('cartography', resp.body)
        assert_in('Add Data', resp.body)
        assert_in('container1', resp.body)

    def test_dataset_copy_to_other_org(self):
        resp = self.make_dataset_request(dataset_id='dataset1', user='user2')
        assert_in('action="/dataset/new"', resp.body)
        #  assert_in('dataset1-copy', resp.body)
        assert_in('f2f', resp.body)
        assert_in('nonprobability', resp.body)
        assert_in('cartography', resp.body)
        assert_in('Add Data', resp.body)
        assert_not_in('container1', resp.body)

    def test_dataset_copy_no_orgs(self):
        resp = self.make_dataset_request(dataset_id='dataset1', user='user3', status=403)

    def test_dataset_copy_bad_dataset(self):
        resp = self.make_dataset_request(dataset_id='bad', user='user1', status=404)

    # Resource Upload

    def test_edit_resource_works(self):
        url = toolkit.url_for(
            controller='package',
            action='resource_edit',
            id=self.dataset1['id'],
            resource_id=self.resource1['id']
        )
        env = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}

        # Mock a resource edit payload
        data = {
            'id': self.resource1['id'],
            'name': self.resource1['name'],
            'type': self.resource1['type'],
            'description': 'updated',
            'format': self.resource1['format'],
            'file_type': self.resource1['file_type'],
            'date_range_start': self.resource1['date_range_start'],
            'date_range_end': self.resource1['date_range_end'],
            'version': self.resource1['version'],
            'process_status': self.resource1['process_status'],
            'identifiability': self.resource1['identifiability'],

            'url': 'test.txt',
            'save': ''

        }

        resp = self.app.post(url, data, extra_environ=env)

        assert 'The form contains invalid entries:' not in resp.body

    def test_edit_resource_must_provide_upload(self):
        url = toolkit.url_for(
            controller='package',
            action='resource_edit',
            id=self.dataset1['id'],
            resource_id=self.resource1['id']
        )
        env = {'REMOTE_USER': self.sysadmin['name'].encode('ascii')}

        # Mock a resource edit payload
        data = {
            'id': self.resource1['id'],
            'name': self.resource1['name'],
            'type': self.resource1['type'],
            'description': 'updated',
            'format': self.resource1['format'],
            'file_type': self.resource1['file_type'],
            'date_range_start': self.resource1['date_range_start'],
            'date_range_end': self.resource1['date_range_end'],
            'version': self.resource1['version'],
            'process_status': self.resource1['process_status'],
            'identifiability': self.resource1['identifiability'],

            'url': '',
            'clear_upload': 'true',
            'save': ''

        }

        resp = self.app.post(url, data, extra_environ=env)

        assert 'The form contains invalid entries:' in resp.body
        assert 'All data resources require an uploaded file' in resp.body

    # Resource Copy

    def test_resource_copy(self):
        resp = self.make_resource_copy_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user='user1')
        assert_in('action="/dataset/new_resource/dataset1"', resp.body)
        assert_in('resource1 (copy)', resp.body)
        assert_in('anonymized_public', resp.body)
        assert_in('Add', resp.body)

    def test_resource_copy_no_access(self):
        resp = self.make_resource_copy_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user='user2', status=403)

    def test_resource_copy_bad_resource(self):
        resp = self.make_resource_copy_request(
            dataset_id='dataset1', resource_id='bad', user='user1', status=404)

    # Resource Download

    def test_resource_download_anonymous(self):
        resp = self.make_resource_download_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user=None,
            status=403
        )

    def test_resource_download_no_access(self):
        resp = self.make_resource_download_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user='user3',
            status=403
        )

    def test_resource_download_collaborator(self):
        core_helpers.call_action(
            'dataset_collaborator_create',
            id='dataset1',
            user_id='user3',
            capacity='member',
        )
        resp = self.make_resource_download_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user='user3',
            status=200
        )

    def test_resource_download_bad_resource(self):
        resp = self.make_resource_download_request(
            dataset_id='dataset1', resource_id='bad', user='user1',
            status=404
        )

    def test_resource_download_valid(self):
        sql = select([
            model.Activity
        ]).where(
            and_(
                model.Activity.activity_type == 'download resource',
                model.Activity.object_id == self.dataset1['id'],
                model.Activity.user_id == 'user1',
            )
        )

        # before we start, this user has never downloaded this resource before
        result = model.Session.execute(sql).fetchall()
        assert_equals(0, len(result))

        resp = self.make_resource_download_request(
            dataset_id='dataset1', resource_id=self.resource1['id'], user='user1',
            status=200
        )

        # after we've downloaded the resource, we should also
        # have also logged a 'download resource' action for this user/resource
        result = model.Session.execute(sql).fetchall()
        assert_equals(1, len(result))

    # Request Access

    def test_request_access_invalid_method(self):
        resp = self.app.get(
            '/dataset/dataset1/request_access',
            extra_environ={'REMOTE_USER': 'user3'},
            status=404
        )

    def test_request_access_missing_message(self):
        self.make_request_access_request(
            dataset_id='dataset1', user='user3', message='',
            status=400
        )

    def test_request_access_duplicate(self):
        rec = AccessRequest(
            user_id=self.user3['id'],
            object_id=self.dataset1['id'],
            object_type='package',
            message='I can haz access?',
            role='member',
        )
        model.Session.add(rec)
        model.Session.commit()
        resp = self.make_request_access_request(
            dataset_id='dataset1', user='user3', message='me again',
            status=400
        )

    def test_request_access_invalid_dataset(self):
        self.make_request_access_request(
            dataset_id='bad', user='user3', message='I can haz access?',
            status=404
        )

    def test_request_access_not_authorized(self):
        self.make_request_access_request(
            dataset_id='dataset1', user=None, message='I can haz access?',
            status=403
        )

    def test_request_access_valid(self):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                dataset_id='dataset1', user='user3', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_called_once()
        assert_equals('user1', mock_mailer.call_args[0][1][0])
        assert_equals(
            '[UNHCR RIDL] - Request for access to dataset: "dataset1"',
            mock_mailer.call_args[0][1][1]
        )
        # call_args[0][1][2] is the HTML message body
        # but we're not going to make any assertions about it here
        # see the mailer tests for this

        assert_equals(
            1,
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.dataset1['id'],
                AccessRequest.user_id == self.user3['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'user3'}, status=200)
        assert_in(
            'Requested access to download resources from Test Dataset 1',
            resp2.body
        )

    def test_request_access_user_already_has_access(self):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                dataset_id='dataset1', user='user1', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_not_called()

        assert_equals(
            0,
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.dataset1['id'],
                AccessRequest.user_id == self.user1['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'user1'}, status=200)
        assert_in(
            'You already have access to download resources from Test Dataset 1',
            resp2.body
        )


class TestDataContainer(base.FunctionalTestBase):

    def setup(self):
        super(TestDataContainer, self).setup()

        self.deposit = factories.DataContainer(
            name='data-deposit',
            id='data-deposit',
        )
        self.user = core_factories.User(name='user1')
        self.admin = core_factories.User(name='admin')
        self.container = factories.DataContainer(
            name='container1',
            title='Test Container',
            users=[
                {'name': self.admin['name'], 'capacity': 'admin'},
            ]
        )

    def make_request_access_request(self, container_id, user, message, **kwargs):
        url = '/data-container/{}/request_access'.format(container_id)
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.post(
            url,
            {'message': message},
            extra_environ=env,
            **kwargs
        )
        return resp

    # Request Access

    def test_request_access_invalid_method(self):
        resp = self.app.get(
            '/data-container/container1/request_access',
            extra_environ={'REMOTE_USER': 'user1'},
            status=404
        )

    def test_request_access_missing_message(self):
        self.make_request_access_request(
            container_id='container1', user='user1', message='',
            status=400
        )

    def test_request_access_duplicate(self):
        rec = AccessRequest(
            user_id=self.user['id'],
            object_id=self.container['id'],
            object_type='organization',
            message='I can haz access?',
            role='member',
        )
        model.Session.add(rec)
        model.Session.commit()
        resp = self.make_request_access_request(
            container_id='container1', user='user1', message='me again',
            status=400
        )

    def test_request_access_invalid_containers(self):
        # this container doesn't exist
        self.make_request_access_request(
            container_id='bad', user='user1', message='I can haz access?',
            status=404
        )

        # we can't request access to the data-deposit
        # because it is _special and different_
        self.make_request_access_request(
            container_id='data-deposit', user='user3', message='I can haz access?',
            status=403
        )

    def test_request_access_not_authorized(self):
        self.make_request_access_request(
            container_id='container1', user=None, message='I can haz access?',
            status=403
        )

    def test_request_access_valid(self):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                container_id='container1', user='user1', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_called_once()
        assert_equals('admin', mock_mailer.call_args[0][1][0])
        assert_equals(
            '[UNHCR RIDL] - Request for access to container: "Test Container"',
            mock_mailer.call_args[0][1][1]
        )
        # call_args[0][1][2] is the HTML message body
        # but we're not going to make any assertions about it here
        # see the mailer tests for this

        assert_equals(
            1,
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.container['id'],
                AccessRequest.user_id == self.user['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'user1'}, status=200)
        assert_in(
            'Requested access to container Test Container',
            resp2.body
        )

    def test_request_access_user_already_has_access(self):
        mock_mailer = mock.Mock()
        with mock.patch('ckan.plugins.toolkit.enqueue_job', mock_mailer):
            resp = self.make_request_access_request(
                container_id='container1', user='admin', message='I can haz access?',
                status=302
            )

        mock_mailer.assert_not_called()

        assert_equals(
            0,
            len(model.Session.query(AccessRequest).filter(
                AccessRequest.object_id == self.container['id'],
                AccessRequest.user_id == self.admin['id'],
                AccessRequest.status == 'requested'
            ).all())
        )

        resp2 = resp.follow(extra_environ={'REMOTE_USER': 'admin'}, status=200)
        assert_in(
            'You are already a member of Test Container',
            resp2.body
        )


class TestAccessRequests(base.FunctionalTestBase):
    def setup(self):
        super(TestAccessRequests, self).setup()

        self.sysadmin = core_factories.Sysadmin()
        self.requesting_user = core_factories.User()
        self.standard_user = core_factories.User()
        self.pending_user = factories.ExternalUser(state=model.State.PENDING)

        self.container1_admin = core_factories.User()
        self.container1 = factories.DataContainer(
            users=[{"name": self.container1_admin["name"], "capacity": "admin"}]
        )
        self.container2 = factories.DataContainer()
        self.dataset1 = factories.Dataset(
            owner_org=self.container1["id"], visibility="private"
        )
        self.container1_request = AccessRequest(
            user_id=self.requesting_user["id"],
            object_id=self.container1["id"],
            object_type="organization",
            message="",
            role="member",
        )
        self.container2_request = AccessRequest(
            user_id=self.requesting_user["id"],
            object_id=self.container2["id"],
            object_type="organization",
            message="",
            role="member",
        )
        self.dataset_request = AccessRequest(
            user_id=self.requesting_user["id"],
            object_id=self.dataset1["id"],
            object_type="package",
            message="",
            role="member",
        )
        self.user_request_container1 = AccessRequest(
            user_id=self.pending_user["id"],
            object_id=self.pending_user["id"],
            object_type="user",
            message="",
            role="member",
            data={'default_containers': [self.container1["id"]]},
        )
        self.user_request_container2 = AccessRequest(
            user_id=self.pending_user["id"],
            object_id=self.pending_user["id"],
            object_type="user",
            message="",
            role="member",
            data={'default_containers': [self.container2["id"]]},
        )
        model.Session.add(self.container1_request)
        model.Session.add(self.container2_request)
        model.Session.add(self.dataset_request)
        model.Session.add(self.user_request_container1)
        model.Session.add(self.user_request_container2)
        model.Session.commit()

    def make_action_request(self, action, request_id, user=None, data=None, **kwargs):
        url = '/access-requests/{action}/{request_id}'.format(
            action=action, request_id=request_id
        )
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.post(url, data, extra_environ=env, **kwargs)
        return resp

    def make_list_request(self, user=None, **kwargs):
        url = '/dashboard/requests'
        env = {'REMOTE_USER': user.encode('ascii')} if user else {}
        resp = self.app.get(url=url, extra_environ=env, **kwargs)
        return resp

    def test_access_requests_reject_missing_param(self):
        self.make_action_request(
            action='reject',
            request_id=self.container1_request.id,
            user=self.container1_admin["name"],
            status=400,
            data={},
        )

    def test_access_requests_invalid_id(self):
        for action, data in [("approve", {}), ("reject", {'message': 'nope'})]:
            self.make_action_request(
                action=action,
                request_id='invalid-id',
                user=self.container1_admin["name"],
                status=404,
                data=data,
            )

    def test_access_requests_invalid_user(self):
        for action, data in [("approve", {}), ("reject", {'message': 'nope'})]:
            for user in [None, self.standard_user["name"]]:
                self.make_action_request(
                    action=action,
                    request_id=self.container1_request.id,
                    user=user,
                    status=403,
                    data=data,
                )

    def test_access_requests_approve_container_admin(self):
        mock_mailer = mock.Mock()
        with mock.patch('ckanext.unhcr.mailer.mail_user_by_id', mock_mailer):
            resp = self.make_action_request(
                action='approve',
                request_id=self.container1_request.id,
                user=self.container1_admin["name"],
                status=302,
                data={},
            )
        mock_mailer.assert_called_once()
        # standard 'you've been added to a container' email
        assert_equals(
            '[UNHCR RIDL] Membership: {}'.format(self.container1['title']),
            mock_mailer.call_args[0][1]
        )

        resp2 = resp.follow(
            extra_environ={'REMOTE_USER': self.container1_admin["name"].encode('ascii')},
            status=200
        )
        orgs = toolkit.get_action("organization_list_for_user")(
            {"user": self.requesting_user["name"]},
            {"id": self.requesting_user["name"], "permission": "read"}
        )
        assert_equals(self.container1['id'], orgs[0]['id'])
        assert_equals('approved', self.container1_request.status)
        assert_in('Access Request Approved', resp2.body)

    def test_access_requests_reject_container_admin(self):
        mock_mailer = mock.Mock()
        with mock.patch('ckanext.unhcr.mailer.mail_user_by_id', mock_mailer):
            resp = self.make_action_request(
                action='reject',
                request_id=self.container1_request.id,
                user=self.container1_admin["name"],
                status=302,
                data={'message': 'nope'},
            )
        mock_mailer.assert_called_once()
        # your request has been rejected email
        assert_equals(
            '[UNHCR RIDL] - Request for access to: "{}"'.format(self.container1['name']),
            mock_mailer.call_args[0][1]
        )

        resp2 = resp.follow(
            extra_environ={'REMOTE_USER': self.container1_admin["name"].encode('ascii')},
            status=200
        )
        orgs = toolkit.get_action("organization_list_for_user")(
            {"user": self.requesting_user["name"]},
            {"id": self.requesting_user["name"], "permission": "read"}
        )
        assert_equals(0, len(orgs))
        assert_equals('rejected', self.container1_request.status)
        assert_in('Access Request Rejected', resp2.body)

    def test_access_requests_list_invalid_user(self):
        for user in [None, self.standard_user["name"]]:
            self.make_list_request(user=user, status=403)

    def test_access_requests_list_sysadmin(self):
        resp = self.make_list_request(user=self.sysadmin['name'], status=200)
        # sysadmin can see all the requests
        assert_in(
            '/access-requests/approve/{}'.format(self.container1_request.id),
            resp.body
        )
        assert_in(
            '/access-requests/approve/{}'.format(self.container2_request.id),
            resp.body
        )
        assert_in(
            '/access-requests/approve/{}'.format(self.dataset_request.id),
            resp.body
        )
        assert_in(
            '/access-requests/approve/{}'.format(self.user_request_container1.id),
            resp.body
        )
        assert_in(
            '/access-requests/approve/{}'.format(self.user_request_container2.id),
            resp.body
        )

    def test_access_requests_list_container_admin(self):
        resp = self.make_list_request(user=self.container1_admin['name'], status=200)
        assert_in(
            '/access-requests/approve/{}'.format(self.container1_request.id),
            resp.body
        )
        assert_in(
            '/access-requests/approve/{}'.format(self.dataset_request.id),
            resp.body
        )
        assert_in(
            '/access-requests/approve/{}'.format(self.user_request_container1.id),
            resp.body
        )
        # container1_admin can't see the requests for container2
        assert_not_in(
            '/access-requests/approve/{}'.format(self.container2_request.id),
            resp.body
        )
        assert_not_in(
            '/access-requests/approve/{}'.format(self.user_request_container2.id),
            resp.body
        )
