import os
import pylons
from ckan import model
from ckan.plugins import toolkit
from paste.registry import Registry
from nose.plugins.attrib import attr
from ckan.tests import factories as core_factories
from nose.tools import assert_raises, assert_equals
from ckan.tests.helpers import call_action, FunctionalTestBase
from ckanext.unhcr.tests import factories
from ckanext.unhcr import validators
from ckanext.unhcr.jobs import _modify_package


class TestJobs(FunctionalTestBase):

    # Config

    @classmethod
    def setup_class(cls):

        # Hack because the hierarchy extension uses c in some methods
        # that are called outside the context of a web request
        c = pylons.util.AttribSafeContextObj()
        registry = Registry()
        registry.prepare()
        registry.register(pylons.c, c)

        super(TestJobs, cls).setup_class()


    # date_range

    def test_modify_package_date_range(self):
        package = _modify_package({
            'date_range_start': None,
            'date_range_end': None,
            'resources': [
                {'date_range_start': '2017-01-01', 'date_range_end': '2017-06-01'},
                {'date_range_start': '2017-03-01', 'date_range_end': '2017-09-01'},
            ]
        })
        assert_equals(package['date_range_start'], '2017-01-01')
        assert_equals(package['date_range_end'], '2017-09-01')


    def test_modify_package_date_range_after_resource_deletion(self):
        package = _modify_package({
            'date_range_start': '2017-01-01',
            'date_range_end': '2017-09-01',
            'resources': [
                {'date_range_start': '2017-01-01', 'date_range_end': '2017-06-01'},
            ]
        })
        assert_equals(package['date_range_start'], '2017-01-01')
        assert_equals(package['date_range_end'], '2017-06-01')


    def test_modify_package_date_range_no_resources(self):
        package = _modify_package({
            'date_range_start': None,
            'date_range_end': None,
            'resources': [],
        })
        assert_equals(package['date_range_start'], None)
        assert_equals(package['date_range_end'], None)


    # process_status

    def test_modify_package_process_status(self):
        package = _modify_package({
            'process_status': None,
            'resources': [
                {'process_status': 'cleaned'},
                {'process_status': 'anonymized'},
            ]
        })
        assert_equals(package['process_status'], 'cleaned')


    def test_modify_package_process_status_resource_deletion(self):
        package = _modify_package({
            'process_status': 'cleaned',
            'resources': [
                {'process_status': 'anonymized'},
            ]
        })
        assert_equals(package['process_status'], 'anonymized')


    def test_modify_package_process_status_none(self):
        package = _modify_package({
            'process_status': None,
            'resources': [
                {'process_status': 'cleaned'},
                {'process_status': 'anonymized'},
            ]
        })
        assert_equals(package['process_status'], 'cleaned')


    def test_modify_package_process_status_no_resources(self):
        package = _modify_package({
            'process_status': 'anonymized',
            'resources': [],
        })
        assert_equals(package['process_status'], None)


    def test_modify_package_process_status_default(self):
        package = _modify_package({
            'process_status': None,
            'resources': [],
        })
        assert_equals(package['process_status'], None)

    # privacy

    def test_modify_package_privacy(self):
        package = _modify_package({
            'identifiability': None,
            'private': False,
            'resources': [
                {'identifiability': 'anonymized_public'},
            ]
        })
        assert_equals(package['identifiability'], 'anonymized_public')
        assert_equals(package['private'], False)


    def test_modify_package_privacy_private_false(self):
        package = _modify_package({
            'identifiability': None,
            'private': False,
            'resources': [
                {'identifiability': 'anonymized_public'},
            ]
        })
        assert_equals(package['identifiability'], 'anonymized_public')
        assert_equals(package['private'], False)


    def test_modify_package_privacy_resource_addition(self):
        package = _modify_package({
            'identifiability': 'anonymized_public',
            'private': False,
            'resources': [
                {'identifiability': 'anonymized_public'},
                {'identifiability': 'personally_identifiable'},
            ]
        })
        assert_equals(package['identifiability'], 'personally_identifiable')
        assert_equals(package['private'], True)


    def test_modify_package_privacy_package_none(self):
        package = _modify_package({
            'identifiability': None,
            'private': False,
            'resources': [
                {'identifiability': 'personally_identifiable'},
            ]
        })
        assert_equals(package['identifiability'], 'personally_identifiable')
        assert_equals(package['private'], True)


    def test_modify_package_privacy_default(self):
        package = _modify_package({
            'identifiability': None,
            'private': False,
            'resources': []
        })
        assert_equals(package['identifiability'], None)
        assert_equals(package['private'], False)
