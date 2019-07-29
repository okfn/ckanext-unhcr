import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
import ckan.logic.action.get as get_core
import ckan.logic.action.patch as patch_core
import ckan.logic.action.delete as delete_core
from ckanext.unhcr import helpers, mailer
log = logging.getLogger(__name__)


class DataContainerController(toolkit.BaseController):

    # Requests

    def approve(self, id):
        context = {'model': model, 'user': toolkit.c.user}

        # check access and state
        _raise_not_authz_or_not_pending(id)

        # organization_patch state=active
        org_dict = patch_core.organization_patch({}, {'id': id, 'state': 'active'})

        # send approve email
        for member in get_core.member_list(context, {'id': org_dict['id']}):
            user = model.User.get(member[0])
            if user and user.email:
                subj = mailer.compose_container_email_subj(org_dict, event='approval')
                body = mailer.compose_container_email_body(org_dict, user, event='approval')
                mailer.mail_user(user, subj, body)

        # show flash message and redirect
        toolkit.h.flash_success('Data container "{}" approved'.format(org_dict['title']))
        toolkit.redirect_to('data-container_read', id=id)

    def reject(self, id, *args, **kwargs):
        context = {'model': model, 'user': toolkit.c.user}

        # check access and state
        _raise_not_authz_or_not_pending(id)

        # send rejection email
        org_dict = get_core.organization_show({'model': model}, {'id': id})
        for member in get_core.member_list(context, {'id': org_dict['id']}):
            user = model.User.get(member[0])
            if user and user.email:
                subj = mailer.compose_container_email_subj(org_dict, event='rejection')
                body = mailer.compose_container_email_body(org_dict, user, event='rejection')
                mailer.mail_user(user, subj, body)

        # call organization_purge
        delete_core.organization_purge({'model': model}, {'id': id})

        # show flash message and redirect
        toolkit.h.flash_error('Data container "{}" rejected'.format(org_dict['title']))
        toolkit.redirect_to('data-container_index')

    # Membership

    def membership(self):
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

        # Get user
        user = None
        if username:
            try:
                user = toolkit.get_action('user_show')(context, {'id': username})
                deposit = helpers.get_data_deposit()
            except toolkit.ObjectNotFound:
                message = 'User "%s" not found'
                toolkit.h.flash_success(message % username)
                toolkit.redirect_to('data_container_membership')

        # Containers
        containers = []
        if user:
            action = 'organization_list'
            data_dict = {'type': 'data-container', 'order_by': 'title', 'all_fields': True}
            containers = toolkit.get_action(action)(context, data_dict)
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
            user_containers = filter(
                lambda cont: cont['name'] != deposit['name'], user_containers)

        return toolkit.render('organization/membership.html', {
            'membership': {
                'users': users,
                'user': user,
                'containers': containers,
                'roles': roles,
                'user_containers': user_containers,
            }
        })

    def membership_add(self):
        context = {'model': model, 'user': toolkit.c.user}
        username = toolkit.request.params.get('username')
        contnames = helpers.normalize_list(toolkit.request.params.getall('contnames'))
        role = toolkit.request.params.get('role')

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
        toolkit.redirect_to('data_container_membership', username=username)

    def membership_remove(self):
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
            toolkit.redirect_to('data_container_membership', username=username)

        # Show flash message and redirect
        message = 'User "%s" removed from the data container "%s"'
        toolkit.h.flash_error(message % (username, contname))
        toolkit.redirect_to('data_container_membership', username=username)


def _raise_not_authz_or_not_pending(id):

    # check auth with toolkit.check_access
    toolkit.check_access('sysadmin', {'model': model})

    # check org exists and it's pending with organization_show
    org_dict = toolkit.get_action('organization_show')({}, {'id': id})
    if org_dict.get('state') != 'approval_needed':
        raise toolkit.ObjectNotFound('Data container "{}" not found'.format(id))
