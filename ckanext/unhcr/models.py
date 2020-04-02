# -*- coding: utf-8 -*-

import datetime
import logging

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.ext.declarative import declarative_base

from ckan.model.meta import metadata


log = logging.getLogger(__name__)

Base = declarative_base(metadata=metadata)


class TimeSeriesMetric(Base):
    __tablename__ = u'time_series_metrics'

    timestamp = Column(DateTime, primary_key=True, default=datetime.datetime.utcnow)
    datasets_count = Column(Integer, nullable=False)
    containers_count = Column(Integer, nullable=False)


def create_tables():
    TimeSeriesMetric.__table__.create()
    log.info(u'TimeSeriesMetric database table created')


def tables_exist():
    return TimeSeriesMetric.__table__.exists()
