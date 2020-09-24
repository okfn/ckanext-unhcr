# -*- coding: utf-8 -*-

import logging
from flask import Blueprint
import ckan.lib.captcha as captcha
import ckan.lib.navl.dictization_functions as dictization_functions
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
from ckan.views.user import RegisterView as BaseRegisterView
from ckanext.unhcr.utils import get_internal_domains

log = logging.getLogger(__name__)
_ = toolkit._


unhcr_user_blueprint = Blueprint('unhcr_user', __name__, url_prefix=u'/user')


def sysadmin():
    if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
        return toolkit.abort(403, "Forbidden")

    id_ = toolkit.request.form.get('id')
    status = toolkit.asbool(toolkit.request.form.get('status'))

    try:
        context = {'user': toolkit.c.user}
        data_dict = {'id': id_, 'is_sysadmin': status}
        user = toolkit.get_action('user_update_sysadmin')(context, data_dict)
    except toolkit.NotAuthorized:
        return toolkit.abort(403, 'Not authorized to promote user to sysadmin')
    except toolkit.ObjectNotFound:
        return toolkit.abort(404, 'User not found')

    if status:
        toolkit.h.flash_success('Promoted {} to sysadmin'.format(user['display_name']))
    else:
        toolkit.h.flash_success('Revoked sysadmin permission from {}'.format(user['display_name']))
    return toolkit.h.redirect_to('unhcr_admin.index')


class RegisterView(BaseRegisterView):

    def post(self):
        context = self._prepare()
        try:
            data_dict = logic.clean_dict(
                dictization_functions.unflatten(
                    logic.tuplize_dict(logic.parse_params(toolkit.request.form))))
        except dictization_functions.DataError:
            toolkit.abort(400, _(u'Integrity Error'))

        context[u'message'] = data_dict.get(u'log_message', u'')
        try:
            captcha.check_recaptcha(toolkit.request)
        except captcha.CaptchaError:
            error_msg = _(u'Bad Captcha. Please try again.')
            toolkit.h.flash_error(error_msg)
            return self.get(data_dict)

        try:
            domain = toolkit.request.form['email'].split('@')[1]
        except IndexError:
            message = 'Please enter an email address'
            return self.get(data_dict, {'email': [message]}, {'email': message})

        if domain in get_internal_domains():
            message = (
                'Users with an @{domain} email may not register for an external account. '.format(
                    domain=domain
                ) + 'Log in to {site} using {email} and use your Active Directory password to access RIDL'.format(
                    site=toolkit.config.get('ckan.site_url'),
                    email=toolkit.request.form['email']
                )
            )
            return self.get(data_dict, {'email': [message]}, {'email': message})

        try:
            data_dict['state'] = context['model'].State.PENDING
            toolkit.get_action(u'user_create')(context, data_dict)
        except toolkit.NotAuthorized:
            toolkit.abort(403, _(u'Unauthorized to create user %s') % u'')
        except toolkit.ObjectNotFound:
            toolkit.abort(404, _(u'User not found'))
        except toolkit.ValidationError as e:
            errors = e.error_dict
            error_summary = e.error_summary
            return self.get(data_dict, errors, error_summary)

        if toolkit.c.user:
            # #1799 User has managed to register whilst logged in - warn user
            # they are not re-logged in as new user.
            toolkit.h.flash_success(
                _(u'User "%s" is now registered but you are still '
                  u'logged in as "%s" from before') % (data_dict[u'name'],
                                                       toolkit.c.user))
            try:
                toolkit.check_access('sysadmin', context)
                return toolkit.h.redirect_to(u'user.activity', id=data_dict[u'name'])
            except toolkit.NotAuthorized:
                return toolkit.render(u'user/logout_first.html')

        return toolkit.render(
            u'user/account_created.html',
            {'email': data_dict['email']}
        )


unhcr_user_blueprint.add_url_rule(
    rule=u'/sysadmin',
    view_func=sysadmin,
    methods=['POST',],
)

unhcr_user_blueprint.add_url_rule(
    u'/register',
    view_func=RegisterView.as_view(str(u'register'))
)
