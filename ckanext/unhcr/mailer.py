import logging
from ckan import model
from ckan.common import config
from ckan.plugins import toolkit
from ckan.lib.mailer import mail_user
from ckan.lib.base import render_jinja2
import ckan.logic.action.get as get_core
log = logging.getLogger(__name__)


# Data Containers

def mail_data_container_request_to_sysadmins(context, org_dict):
    context.setdefault('model', model)

    # Mail all sysadmins
    for user in _get_sysadmins(context):
        if user.email:
            subj = _compose_email_subj(org_dict, event='request')
            body = _compose_email_body(org_dict, user, event='request')
            mail_user(user, subj, body)
            log.debug('[email] Data container request email sent to {0}'.format(user.name))


def mail_data_container_update_to_user(context, org_dict, event='approval'):
    context.setdefault('model', model)

    # Mail all members
    for member in get_core.member_list(context, {'id': org_dict['id']}):
        user = model.User.get(member[0])
        if user and user.email:
            subj = _compose_email_subj(org_dict, event=event)
            body = _compose_email_body(org_dict, user, event=event)
            mail_user(user, subj, body)
            log.debug('[email] Data container update email sent to {0}'.format(user.name))


def _get_sysadmins(context):
    model = context['model']
    return model.Session.query(model.User).filter(model.User.sysadmin==True).all()


def _compose_email_subj(org_dict, event='request'):
    return '[UNHCR RIDL] Data Container {0}: {1}'.format(event.capitalize(), org_dict['title'])


def _compose_email_body(org_dict, user, event='request'):
    org_link = toolkit.url_for('data-container_read', id=org_dict['name'], qualified=True)
    return render_jinja2('emails/data_container_{0}.txt'.format(event), {
        'user_name': user.fullname or user.name,
        'site_title': config.get('ckan.site_title'),
        'site_url': config.get('ckan.site_url'),
        'org_title': org_dict['title'],
        'org_link': org_link,
    })


# Data Deposit
# TODO: sync data/container deposit approaches

def compose_curation_email_subj(dataset):
    return '[UNHCR RIDL] Curation: %s' % dataset.get('title')


def compose_curation_email_body(dataset, curation, recipient, event):
    context = {}
    context['site_title'] = config.get('ckan.site_title')
    context['site_url'] = config.get('ckan.site_url')
    context['dataset'] = dataset
    context['dataset_url'] = toolkit.url_for('dataset_read', id=dataset['name'], qualified=True)
    context['curation'] = curation
    context['recipient'] = recipient
    return render_jinja2('emails/curation_%s.html' % event, context)


def mail_user_by_id(user_id, subj, body):
    user = model.User.get(user_id)
    return mail_user(user, subj, body)
