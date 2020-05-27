import pylons
from ckan.lib.search import rebuild
from paste.registry import Registry
from ckan.tests import helpers as core_helpers, factories as core_factories
from ckanext.unhcr.models import (
    create_tables as unhcr_create_tables,
    create_columns as unhcr_create_columns,
)
from ckanext.collaborators.model import (
    tables_exist as collaborators_tables_exist,
    create_tables as collaborators_create_tables,
)


class FunctionalTestBase(core_helpers.FunctionalTestBase):

    # Config

    @classmethod
    def setup_class(cls):
        super(FunctionalTestBase, cls).setup_class()
        core_helpers.reset_db()

        unhcr_create_tables()
        unhcr_create_columns()
        if not collaborators_tables_exist():
            collaborators_create_tables()

        # Fix ckanext-hierarchy "c"
        c = pylons.util.AttribSafeContextObj()
        registry = Registry()
        registry.prepare()
        registry.register(pylons.c, c)

    @classmethod
    def teardown_class(cls):
        super(FunctionalTestBase, cls).teardown_class()
        core_helpers.reset_db()

    def setup(self):
        super(FunctionalTestBase, self).setup()
        core_helpers.reset_db()
        rebuild()

        # Get app
        self.app = self._get_test_app()
