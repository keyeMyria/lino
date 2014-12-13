# -*- coding: UTF-8 -*-
# Copyright 2011-2014 Luc Saffre
# License: BSD (see file COPYING for details)

"""
Miscellaneous mixins available in :mod:`ml.system`.

"""

from __future__ import unicode_literals

import datetime

from django.utils.translation import ugettext_lazy as _
from django.db import models

from lino.core.choicelists import ChoiceList, Choice

from lino.utils import AttrDict


class YesNo(ChoiceList):
    """
    Used e.g. for table parameters. TODO: write usage example.

    """
    verbose_name_plural = _("Yes or no")
add = YesNo.add_item
add('y', _("Yes"), 'yes')
add('n', _("No"), 'no')


class Genders(ChoiceList):
    """A choicelist with two choices ``male`` and ``female``. 
    See :doc:`/dev/choicelists`.
    """

    verbose_name = _("Gender")

add = Genders.add_item
add('M', _("Male"), 'male')
add('F', _("Female"), 'female')


class PeriodEvent(Choice):

    def add_filter(self, qs, obj):

        if isinstance(obj, datetime.date):
            obj = AttrDict(start_date=obj, end_date=obj)

        if obj.start_date is None or obj.end_date is None:
            return qs

        if self.name == 'started':
            qs = qs.filter(start_date__gte=obj.start_date)
            qs = qs.filter(start_date__lte=obj.end_date)
        elif self.name == 'ended':
            qs = qs.filter(end_date__isnull=False)
            qs = qs.filter(end_date__gte=obj.start_date)
            qs = qs.filter(end_date__lte=obj.end_date)
        elif self.name == 'active':
            qs = qs.filter(models.Q(start_date__isnull=True) |
                           models.Q(start_date__lte=obj.end_date))
            qs = qs.filter(models.Q(end_date__isnull=True) |
                           models.Q(end_date__gte=obj.start_date))
        return qs


class PeriodEvents(ChoiceList):
    verbose_name = _("Observed event")
    verbose_name_plural = _("Observed events")
    item_class = PeriodEvent


add = PeriodEvents.add_item
add('10', _("Started"), 'started')
add('20', _("Active"), 'active')
add('30', _("Ended"), 'ended')



