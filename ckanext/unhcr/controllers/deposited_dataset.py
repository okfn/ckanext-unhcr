import logging
import string
import random
from ckan import model
import ckan.plugins.toolkit as toolkit
import ckan.lib.helpers as lib_helpers
from ckanext.unhcr import helpers, mailer
log = logging.getLogger(__name__)


# Module API

# TODO: add messages to email notifications
# TODO: extract duplication (get_curation/authorize) from methods
class DepositedDatasetController(toolkit.BaseController):

    # Curation

    def approve(self, dataset_id):
        user_id = getattr(toolkit.c.userobj, 'id', None)

        # Get curation data
        try:
            context, dataset, curation = _get_curation_data(dataset_id, user_id)
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to read dataset "%s"'
            return toolkit.abort(403, message % dataset_id)

        # Authorize context
        if 'approve' not in curation['actions']:
            message = 'Not authorized to approve dataset "%s"'
            return toolkit.abort(403, message % dataset_id)
        context['ignore_auth'] = True

        # Update dataset
        try:
            # We also set type in context to allow type switching by ckan patch
            dataset = helpers.convert_deposited_dataset_to_regular_dataset(dataset)
            dataset = toolkit.get_action('package_update')(
                    dict(context.items() + {'type': dataset['type']}.items()), dataset)
        except toolkit.ValidationError as error:
            message = 'Deposited dataset "%s" is invalid\n(validation error summary: %s)'
            return toolkit.abort(403, message % (id, error.error_summary))

        # Update activity stream
        message = toolkit.request.params.get('message')
        helpers.create_curation_activity('dataset_approved', dataset['id'],
            dataset['name'], user_id, message=message)

        # Send notification email
        message = toolkit.request.params.get('message')
        if curation['state'] == 'submitted':
            recipient = curation['contacts']['depositor']
        elif curation['state'] == 'review':
            recipient = curation['contacts']['curator']
        if recipient:
            subj = mailer.compose_curation_email_subj(dataset)
            body = mailer.compose_curation_email_body(
                dataset, curation, recipient['title'], 'approve', message=message)
            mailer.mail_user_by_id(recipient['name'], subj, body)

        # Show flash message and redirect
        message = 'Datasest "%s" approved and moved to the destination data container'
        toolkit.h.flash_success(message % dataset['title'])
        toolkit.redirect_to('deposited-dataset_read', id=dataset['name'])

    def assign(self, dataset_id):
        user_id = getattr(toolkit.c.userobj, 'id', None)

        # Get curation data
        try:
            context, dataset, curation = _get_curation_data(dataset_id, user_id)
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to read dataset "%s"'
            return toolkit.abort(403, message % dataset_id)

        # Authorize context
        if 'assign' not in curation['actions']:
            message = 'Not authorized to assign Curator to dataset "%s"'
            return toolkit.abort(403, message % dataset_id)
        context['ignore_auth'] = True

        # Update dataset
        curator_id = toolkit.request.params.get('curator_id')
        if curator_id:
            dataset['curator_id'] = curator_id
        else:
            dataset.pop('curator_id', None)
        try:
            dataset = toolkit.get_action('package_update')(context, dataset)
        except toolkit.ValidationError:
            message = 'Curator is invalid'
            return toolkit.abort(403, message)

        # Update activity stream
        if curator_id:
            context = _get_context(ignore_auth=True)
            curator = toolkit.get_action('user_show')(context, {'id': curator_id})
            helpers.create_curation_activity('curator_assigned', dataset['id'],
                dataset['name'], user_id, curator_name=curator['name'])
        else:
            helpers.create_curation_activity('curator_removed', dataset['id'],
                dataset['name'], user_id)

        # Send notification email
        recipient = None
        if curator_id:
            action = 'assign'
            recipient = {'name': curator['id'], 'title': curator['display_name']}
        elif curation['contacts']['curator']:
            action = 'assign_remove'
            recipient = curation['contacts']['curator']
        if recipient:
            subj = mailer.compose_curation_email_subj(dataset)
            body = mailer.compose_curation_email_body(
                dataset, curation, recipient['title'], action)
            mailer.mail_user_by_id(recipient['name'], subj, body)

        # Show flash message and redirect
        message = 'Datasest "%s" Curator updated'
        toolkit.h.flash_success(message % dataset['title'])
        toolkit.redirect_to('deposited-dataset_read', id=dataset['name'])

    def request_changes(self, dataset_id):
        user_id = getattr(toolkit.c.userobj, 'id', None)

        # Get curation data
        try:
            context, dataset, curation = _get_curation_data(dataset_id, user_id)
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to read dataset "%s"'
            return toolkit.abort(403, message % dataset_id)

        # Authorize context
        if 'request_changes' not in curation['actions']:
            message = 'Not authorized to request changes of dataset "%s"'
            return toolkit.abort(403, message % dataset_id)
        context['ignore_auth'] = True

        # Update dataset
        if dataset['curation_state'] == 'review':
            dataset['curation_state'] = 'submitted'
        else:
            dataset['curation_state'] = 'draft'
        dataset = toolkit.get_action('package_update')(context, dataset)

        # Update activity stream
        message = toolkit.request.params.get('message')
        helpers.create_curation_activity('changes_requested', dataset['id'],
                dataset['name'], user_id, message=message)

        # Send notification email
        message = toolkit.request.params.get('message')
        if curation['state'] == 'submitted':
            recipient = curation['contacts']['depositor']
        elif curation['state'] == 'review':
            recipient = curation['contacts']['curator']
        if recipient:
            subj = mailer.compose_curation_email_subj(dataset)
            body = mailer.compose_curation_email_body(
                dataset, curation, recipient['title'], 'request_changes', message=message)
            mailer.mail_user_by_id(recipient['name'], subj, body)

        # Show flash message and redirect
        message = 'Datasest "%s" changes requested'
        toolkit.h.flash_success(message % dataset['title'])
        toolkit.redirect_to('deposited-dataset_read', id=dataset['name'])

    def request_review(self, dataset_id):
        user_id = getattr(toolkit.c.userobj, 'id', None)

        # Get curation data
        try:
            context, dataset, curation = _get_curation_data(dataset_id, user_id)
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to read dataset "%s"'
            return toolkit.abort(403, message % dataset_id)

        # Authorize context
        if 'request_review' not in curation['actions']:
            message = 'Not authorized to request review of dataset "%s"'
            return toolkit.abort(403, message % dataset_id)
        context['ignore_auth'] = True

        # Update dataset
        dataset['curation_state'] = 'review'
        dataset = toolkit.get_action('package_update')(context, dataset)

        # Update activity stream
        message = toolkit.request.params.get('message')
        context = _get_context(ignore_auth=True)
        depositor = toolkit.get_action('user_show')(context, {'id': dataset['creator_user_id']})
        helpers.create_curation_activity('final_review_requested', dataset['id'],
            dataset['name'], user_id, message=message, depositor_name=depositor['name'])

        # Send notification email
        message = toolkit.request.params.get('message')
        depositor = curation['contacts']['depositor']
        subj = mailer.compose_curation_email_subj(dataset)
        body = mailer.compose_curation_email_body(
            dataset, curation, depositor['title'], 'request_review', message=message)
        mailer.mail_user_by_id(depositor['name'], subj, body)

        # Show flash message and redirect
        message = 'Datasest "%s" review requested'
        toolkit.h.flash_success(message % dataset['title'])
        toolkit.redirect_to('deposited-dataset_read', id=dataset['name'])

    def reject(self, dataset_id):
        user_id = getattr(toolkit.c.userobj, 'id', None)

        # Get curation data
        try:
            context, dataset, curation = _get_curation_data(dataset_id, user_id)
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to read dataset "%s"'
            return toolkit.abort(403, message % dataset_id)

        # Authorize context
        if 'reject' not in curation['actions']:
            message = 'Not authorized to reject dataset "%s"'
            return toolkit.abort(403, message % dataset_id)
        context['ignore_auth'] = True

        # Delete rejected dataset, but first update its name so it can be reused
        new_name = _get_rejected_dataset_name(dataset['name'])
        toolkit.get_action('package_patch')(context, {'id': dataset_id, 'name': new_name})
        toolkit.get_action('package_delete')(context, {'id': dataset_id})

        # Update activity stream
        message = toolkit.request.params.get('message')
        helpers.create_curation_activity('dataset_rejected', dataset['id'],
            dataset['name'], user_id, message=message)

        # Send notification email
        message = toolkit.request.params.get('message')
        depositor = curation['contacts']['depositor']
        subj = mailer.compose_curation_email_subj(dataset)
        body = mailer.compose_curation_email_body(
            dataset, curation, depositor['title'], 'reject', message=message)
        mailer.mail_user_by_id(depositor['name'], subj, body)

        # Show flash message and redirect
        message = 'Datasest "%s" rejected'
        toolkit.h.flash_error(message % dataset['title'])
        toolkit.redirect_to('data-container_read', id='data-deposit')

    def submit(self, dataset_id):
        user_id = getattr(toolkit.c.userobj, 'id', None)

        # Get curation data
        try:
            context, dataset, curation = _get_curation_data(dataset_id, user_id)
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to read dataset "%s"'
            return toolkit.abort(403, message % dataset_id)

        # Authorize context
        if 'submit' not in curation['actions']:
            message = 'Not authorized to submit dataset "%s"'
            return toolkit.abort(403, message % dataset_id)
        context['ignore_auth'] = True

        # Update dataset
        dataset['curation_state'] = 'submitted'
        dataset = toolkit.get_action('package_update')(context, dataset)

        # Update activity stream
        message = toolkit.request.params.get('message')
        helpers.create_curation_activity('dataset_submitted', dataset['id'],
            dataset['name'], user_id, message=message)

        # Send notification email
        message = toolkit.request.params.get('message')
        curator = curation['contacts']['curator']
        # We don't bother all curators if someone is already assigned
        users = [curator] if curator else helpers.get_data_curation_users()
        for user in users:
            subj = mailer.compose_curation_email_subj(dataset)
            body = mailer.compose_curation_email_body(
                dataset, curation, user['display_name'], 'submit', message=message)
            mailer.mail_user_by_id(user['id'], subj, body)

        # Show flash message and redirect
        message = 'Datasest "%s" submitted'
        toolkit.h.flash_success(message % dataset['title'])
        toolkit.redirect_to('deposited-dataset_read', id=dataset['name'])

    def withdraw(self, dataset_id):
        user_id = getattr(toolkit.c.userobj, 'id', None)

        # Get curation data
        try:
            context, dataset, curation = _get_curation_data(dataset_id, user_id)
        except (toolkit.ObjectNotFound, toolkit.NotAuthorized):
            message = 'Not authorized to read dataset "%s"'
            return toolkit.abort(403, message % dataset_id)

        # Authorize context
        if 'withdraw' not in curation['actions']:
            message = 'Not authorized to withdraw dataset "%s"'
            return toolkit.abort(403, message % dataset_id)
        context['ignore_auth'] = True

        # Delete withdrawn dataset, but first update its name so it can be reused
        new_name = _get_withdrawn_dataset_name(dataset['name'])
        toolkit.get_action('package_patch')(context, {'id': dataset_id, 'name': new_name})
        toolkit.get_action('package_delete')(context, {'id': dataset_id})

        # Update activity stream
        message = toolkit.request.params.get('message')
        helpers.create_curation_activity('dataset_withdrawn', dataset['id'],
            dataset['name'], user_id, message=message)

        # Send notification email
        message = toolkit.request.params.get('message')
        for user in helpers.get_data_curation_users():
            subj = mailer.compose_curation_email_subj(dataset)
            body = mailer.compose_curation_email_body(
                dataset, curation, user['display_name'], 'withdraw', message=message)
            mailer.mail_user_by_id(user['id'], subj, body)

        # Show flash message and redirect
        message = 'Datasest "%s" withdrawn'
        toolkit.h.flash_error(message % dataset['title'])
        toolkit.redirect_to('data-container_read', id='data-deposit')

    # Activity

    def activity(self, dataset_id):
        '''Render package's curation activity stream page.'''

        context = _get_context()
        data_dict = {'id': dataset_id}
        try:
            # We check for package_show because
            # in some states package_update can be forbidden
            toolkit.check_access('package_show', context, data_dict)
            toolkit.c.pkg_dict = toolkit.get_action('package_show')(context, data_dict)
            toolkit.c.pkg = context['package']
            toolkit.c.package_activity_stream = toolkit.get_action(
                'package_activity_list_html')(
                context, {
                    'id': dataset_id,
                    'get_curation_activities': True
                })
        except toolkit.ObjectNotFound:
            toolkit.abort(404, toolkit._('Dataset not found'))
        except toolkit.NotAuthorized:
            toolkit.abort(403, toolkit._('Unauthorized to read the curation activity for dataset %s') % dataset_id)

        return toolkit.render('package/activity.html', {'dataset_type': 'deposited-dataset'})



# Internal

def _get_curation_data(dataset_id, user_id):
    context = _get_context()
    dataset = _get_deposited_dataset(context, dataset_id)
    curation = helpers.get_deposited_dataset_user_curation_status(dataset, user_id)
    return context, dataset, curation


def _get_context(**patch):
    context = {'model': model, 'user': toolkit.c.user}
    context.update(patch)
    return context


def _get_deposited_dataset(context, dataset_id):
    deposit = helpers.get_data_deposit()
    dataset = toolkit.get_action('package_show')(context, {'id': dataset_id})
    if dataset.get('owner_org') != deposit['id']:
        message = 'Deposited dataset "%s" not found' % dataset_id
        raise toolkit.ObjectNotFound(message)
    return dataset


def _get_rejected_dataset_name(name):
    return _get_deleted_dataset_name(name, 'rejected')


def _get_withdrawn_dataset_name(name):
    return _get_deleted_dataset_name(name, 'withdrawn')


def _get_deleted_dataset_name(name, operation='rejected'):
    rand_chars = ''.join(
        random.choice(
            string.ascii_lowercase + string.digits) for _ in range(4)
    )
    return '{}-{}-{}'.format(name, operation, rand_chars)
