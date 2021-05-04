# -*- coding: utf-8 -*-

import logging
from flask import Blueprint
import ckan.logic as logic
from ckan import model
import ckan.lib.navl.dictization_functions as dict_fns
import ckan.logic.action.get as get_core
import ckan.logic.action.patch as patch_core
import ckan.logic.action.delete as delete_core
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr import helpers
from ckanext.unhcr import mailer
from ckanext.unhcr.utils import require_user
log = logging.getLogger(__name__)


unhcr_data_container_blueprint = Blueprint(
    'unhcr_data_container',
    __name__,
    url_prefix=u'/data-container'
)


def _parse_form(form):
    return logic.clean_dict(
        dict_fns.unflatten(
            logic.tuplize_dict(
                logic.parse_params(form)
            )
        )
    )


def _raise_not_authz_or_not_pending(container_id):

    # check auth with toolkit.check_access
    toolkit.check_access('sysadmin', {'model': model})

    # check org exists and it's pending with organization_show
    org_dict = toolkit.get_action('organization_show')({}, {'id': container_id})
    if org_dict.get('state') != 'approval_needed':
        raise toolkit.ObjectNotFound('Data container "{}" not found'.format(container_id))


@require_user
def approve(container_id):
    context = {'model': model, 'user': toolkit.c.user}

    # check access and state
    _raise_not_authz_or_not_pending(container_id)

    # organization_patch state=active
    org_dict = patch_core.organization_patch({}, {'id': container_id, 'state': 'active'})

    # send approve email
    for member in get_core.member_list(context, {'id': org_dict['id']}):
        user = model.User.get(member[0])
        if user and user.email:
            subj = mailer.compose_container_email_subj(org_dict, event='approval')
            body = mailer.compose_container_email_body(org_dict, user, event='approval')
            mailer.mail_user(user, subj, body)

    # show flash message and redirect
    toolkit.h.flash_success(u'Data container "{}" approved'.format(org_dict['title']))
    return toolkit.redirect_to('data-container_read', id=container_id)


@require_user
def reject(container_id):
    context = {'model': model, 'user': toolkit.c.user}

    # check access and state
    _raise_not_authz_or_not_pending(container_id)

    # send rejection email
    org_dict = get_core.organization_show({'model': model}, {'id': container_id})
    for member in get_core.member_list(context, {'id': org_dict['id']}):
        user = model.User.get(member[0])
        if user and user.email:
            subj = mailer.compose_container_email_subj(org_dict, event='rejection')
            body = mailer.compose_container_email_body(org_dict, user, event='rejection')
            mailer.mail_user(user, subj, body)

    # call organization_purge
    delete_core.organization_purge({'model': model}, {'id': container_id})

    # show flash message and redirect
    toolkit.h.flash_error(u'Data container "{}" rejected'.format(org_dict['title']))
    return toolkit.redirect_to('data-container_index')


@require_user
def membership():
    context = {'model': model, 'user': toolkit.c.user}
    username = toolkit.request.params.get('username')

    # Check access
    try:
        toolkit.check_access('sysadmin', context)
    except toolkit.NotAuthorized:
        message = 'Not authorized to manage membership'
        return toolkit.abort(403, message)

    # Get users
    users = toolkit.get_action('user_list')(
        context, {'order_by': 'display_name'})
    users = [u for u in users if not u['external']]

    # Get user
    user = None
    if username:
        try:
            user = toolkit.get_action('user_show')(context, {'id': username})
            deposit = helpers.get_data_deposit()
        except toolkit.ObjectNotFound:
            message = 'User "%s" not found'
            toolkit.h.flash_success(message % username)
            return toolkit.redirect_to('unhcr_data_container.membership')

    # Containers
    containers = []
    if user:
        containers = toolkit.get_action('organization_list_all_fields')(context, {})
        containers = filter(lambda cont: cont['name'] != deposit['name'], containers)

    # Roles
    roles = []
    if user:
        roles = [
            {'name': 'admin', 'title': 'Admin'},
            {'name': 'editor', 'title': 'Editor'},
            {'name': 'member', 'title': 'Member'},
        ]

    # Get user containers
    user_containers = []
    if user:
        action = 'organization_list_for_user'
        user_containers = toolkit.get_action(action)(context, {'id': username})
        user_containers = list(
            filter(lambda cont: cont['name'] != deposit['name'], user_containers)
        )

    for role in roles:
        role['total'] = len([
            uc for uc in user_containers if uc['capacity'] == role['name']
        ])

    return toolkit.render('organization/membership.html', {
        'membership': {
            'users': users,
            'user': user,
            'containers': containers,
            'roles': roles,
            'user_containers': user_containers,
        }
    })


