# -*- coding: utf-8 -*-

import pytest
from ckan import model
from ckan.plugins import toolkit
from ckan.tests import helpers as core_helpers
from ckanext.unhcr.tests import factories, mocks


@pytest.mark.usefixtures('clean_db', 'unhcr_migrate')
class TestResourceUpload(object):

    def test_upload_present(self):

        dataset = factories.Dataset()

        resource = factories.Resource(
            package_id=dataset['id'],
            upload=mocks.FakeFileStorage(),
            url = "http://fakeurl/test.txt",
            url_type='upload',
        )

        assert (
            resource['url'] ==
            '{}/dataset/{}/resource/{}/download/test.txt'.format(
                toolkit.config.get('ckan.site_url').rstrip('/'),
                dataset['id'],
                resource['id']
            )
        )

    def test_upload_present_after_update(self):

        dataset = factories.Dataset()

        resource = factories.Resource(
            package_id=dataset['id'],
            upload=mocks.FakeFileStorage(),
            url = "http://fakeurl/test.txt",
            url_type='upload',
        )

        resource['name'] = 'updated'
        updated_resource = core_helpers.call_action(
            'resource_update',
            {'ignore_auth': True},
            **resource
        )

        assert updated_resource['name'] == 'updated'

        assert (
            updated_resource['url'] ==
            '{}/dataset/{}/resource/{}/download/test.txt'.format(
                toolkit.config['ckan.site_url'].rstrip('/'),
                dataset['id'],
                resource['id']
            )
        )

    def test_upload_external_url_data(self):

        dataset = factories.Dataset()

        with pytest.raises(toolkit.ValidationError) as exc:
            factories.Resource(
                type='data',
                package_id=dataset['id'],
                url='https://example.com/some.data.csv'
            )
        assert exc.value.error_dict.keys() == ['url']

        assert (
            exc.value.error_dict['url'] ==
            ['All data resources require an uploaded file']
        )

    def test_upload_external_url_attachment(self):
        dataset = factories.Dataset()
        resource = factories.Resource(
            type='attachment',
            package_id=dataset['id'],
            url='https://example.com/some.data.csv',
            file_type='other'
        )

        # tbh, the main thing we're testing here is that the line above
        # runs without throwing a ValidationError
        # but I suppose we should assert _something_
        assert resource['url'] == 'https://example.com/some.data.csv'

    def test_upload_missing(self):

        dataset = factories.Dataset()

        with pytest.raises(toolkit.ValidationError) as exc:
            factories.Resource(package_id=dataset['id'])

        assert exc.value.error_dict.keys() == ['url']

        assert (
            exc.value.error_dict['url'] ==
            ['All data resources require an uploaded file']
        )
