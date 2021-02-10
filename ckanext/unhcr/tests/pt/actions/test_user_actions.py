# -*- coding: utf-8 -*-

import pytest
from ckan.plugins import toolkit
from ckan.tests.helpers import call_action
from ckantoolkit.tests import factories as core_factories


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
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
