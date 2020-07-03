import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.controllers.user import UserController
from ckanext.unhcr import helpers
log = logging.getLogger(__name__)


class ExtendedUserController(UserController):

    # Requests

    def list_requests(self):
        if not helpers.user_is_container_admin() and not toolkit.c.userobj.sysadmin:
            return toolkit.abort(403, "Forbidden")

        context = {'model': model, 'user': toolkit.c.user}
        self._custom_setup_template_variables(context)

        try:
            new_container_requests = toolkit.get_action('pending_requests_list')(
                context, {'all_fields': True}
            )
        except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
            new_container_requests = []

        try:
            access_requests = toolkit.get_action('access_request_list_for_user')(
                context, {}
            )
        except (toolkit.NotAuthorized, toolkit.ObjectNotFound):
            access_requests = []

        container_access_requests = [
            req for req in access_requests if req['object_type'] == 'organization'
        ]
        dataset_access_requests = [
            req for req in access_requests if req['object_type'] == 'package'
        ]

        return toolkit.render('user/dashboard_requests.html', {
            'user_dict': context['user'],
            'new_container_requests': new_container_requests,
            'container_access_requests': container_access_requests,
            'dataset_access_requests': dataset_access_requests,
        })

    # Private

    def _custom_setup_template_variables(self, context):
        context = {'model': model, 'session': model.Session,
                   'user': toolkit.c.user, 'auth_user_obj': toolkit.c.userobj,
                   'for_view': True}
        data_dict = {'id': toolkit.c.userobj.id, 'user_obj': toolkit.c.userobj, 'offset': 0}
        self._setup_template_variables(context, data_dict)
