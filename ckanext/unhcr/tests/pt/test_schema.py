# -*- coding: utf-8 -*-

import pytest
from ckan.plugins import toolkit
from ckan.tests.helpers import call_action
from ckan import model
from ckantoolkit.tests import factories as core_factories
from ckanext.unhcr.tests import factories


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestResourceFields(object):
    def setup(self):
        self.sysadmin = core_factories.Sysadmin(name='sysadmin', id='sysadmin')

    def test_file_ment_fields(self):

        dataset = factories.Dataset()

        resource = {
            'name': 'Test File attachment',
            'url': 'http://example.com/doc.pdf',
            'format': 'PDF',
            'description': 'Some description',
            'type': 'attachment',
            'file_type': 'report',
            'url_type': 'upload',
        }

        dataset['resources'] = [resource]

        updated_dataset = call_action(
            'package_update',
            {'user': self.sysadmin['name']},
            **dataset
        )

        for field in [k for k in resource.keys() if k != 'url']:
            assert updated_dataset['resources'][0][field] == resource[field]
        assert (
            updated_dataset['resources'][0]['url'].split('/')[-1]
            == resource['url'].split('/')[-1]
        )
        assert 'date_range_start' not in updated_dataset['resources'][0]

    def test_data_file_fields(self):

        dataset = factories.Dataset()

        resource = {
            'name': 'Test Data file',
            'url': 'http://example.com/data.csv',
            'format': 'CSV',
            'description': 'Some data file',
            'type': 'data',
            'file_type': 'microdata',
        }

        dataset['resources'] = [resource]

        with pytest.raises(toolkit.ValidationError) as e:
            call_action('package_update', {'user': self.sysadmin['name']}, **dataset)

        errors = e.value.error_dict['resources'][0]

        for field in ['identifiability', 'date_range_end',
                      'version', 'date_range_start', 'process_status']:
            error = errors[field]

            assert error == ['Missing value']

    def test_both_types_data_fields_missing(self):

        dataset = factories.Dataset()

        resource1 = {
            'name': 'Test File attachment',
            'url': 'http://example.com/doc.pdf',
            'format': 'PDF',
            'description': 'Some description',
            'type': 'attachment',
            'file_type': 'report',
        }
        resource2 = {
            'name': 'Test Data file',
            'url': 'http://example.com/data.csv',
            'format': 'CSV',
            'description': 'Some data file',
            'type': 'data',
            'file_type': 'microdata',
        }

        dataset['resources'] = [resource1, resource2]

        with pytest.raises(toolkit.ValidationError) as e:
            call_action('package_update', {'user': self.sysadmin['name']}, **dataset)

        errors = e.value.error_dict['resources'][1]

        for field in ['identifiability', 'date_range_end',
                      'version', 'date_range_start', 'process_status']:
            error = errors[field]

            assert error == ['Missing value']
