# -*- coding: utf-8 -*-

import mock
import pytest
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestCollaboratorsActions(object):

    @mock.patch('ckanext.unhcr.mailer.core_mailer.mail_user')
    def test_collaborators_actions_email_notification(self, mock_mail_user):
        dataset = factories.Dataset()
        user = core_factories.User()
        capacity = 'editor'

        member = core_helpers.call_action(
            'package_collaborator_create',
            id=dataset['id'],
            user_id=user['id'],
            capacity=capacity
        )
        assert mock_mail_user.call_count == 1
        mock_mail_user.reset_mock()

        core_helpers.call_action(
            'package_collaborator_delete',
            id=dataset['id'],
            user_id=user['id']
        )
        assert mock_mail_user.call_count == 1
