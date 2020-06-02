# -*- coding: utf-8 -*-

import datetime
import logging

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.types import Enum, UnicodeText

from ckan.model.meta import metadata
import ckan.model as model
from ckan.model.types import make_uuid


log = logging.getLogger(__name__)

Base = declarative_base(metadata=metadata)


class TimeSeriesMetric(Base):
    __tablename__ = u'time_series_metrics'

    timestamp = Column(DateTime, primary_key=True, default=datetime.datetime.utcnow)
    datasets_count = Column(Integer)
    deposits_count = Column(Integer)
    containers_count = Column(Integer)


class AccessRequest(Base):
    __tablename__ = u'access_requests'

    id = Column(UnicodeText, primary_key=True, default=make_uuid)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    user_id = Column(UnicodeText, nullable=False)
    message = Column(UnicodeText, nullable=False)
    role = Column(
        Enum('member', 'editor', 'admin', name='access_request_role_enum'),
        nullable=False,
    )
    status = Column(
        Enum('requested', 'approved', 'rejected', name='access_request_status_enum'),
        default='requested',
        nullable=False,
    )
    object_type = Column(
        Enum('dataset', 'container', name='access_request_object_type_enum'),
        nullable=False,
    )
    object_id = Column(UnicodeText, nullable=False)


def create_metric_columns():
    cols = ['datasets_count', 'deposits_count', 'containers_count']
    table = TimeSeriesMetric.__tablename__
    for col in cols:
        model.Session.execute(
            u"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} INTEGER;".format(
                table=table,
                col=col
            )
        )
    model.Session.commit()


def create_tables():
    if not TimeSeriesMetric.__table__.exists():
        TimeSeriesMetric.__table__.create()
        log.info(u'TimeSeriesMetric database table created')

    create_metric_columns()

    if not AccessRequest.__table__.exists():
        AccessRequest.__table__.create()
        log.info(u'AccessRequest database table created')
