# -*- coding: utf-8 -*-

import logging
from flask import Blueprint
from ckan import model
import ckan.lib.captcha as captcha
import ckan.lib.navl.dictization_functions as dictization_functions
import ckan.logic as logic
import ckan.plugins.toolkit as toolkit
from ckan.views.user import (
    RegisterView as BaseRegisterView,
    login as core_login
)
from ckanext.unhcr.helpers import get_data_deposit
from ckanext.unhcr.utils import require_user, get_internal_domains
from ckanext.unhcr import mailer

log = logging.getLogger(__name__)
_ = toolkit._


unhcr_user_blueprint = Blueprint('unhcr_user', __name__, url_prefix=u'/user')


@require_user
def sysadmin():
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
        toolkit.h.flash_success(u'Promoted {} to sysadmin'.format(user['display_name']))
    else:
        toolkit.h.flash_success(u'Revoked sysadmin permission from {}'.format(user['display_name']))
    return toolkit.h.redirect_to('unhcr_admin.index')


class RegisterView(BaseRegisterView):

    def _get_container_list(self):
        context = {'model': model, 'ignore_auth': True}
        orgs = toolkit.get_action('organization_list_all_fields')(context, {})
        deposit = get_data_deposit()
        containers = sorted(
            [
                {'value': o['id'], 'text': o['display_name'] }
                for o in orgs
                if o['id'] != deposit['id']
                and 'visible_external' in o
                and o['visible_external']
            ],
            key=lambda o: o['text']
        )
        containers.insert(0, {'value': '', 'text': 'Select...'})
        return containers

    def post(self):
        if toolkit.c.user:
            return toolkit.abort(403, "You can't create a new user account while already logged in")

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
            error_message = 'Please enter an email address'
            return self.get(data_dict, {'email': [error_message]}, {'email': error_message})

        if domain in get_internal_domains():
            error_message = (
                'Users with an @{domain} email may not register for a partner account. '.format(
                    domain=domain
                ) + 'Log in to {site} using {email} and use your Active Directory password to access RIDL'.format(
                    site=toolkit.config.get('ckan.site_url'),
                    email=toolkit.request.form['email']
                )
            )
            return self.get(data_dict, {'email': [error_message]}, {'email': error_message})

        if not data_dict.get('container'):
            error_message = "A region must be specified"
            return self.get(data_dict, {'container': [error_message]}, {'container': error_message})

        context['defer_commit'] = True
        data_dict['state'] = context['model'].State.PENDING
        deposit = get_data_deposit()
        containers = [data_dict.get('container'), deposit['id']]
        data_dict['default_containers'] = containers

        try:
            model.Session.begin_nested()
            user = toolkit.get_action(u'user_create')(context, data_dict)

            access_request_data_dict = {
                'object_id': user['id'],
                'object_type': 'user',
                'message': data_dict['message'],
                'role': 'member',
                'data': {'default_containers': containers}
            }
            toolkit.get_action(u'access_request_create')(
                {'user': user['id'], 'ignore_auth': True, 'defer_commit': True},
                access_request_data_dict
            )

            model.Session.commit()
        except toolkit.NotAuthorized:
            model.Session.rollback()
            toolkit.abort(403, _(u'Unauthorized to create user %s') % u'')
        except toolkit.ObjectNotFound:
            model.Session.rollback()
            toolkit.abort(404, _(u'User not found'))
        except toolkit.ValidationError as e:
            model.Session.rollback()
            errors = e.error_dict
            error_summary = e.error_summary
            return self.get(data_dict, errors, error_summary)
        except:
            model.Session.rollback()
            raise

        recipients = mailer.get_user_account_request_access_email_recipients(
            containers
        )
        for recipient in recipients:
            subj = mailer.compose_user_request_access_email_subj()
            body = mailer.compose_request_access_email_body(
                'user',
                recipient,
                user,
                user,
                data_dict['message']
            )
            toolkit.enqueue_job(mailer.mail_user_by_id, [recipient['name'], subj, body])

        return toolkit.render(
            u'user/account_created.html',
            {'email': data_dict['email']}
        )

    def get(self, data=None, errors=None, error_summary=None):
        if toolkit.c.user:
            return toolkit.abort(403, "You can't create a new user account while already logged in")

        self._prepare()

        form_vars = {
            u'data': data or {},
            u'errors': errors or {},
            u'error_summary': error_summary or {},
            u'containers': self._get_container_list(),
        }

        extra_vars = {
            u'form': toolkit.render(u'user/new_user_form.html', form_vars)
        }
        return toolkit.render(u'user/new.html', extra_vars)


def me():
    route = u'user.login'
    if toolkit.c.userobj:
        if toolkit.c.userobj.external:
            route = u'home.index'
        else:
            route = u'dashboard.index'
    return toolkit.h.redirect_to(route)


def logged_in():
    # redirect if needed
    came_from = toolkit.request.params.get(u'came_from', u'')
    if toolkit.h.url_is_local(came_from):
        return toolkit.redirect_to(str(came_from))

    if toolkit.c.user:
        return me()
    else:
        err = _(u'Login failed. Bad username or password.')
        toolkit.h.flash_error(err)
        return core_login()


def logged_out():
    # redirect to home
    return toolkit.redirect_to('home.index')


unhcr_user_blueprint.add_url_rule(
    rule=u'/sysadmin',
    view_func=sysadmin,
    methods=['POST',],
)

unhcr_user_blueprint.add_url_rule(
    u'/register',
    view_func=RegisterView.as_view(str(u'register'))
)

unhcr_user_blueprint.add_url_rule(
    u'/logged_in',
    view_func=logged_in
)

unhcr_user_blueprint.add_url_rule(
    u'/logged_out',
    view_func=logged_out
)
