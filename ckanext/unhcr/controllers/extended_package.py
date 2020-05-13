import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.controllers.package import PackageController
from ckanext.scheming.helpers import scheming_get_dataset_schema
from ckanext.unhcr import mailer
log = logging.getLogger(__name__)


class ExtendedPackageController(PackageController):

    # Read

    def read(self, id):
        if not toolkit.c.user:
            return toolkit.abort(403, toolkit.render('page.html'))
        return super(ExtendedPackageController, self).read(id)

    # Publish

    def publish(self, id):
        context = {'model': model, 'user': toolkit.c.user}
        dataset = toolkit.get_action('package_patch')(context, {'id': id, 'state': 'active'})
        toolkit.h.flash_success('Dataset "%s" has been published' % dataset['title'])
        toolkit.redirect_to('dataset_read', id=dataset['name'])

    # Copy

    def copy(self, id):
        context = {'model': model, 'user': toolkit.c.user}

        # Get organizations
        orgs = toolkit.get_action('organization_list_for_user')(
            context, {'permission': 'create_dataset'})
        org_ids = [org['id'] for org in orgs]

        # Check access
        if not orgs:
            message = 'Not authorized to copy dataset "%s"'
            return toolkit.abort(403, message % id)

        # Get dataset
        try:
            dataset = toolkit.get_action('package_show')(context, {'id': id})
        except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
            message = 'Not found py dataset "%s"'
            return toolkit.abort(404, message % id)

        # Extract data
        data = {}
        schema = scheming_get_dataset_schema('dataset')
        for field in schema['dataset_fields']:
            # We skip name/title
            if field['field_name'] in ['name', 'title']:
                continue
            # We skip autogenerated fields
            if field.get('form_snippet', True) is None:
                continue
            # We skip empty fields
            if field['field_name'] not in dataset:
                continue
            data[field['field_name']] = dataset[field['field_name']]
        data['type'] = 'dataset'
        data['private'] = bool(dataset.get('private'))
        if data.get('owner_org'):
            data['owner_org'] = data['owner_org'] if data['owner_org'] in org_ids else None
        data['original_dataset'] = dataset

        return self.new(data=data)

    def resource_copy(self, id, resource_id):
        context = {'model': model, 'user': toolkit.c.user}

        # Check access
        try:
            toolkit.check_access('package_update', context, {'id': id})
        except toolkit.NotAuthorized:
            message = 'Not authorized to copy resource of dataset "%s"'
            return toolkit.abort(403, message % id)

        # Get resource
        try:
            resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
        except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
            message = 'Not found resource "%s" of dataset "%s"'
            return toolkit.abort(404, message % (resource_id, id))

        # Extract data
        data = {}
        schema = scheming_get_dataset_schema('dataset')
        for field in schema['resource_fields']:
            # We skip url field (current file)
            if field['field_name'] == 'url':
                continue
            # We skip autogenerated fields
            if field.get('form_snippet', True) is None:
                continue
            if field['field_name'] in resource:
                data[field['field_name']] = resource[field['field_name']]
        data['name'] = '%s (copy)' % resource.get('name')

        return self.new_resource(id, data=data)

    # Download

    def _log_download_activity(self, context, resource_id):
        """Log a resource download activity in the activity stream
        """
        user = context['user']
        user_id = None
        user_by_name = model.User.by_name(user.decode('utf8'))
        if user_by_name is not None:
            user_id = user_by_name.id

        activity_dict = {
            'activity_type': 'download resource',
            'user_id': user_id,
            'object_id': resource_id,
            'data': {}
        }

        activity_create_context = {
            'model': model,
            'user': user_id or user,
            'defer_commit': False,
            'ignore_auth': True,
        }

        create_activity = toolkit.get_action('activity_create')
        create_activity(activity_create_context, activity_dict)

    def resource_download(self, id, resource_id, filename=None):
        """
        Wraps default `resource_download` endpoint checking
        the custom `resoruce_download` auth function
        """
        context = {'model': model, 'session': model.Session,
                   'user': toolkit.c.user, 'auth_user_obj': toolkit.c.userobj}

        # Check resource_download access
        try:
            toolkit.check_access(u'resource_download', context, {u'id': resource_id})
        except toolkit.ObjectNotFound:
            return toolkit.abort(404, toolkit._(u'Resource not found'))
        except toolkit.NotAuthorized:
            return toolkit.abort(403, toolkit._(u'Not Authorized to download the resource'))

        resp = super(ExtendedPackageController, self).resource_download(
            id, resource_id, filename=filename
        )
        self._log_download_activity(context, resource_id)
        return resp

    # Publish

    def publish_microdata(self, id):
        context = {'model': model, 'user': toolkit.c.user}
        nation = toolkit.request.params.get('nation')
        repoid = toolkit.request.params.get('repoid')

        # Get dataset
        try:
            dataset = toolkit.get_action('package_show')(context, {'id': id})
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to publish of dataset "%s"'
            return toolkit.abort(403, message % id)

        # Publish to Microdata
        error = None
        try:
            survey = toolkit.get_action('package_publish_microdata')(
                context, {'id': id, 'nation': nation, 'repoid': repoid})
        except (toolkit.NotAuthorized, RuntimeError) as exception:
            error = str(exception)

        # Show flash message and redirect
        if not error:
            message = 'Dataset "%s" published to the Microdata library at the following address: "%s"'
            toolkit.h.flash_success(message % (dataset['title'], survey['url']))
        else:
            message = 'Dataset "%s" publishing to the Microdata library is not completed for the following reason: "%s"'
            toolkit.h.flash_error(message % (dataset['title'], error))
        toolkit.redirect_to('dataset_edit', id=dataset['name'])

    def request_access(self, id):
        message = toolkit.request.params.get('message')
        if not message:
            return toolkit.abort(400, "'message' is required")

        action_context = {'model': model, 'user': toolkit.c.user}
        try:
            dataset = toolkit.get_action('package_show')(action_context, {'id': id})
        except toolkit.ObjectNotFound:
            return toolkit.abort(404, 'Dataset not found')
        except toolkit.NotAuthorized:
            return toolkit.abort(403, 'Not Authorized')

        if toolkit.h.can_download(dataset):
            toolkit.h.flash_notice(
                'You already have access to download resources from {}'.format(
                    dataset['title']
                )
            )
            return toolkit.redirect_to('dataset_read', id=dataset['id'])

        org_admins = mailer.get_request_access_email_recipients(dataset)
        for recipient in org_admins:
            subj = mailer.compose_request_access_email_subj(dataset)
            body = mailer.compose_request_access_email_body(
                recipient,
                dataset,
                toolkit.c.user,
                message,
            )
            mailer.mail_user_by_id(recipient['name'], subj, body)

        toolkit.h.flash_notice(
            'Requested access to download resources from {}'.format(
                dataset['title']
            )
        )

        return toolkit.redirect_to('dataset_read', id=dataset['id'])