@require_user
def membership_add():
    form_data = _parse_form(toolkit.request.form)
    context = {'model': model, 'user': toolkit.c.user}
    username = form_data.get('username')
    contnames = form_data.get('contnames')
    if type(contnames) != list:
        contnames = [contnames]
    role = form_data.get('role')

    # Check access
    try:
        toolkit.check_access('sysadmin', context)
    except toolkit.NotAuthorized:
        message = 'Not authorized to add membership'
        return toolkit.abort(403, message)

    # Add membership
    containers = []
    for contname in contnames:
        try:
            container = toolkit.get_action('organization_show')(context, {'id': contname})
            data_dict = {'id': contname, 'username': username, 'role': role, 'not_notify': True}
            toolkit.get_action('organization_member_create')(context, data_dict)
            containers.append(container)
        except (toolkit.ObjectNotFound, toolkit.ValidationError):
            message = 'User "%s" NOT added to the following data container: "%s"'
            toolkit.h.flash_error(message % (username, contname))

    # Notify by flash
    titles = ['"%s"' % cont.get('title', cont['name']) for cont in containers]
    message = 'User "%s" added to the following data containers: %s'
    toolkit.h.flash_success(message % (username, ', '.join(titles)))

    # Notify by email
    user = toolkit.get_action('user_show')(context, {'id': username})
    subj = mailer.compose_membership_email_subj({'title': 'multiple containers'})
    body = mailer.compose_membership_email_body(containers, user, 'create_multiple')
    mailer.mail_user_by_id(username, subj, body)

    # Redirect
    return toolkit.redirect_to('unhcr_data_container.membership', username=username)


@require_user
def membership_remove():
    context = {'model': model, 'user': toolkit.c.user}
    username = toolkit.request.params.get('username')
    contname = toolkit.request.params.get('contname')

    # Check access
    try:
        toolkit.check_access('sysadmin', context)
    except toolkit.NotAuthorized:
        message = 'Not authorized to remove membership'
        return toolkit.abort(403, message)

    # Remove membership
    try:
        data_dict = {'id': contname, 'user_id': username}
        container = toolkit.get_action('organization_member_delete')(context, data_dict)
    except (toolkit.ObjectNotFound, toolkit.ValidationError):
        message = 'User, container or role not found'
        toolkit.h.flash_error(message)
        return toolkit.redirect_to('unhcr_data_container.membership', username=username)

    # Show flash message and redirect
    message = 'User "%s" removed from the data container "%s"'
    toolkit.h.flash_error(message % (username, contname))
    return toolkit.redirect_to('unhcr_data_container.membership', username=username)


@require_user
def request_access(container_id):
    message = toolkit.request.form.get('message')

    deposit = helpers.get_data_deposit()
    if container_id == deposit['id']:
        return toolkit.abort(403, 'Not Authorized')

    action_context = {'model': model, 'user': toolkit.c.user}
    try:
        container = toolkit.get_action('organization_show')(
            action_context, {'id': container_id}
        )
    except toolkit.ObjectNotFound:
        return toolkit.abort(404, 'Dataset not found')
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not Authorized')

    if toolkit.c.userobj.id in [u['id'] for u in container['users']]:
        toolkit.h.flash_notice(
            'You are already a member of {}'.format(
                container['display_name']
            )
        )
        return toolkit.redirect_to('data-container_read', id=container_id)

    try:
        toolkit.get_action('access_request_create')(
            action_context, {
                'object_id': container['id'],
                'object_type': 'organization',
                'message': message,
                'role': 'member',
            }
        )
    except toolkit.ObjectNotFound as e:
        return toolkit.abort(404, str(e))
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not Authorized')
    except toolkit.ValidationError as e:
        if e.error_dict and 'message' in e.error_dict:
            return toolkit.abort(
                400,
                e.error_dict['message'][0].replace('organization', 'container')
            )
        return toolkit.abort(400, 'Bad Request')

    org_admins = mailer.get_container_request_access_email_recipients(container)
    for recipient in org_admins:
        subj = mailer.compose_container_request_access_email_subj(container)
        body = mailer.compose_request_access_email_body(
            'container',
            recipient,
            container,
            toolkit.c.userobj,
            message
        )
        toolkit.enqueue_job(mailer.mail_user_by_id, [recipient['name'], subj, body])

    toolkit.h.flash_success(
        'Requested access to container {}'.format(
            container['display_name']
        )
    )
    return toolkit.redirect_to('data-container_read', id=container_id)


unhcr_data_container_blueprint.add_url_rule(
    rule=u'/<container_id>/approve',
    view_func=approve,
    methods=['GET',],
)
unhcr_data_container_blueprint.add_url_rule(
    rule=u'/<container_id>/reject',
    view_func=reject,
    methods=['GET',],
)
unhcr_data_container_blueprint.add_url_rule(
    rule=u'/membership',
    view_func=membership,
    methods=['GET',],
)
unhcr_data_container_blueprint.add_url_rule(
    rule=u'/membership_add',
    view_func=membership_add,
    methods=['POST',],
)
unhcr_data_container_blueprint.add_url_rule(
    rule=u'/membership_remove',
    view_func=membership_remove,
    methods=['POST',],
)
unhcr_data_container_blueprint.add_url_rule(
    rule=u'/<container_id>/request_access',
    view_func=request_access,
    methods=['POST',],
)
