# -*- coding: utf-8 -*-

import pytest


@pytest.mark.usefixtures(
    'clean_db', 'clean_index', 'with_request_context', 'unhcr_migrate'
)
class TestExample(object):

    def test_example(self):
        print(sys.getrecursionlimit())
        assert False

