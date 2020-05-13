# -*- coding: utf-8 -*-

import datetime
import logging

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

from ckan.model.meta import metadata
import ckan.model as model


log = logging.getLogger(__name__)

Base = declarative_base(metadata=metadata)


class TimeSeriesMetric(Base):
    __tablename__ = u'time_series_metrics'

    timestamp = Column(DateTime, primary_key=True, default=datetime.datetime.utcnow)
    datasets_count = Column(Integer)
    deposits_count = Column(Integer)
    containers_count = Column(Integer)


def create_tables():
    if not tables_exist():
        TimeSeriesMetric.__table__.create()
        log.info(u'TimeSeriesMetric database table created')


def create_columns():
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


def tables_exist():
    return TimeSeriesMetric.__table__.exists()
