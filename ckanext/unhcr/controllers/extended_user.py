import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.controllers.user import UserController
from ckanext.unhcr import helpers
log = logging.getLogger(__name__)


class ExtendedUserController(UserController):

    # Requests

    def list_requests(self):
        context = {'model': model, 'user': toolkit.c.user}
        self._custom_setup_template_variables(context)

        # Get requests
        try:
            requests = helpers.get_pending_requests(all_fields=True)
        except toolkit.NotAuthorized:
            message = 'Not authorized to see pending requests'
            return toolkit.abort(403, message)

        return toolkit.render('user/dashboard_requests.html', {
            'user_dict': context['user'],
            'requests': requests,
        })

    # Private

    def _custom_setup_template_variables(self, context):
        context = {'model': model, 'session': model.Session,
                   'user': toolkit.c.user, 'auth_user_obj': toolkit.c.userobj,
                   'for_view': True}
        data_dict = {'id': toolkit.c.userobj.id, 'user_obj': toolkit.c.userobj, 'offset': 0}
        self._setup_template_variables(context, data_dict)
