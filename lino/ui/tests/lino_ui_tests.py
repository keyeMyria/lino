# -*- coding: utf-8 -*-
## Copyright 2013 Luc Saffre
## This file is part of the Lino project.
## Lino is free software; you can redistribute it and/or modify 
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 3 of the License, or
## (at your option) any later version.
## Lino is distributed in the hope that it will be useful, 
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the 
## GNU General Public License for more details.
## You should have received a copy of the GNU General Public License
## along with Lino; if not, see <http://www.gnu.org/licenses/>.

"""
This module contains "quick" tests that are run on a demo database 
without any fixture. You can run only these tests by issuing::

  python manage.py test ui.QuickTest

"""

from __future__ import unicode_literals

import logging
logger = logging.getLogger(__name__)

from django.conf import settings


from django.utils import translation
from django.utils.encoding import force_unicode
from django.core.exceptions import ValidationError

#~ from lino import dd
from djangosite.utils.test import NoAuthTestCase


class QuickTest(NoAuthTestCase):
    pass
            


def test01(self):
    """
    Try wether the index page loads.
    """
    if settings.SITE.is_installed('pages'):
        from lino.modlib.pages.fixtures import std
        from north import dpy 
        dpy.load_fixture_from_module(std)
        #~ d = load_fixture(std)
        #~ self.assertEqual(d.saved,1)
        
    #~ with self.settings(DEBUG=True):
        
    response = self.client.get('')
        #~ response = self.client.get('/',REMOTE_USER='root',HTTP_ACCEPT_LANGUAGE='en')
    #~ print response.content
    self.assertEqual(response.status_code,200)


    response = self.client.get('/foo')
    self.assertEqual(response.status_code,404)
    
