from ckan.plugins import toolkit
from nose.plugins.attrib import attr
from nose.tools import assert_raises, assert_equals
from ckanext.unhcr.tests import base, factories
from ckanext.unhcr import utils


class TestUtils(base.FunctionalTestBase):

    # Misc

    def test_normalize_list(self):
        value = ['name1', 'name2']
        assert_equals(utils.normalize_list(value), value)
        assert_equals(utils.normalize_list('{name1,name2}'), value)
        assert_equals(utils.normalize_list(''), [])
