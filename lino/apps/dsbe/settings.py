# -*- coding: UTF-8 -*-
## Copyright 2009-2011 Luc Saffre
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
Default settings for :doc:`/dsbe/index`.

"""

import os
import lino

from lino.apps.std.settings import *

LISTINGS = """
jobs.ContractsSituation
lino.DataControlListing
""".split()


class Lino(Lino):
    """
    Lino/DSBE is
    the first of the real-world demo applications that are part 
    of the Lino project.
    It is a tool for social assistants that help receivers 
    of public aid to find a suitable job or education, 
    adapted to Belgian *Public Centres for Social Welfare* 
    (Centres Publics d'Action Sociale).
    
    """
    source_dir = os.path.dirname(__file__)
    title = "Lino/DSBE"
    #~ domain = "dsbe.saffre-rumma.net"
    help_url = "http://lino.saffre-rumma.net/dsbe/index.html"
    migration_module = 'lino.apps.dsbe.migrate'
    project_model = 'contacts.Person'
    
    languages = ('de', 'fr', 'nl', 'en')
    
    def get_app_source_file(self):
        return __file__
        
    def setup_quicklinks(self,ui,user,tb):
        #~ tb.add_action(self.modules.contacts.Persons().detail)
        tb.add_action('contacts.Persons.detail')
        tb.add_action(self.modules.cal.Panel)
        tb.add_action(self.modules.dsbe.MyPersons)
        tb.add_action(self.modules.isip.MyContracts)
        tb.add_action(self.modules.jobs.MyContracts)
        
        
    def setup_menu(self,ui,user,main):
        from django.utils.translation import ugettext_lazy as _
        from django.db import models
        
        m = main.add_menu("contacts",_("Contacts"))
        m.add_action(self.modules.dsbe.Companies)
        m.add_action(self.modules.dsbe.Persons)
        #~ m.add_action('contacts.Persons.detail')
        #~ m.add_action('contacts.Persons',label="Alle Personen",params={})
        m.add_action(self.modules.dsbe.MySearches)
        #~ m.add_action('contacts.AllContacts')
        m.add_action(self.modules.dsbe.AllContacts)
        m.add_action(self.modules.dsbe.Newcomers)
        m.add_action(self.modules.dsbe.OverviewClientsByUser)
        self.modules.isip.setup_main_menu(self,ui,user,m)
        #~ jobs.setup_main_menu(self,ui,user,m)
        #~ m.add_action('jobs.JobProviders')


        if user is None:
            return main
            
        m = main.add_menu("my",_("My menu"))
        #~ m.add_action('projects.Projects')
        m.add_action(self.modules.dsbe.MyNotes)
        
        mypersons = m.add_menu("mypersons",self.modules.dsbe.MyPersons.label)
        mypersons.add_action(self.modules.dsbe.MyPersons)
        for pg in self.modules.dsbe.PersonGroup.objects.order_by('ref_name'):
            mypersons.add_action(self.modules.dsbe.MyPersonsByGroup,label=pg.name,
                params=dict(master_instance=pg))
            #~ m.add_action('contacts.MyPersonsByGroup',label=pg.name,
            #~ params=dict(master_id=pg.pk))
            
        self.modules.isip.setup_my_menu(self,ui,user,m)
        self.modules.jobs.setup_my_menu(self,ui,user,m)
        
        self.modules.cal.setup_my_menu(self,ui,user,m)
        self.modules.mails.setup_my_menu(self,ui,user,m)
        m.add_action(self.modules.uploads.MyUploads)
        m.add_action(self.modules.lino.MyTextFieldTemplates)

        #~ m.add_instance_action(user,label="My user preferences")

        m = main.add_menu("courses",_("Courses"))
        m.add_action(self.modules.dsbe.CourseProviders)
        m.add_action(self.modules.dsbe.CourseOffers)
        
        m = main.add_menu("jobs",_("Jobs"))
        self.modules.jobs.setup_main_menu(self,ui,user,m)
        
        #~ sitemenu = system.add_site_menu(self)
        #~ if False:
        listings = main.add_menu("lst",_("Listings"))
        for listing in LISTINGS:
            #~ listings.add_action(listing)
            listings.add_action(listing + '.listing')
        #~ listings.add_instance_action(lst)
        #~ for lst in dsbe.FooListing.objects.all():
            #~ listings.add_instance_action(lst)
        
        if user.is_staff:
            cfg = main.add_menu("config",_("Configure"))
            
            config_contacts = cfg.add_menu("contacts",_("Contacts"))
            config_contacts.add_action(self.modules.countries.Countries)
            config_contacts.add_action(self.modules.countries.Cities)
            config_contacts.add_action(self.modules.contacts.CompanyTypes)
            #~ config_contacts.add_action('contacts.ContactTypes')
            #~ config_contacts.add_action('contacts.RoleTypes')
            config_contacts.add_action(self.modules.countries.Languages)
            
            
            #~ config_notes    = cfg.add_menu("notes",_("~Notes"))
            config_dsbe     = cfg.add_menu("dsbe",_("SIS"))
            
            config_cv       = cfg.add_menu("cv",_("CV"))
            config_etc      = cfg.add_menu("etc",_("System"))
            
            
            m = cfg.add_menu("courses",_("Courses"))
            m.add_action(self.modules.dsbe.CourseContents)
            m.add_action(self.modules.dsbe.CourseEndings)
            
            self.modules.notes.setup_config_menu(self,ui,user,cfg)
            self.modules.isip.setup_config_menu(self,ui,user,cfg)
            self.modules.jobs.setup_config_menu(self,ui,user,cfg)
            
            config_dsbe.add_action(self.modules.dsbe.PersonGroups)
        
            if True: # user.is_expert:
                config_props = cfg.add_menu("props",_("Properties"))
                config_props.add_action(self.modules.properties.PropGroups)
                config_props.add_action(self.modules.properties.PropTypes)
                for pg in self.modules.properties.PropGroup.objects.all():
                    #~ mm.add_request_action(properties.PropsByGroup().request(master_instance=pg),label=pg.name)
                    config_props.add_action(
                        self.modules.properties.PropsByGroup,
                        params=dict(master_instance=pg),
                        label=pg.name)
        
            config_cv.add_action(self.modules.dsbe.Activities)
            
            config_dsbe.add_action(self.modules.dsbe.ExclusionTypes)
            config_dsbe.add_action(self.modules.dsbe.AidTypes)
            #~ config_jobs.add_action('jobs.Jobs')
            #~ m.add_action('dsbe.JobTypes')
            #~ m.add_action('dsbe.CoachingTypes')
            
            #~ links.setup_config_menu(self,ui,user,cfg)
            #~ config_etc.add_action('links.LinkTypes')
            config_etc.add_action(self.modules.uploads.UploadTypes)
            
            self.modules.cal.setup_config_menu(self,ui,user,cfg)
            self.modules.mails.setup_config_menu(self,ui,user,cfg)
            
            config_etc.add_action(self.modules.users.Users)
            #~ if self.use_tinymce:
            config_etc.add_action(self.modules.lino.TextFieldTemplates)
            config_etc.add_instance_action(self.site_config)
        
            m = main.add_menu("explorer",_("Explorer"))
            #m.add_action('properties.PropChoices')
            #~ m.add_action('properties.PropValues')
            m.add_action(self.modules.dsbe.AllPersons)
            #~ m.add_action('contacts.Roles')
            self.modules.notes.setup_explorer_menu(self,ui,user,m)
            self.modules.isip.setup_explorer_menu(self,ui,user,m)
            self.modules.jobs.setup_explorer_menu(self,ui,user,m)
            #~ links.setup_explorer_menu(self,ui,user,m)
            #~ m.add_action('notes.Notes')
            #~ m.add_action('lino.TextFieldTemplates')
            #~ m.add_action('links.Links')
            m.add_action(self.modules.uploads.Uploads)
            m.add_action(self.modules.dsbe.Exclusions)
            m.add_action(self.modules.dsbe.CourseRequests)
            m.add_action(self.modules.dsbe.PersonSearches)
            m.add_action(self.modules.lino.ContentTypes)
            m.add_action(self.modules.properties.Properties)
            m.add_action(self.modules.dsbe.Courses)
            
            self.modules.cal.setup_explorer_menu(self,ui,user,m)
            
            lst = m.add_menu("lst",_("Listings"))
            for listing in LISTINGS:
                #~ listings.add_action(listing)
                lst.add_action(listing+"Table")
            

        
        m = main.add_menu("help",_("Help"))
        m.add_item('userman',_("~User Manual"),
            href='http://lino.saffre-rumma.net/dsbe/index.html')
            
        return main
      

LINO = Lino(__file__,globals())


#~ PROJECT_DIR = abspath(dirname(__file__))
#~ DATA_DIR = join(PROJECT_DIR,"data")
#~ LINO_SETTINGS = join(PROJECT_DIR,"lino_settings.py")

#~ MEDIA_ROOT = join(LINO.project_dir,'media')
#~ MEDIA_ROOT = join(PROJECT_DIR,'media')

#~ TIME_ZONE = 'Europe/Brussels'
TIME_ZONE = None

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
#~ LANGUAGE_CODE = 'de'
#~ LANGUAGE_CODE = 'de-BE'
#~ LANGUAGE_CODE = 'fr-BE'

#~ SITE_ID = 1 # see also fill.py

INSTALLED_APPS = (
  #~ 'django.contrib.auth',
  'django.contrib.contenttypes',
  #~ 'django.contrib.sessions',
  #~ 'django.contrib.sites',
  #~ 'django.contrib.markup',
  #~ 'lino.modlib.system',
  'lino',
  'lino.modlib.users',
  'lino.modlib.countries',
  #~ 'lino.modlib.documents',
  'lino.modlib.properties',
  'lino.modlib.contacts',
  #~ 'lino.modlib.projects',
  'lino.modlib.notes',
  #~ 'lino.modlib.links',
  'lino.modlib.uploads',
  'lino.modlib.thirds',
  'lino.modlib.cal',
  'lino.modlib.mails',
  'lino.modlib.jobs',
  'lino.modlib.isip',
  'lino.modlib.bcss',
  'lino.apps.dsbe',
  #'dsbe.modlib.contacts',
  #'dsbe.modlib.projects',
  #~ 'south', # http://south.aeracode.org
)

#~ LANGUAGES = language_choices('de','fr','nl','en')
#~ LANGUAGES = language_choices('de','fr','en')

