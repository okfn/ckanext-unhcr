# -*- coding: utf-8 -*-

import pytest
from ckanext.unhcr.jobs import _modify_package


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestJobs(object):

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
        assert package['date_range_start'] == '2017-01-01'
        assert package['date_range_end'] == '2017-09-01'


    def test_modify_package_date_range_after_resource_deletion(self):
        package = _modify_package({
            'date_range_start': '2017-01-01',
            'date_range_end': '2017-09-01',
            'resources': [
                {'date_range_start': '2017-01-01', 'date_range_end': '2017-06-01'},
            ]
        })
        assert package['date_range_start'] == '2017-01-01'
        assert package['date_range_end'] == '2017-06-01'


    def test_modify_package_date_range_no_resources(self):
        package = _modify_package({
            'date_range_start': None,
            'date_range_end': None,
            'resources': [],
        })
        assert package['date_range_start'] is None
        assert package['date_range_end'] is None


    # process_status

    def test_modify_package_process_status(self):
        package = _modify_package({
            'process_status': None,
            'resources': [
                {'process_status': 'cleaned'},
                {'process_status': 'anonymized'},
            ]
        })
        assert package['process_status'] == 'cleaned'


    def test_modify_package_process_status_resource_deletion(self):
        package = _modify_package({
            'process_status': 'cleaned',
            'resources': [
                {'process_status': 'anonymized'},
            ]
        })
        assert package['process_status'] == 'anonymized'


    def test_modify_package_process_status_none(self):
        package = _modify_package({
            'process_status': None,
            'resources': [
                {'process_status': 'cleaned'},
                {'process_status': 'anonymized'},
            ]
        })
        assert package['process_status'] == 'cleaned'


    def test_modify_package_process_status_no_resources(self):
        package = _modify_package({
            'process_status': 'anonymized',
            'resources': [],
        })
        assert package['process_status'] is None


    def test_modify_package_process_status_default(self):
        package = _modify_package({
            'process_status': None,
            'resources': [],
        })
        assert package['process_status'] is None

    # privacy

    def test_modify_package_privacy(self):
        package = _modify_package({
            'identifiability': None,
            'visibility': 'public',
            'resources': [
                {'identifiability': 'anonymized_public'},
            ]
        })
        assert package['identifiability'] == 'anonymized_public'
        assert package['visibility'] == 'public'


    def test_modify_package_privacy_private_false(self):
        package = _modify_package({
            'identifiability': None,
            'visibility': 'public',
            'resources': [
                {'identifiability': 'anonymized_public'},
            ]
        })
        assert package['identifiability'] == 'anonymized_public'
        assert package['visibility'] == 'public'


    def test_modify_package_privacy_resource_addition(self):
        package = _modify_package({
            'identifiability': 'anonymized_public',
            'visibility': 'public',
            'resources': [
                {'identifiability': 'anonymized_public'},
                {'identifiability': 'personally_identifiable'},
            ]
        })
        assert package['identifiability'] == 'personally_identifiable'
        assert package['visibility'] == 'restricted'


    def test_modify_package_privacy_package_none(self):
        package = _modify_package({
            'identifiability': None,
            'visibility': 'public',
            'resources': [
                {'identifiability': 'personally_identifiable'},
            ]
        })
        assert package['identifiability'] == 'personally_identifiable'
        assert package['visibility'] == 'restricted'


    def test_modify_package_privacy_default(self):
        package = _modify_package({
            'identifiability': None,
            'visibility': 'public',
            'resources': []
        })
        assert package['identifiability'] is None
        assert package['visibility'] == 'public'
