import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.controllers.organization import OrganizationController
log = logging.getLogger(__name__)


class ExtendedOrganizationController(OrganizationController):

    # Read

    def read(self, id):
        if not toolkit.c.user:
            return toolkit.abort(403, toolkit.render('page.html'))
        return super(ExtendedOrganizationController, self).read(id)
