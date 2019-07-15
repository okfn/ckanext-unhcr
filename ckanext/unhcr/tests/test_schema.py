from nose.plugins.attrib import attr
from nose.tools import assert_equals, assert_raises

from ckan.plugins.toolkit import ValidationError
from ckan.tests.helpers import call_action, FunctionalTestBase


from ckanext.unhcr.tests import base, factories


class TestResourceFields(base.FunctionalTestBase):

    def test_file_ment_fields(self):

        dataset = factories.Dataset()

        resource = {
            'name': 'Test File attachment',
            'url': 'http://example.com/doc.pdf',
            'format': 'PDF',
            'description': 'Some description',
            'type': 'attachment',
            'file_type': 'report',
        }

        dataset['resources'] = [resource]

        updated_dataset = call_action('package_update', {}, **dataset)

        for field in resource.keys():
            assert_equals(
                updated_dataset['resources'][0][field], resource[field])

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

        with assert_raises(ValidationError) as e:
            call_action('package_update', {}, **dataset)

        errors = e.exception.error_dict['resources'][0]

        for field in ['identifiability', 'date_range_end',
                      'version', 'date_range_start', 'process_status']:
            error = errors[field]

            assert_equals(error, ['Missing value'])

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

        with assert_raises(ValidationError) as e:
            call_action('package_update', {}, **dataset)

        errors = e.exception.error_dict['resources'][1]

        for field in ['identifiability', 'date_range_end',
                      'version', 'date_range_start', 'process_status']:
            error = errors[field]

            assert_equals(error, ['Missing value'])

