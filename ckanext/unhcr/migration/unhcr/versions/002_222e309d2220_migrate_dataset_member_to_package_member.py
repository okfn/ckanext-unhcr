"""migrate dataset_member to package_member

Revision ID: 222e309d2220
Revises: 
Create Date: 2021-04-16 10:23:34.822976

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import engine_from_config
from sqlalchemy.engine import reflection
from sqlalchemy.sql import text

# revision identifiers, used by Alembic.
revision = '222e309d2220'
down_revision = None
branch_labels = None
depends_on = None


def _table_exists(table):
    config = op.get_context().config
    engine = engine_from_config(
        config.get_section(config.config_ini_section), prefix='sqlalchemy.')
    insp = reflection.Inspector.from_engine(engine)
    return table in insp.get_table_names()


def upgrade():
    if not _table_exists(u'dataset_member'):
        return
    conn = op.get_bind()
    conn.execute(text(
        """
        INSERT INTO package_member
        (user_id, package_id, capacity, modified)
        SELECT user_id, dataset_id as package_id, capacity, modified
        FROM dataset_member
        WHERE user_id IN (SELECT id FROM "user")
        AND dataset_id IN (SELECT id FROM package)
        AND modified IS NOT NULL;
        """
    ))
    op.drop_table(u'dataset_member')


def downgrade():
    pass
