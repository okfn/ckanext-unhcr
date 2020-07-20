# -*- coding: utf-8 -*-

from flask import Blueprint
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckanext.unhcr import helpers
from ckanext.unhcr import mailer
from ckanext.unhcr.models import AccessRequest


unhcr_data_container_blueprint = Blueprint(
    'unhcr_data_container',
    __name__,
    url_prefix=u'/data-container'
)


def request_access(container_id):
    if (not hasattr(toolkit.c, "user") or not toolkit.c.user):
        return toolkit.abort(403, "Forbidden")

    message = toolkit.request.form.get('message')
    if not message:
        return toolkit.abort(400, "'message' is required")

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

    rec = AccessRequest(
        user_id=toolkit.c.userobj.id,
        object_id=container['id'],
        object_type='organization',
        message=message,
        role='member',
    )
    model.Session.add(rec)
    model.Session.commit()

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
        mailer.mail_user_by_id(recipient['name'], subj, body)

    toolkit.h.flash_success(
        'Requested access to container {}'.format(
            container['display_name']
        )
    )
    return toolkit.redirect_to('data-container_read', id=container_id)


unhcr_data_container_blueprint.add_url_rule(
    rule=u'/<container_id>/request_access',
    view_func=request_access,
    methods=['POST',],
)
