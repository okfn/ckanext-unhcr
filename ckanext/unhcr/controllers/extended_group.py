import logging
from ckan import model
import ckan.plugins.toolkit as toolkit
from ckan.controllers.group import GroupController
log = logging.getLogger(__name__)


class ExtendedGroupController(GroupController):

    # Read

    def read(self, id):
        if not toolkit.c.user:
            return toolkit.render('page.html')
        return super(ExtendedGroupController, self).read(id)
