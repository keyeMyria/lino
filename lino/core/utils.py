# Copyright 2010-2015 Luc Saffre
# License: BSD (see file COPYING for details)
"""A collection of utilities which require Django settings to be
importable.

This defines some helper classes like

- :class:`Parametrizable` and :class:`Permittable` ("mixins" with
  common functionality for both actors and actions),
- the volatile :class:`InstanceAction` object
- the :class:`ParameterPanel` class (used
  e.g. by :class:`lino.mixins.periods.ObservedPeriod`)

.. autosummary::

"""

from __future__ import unicode_literals


import logging
logger = logging.getLogger(__name__)

import sys
import datetime

from django.db import models
from django.db.models import Q
from django.db.models import loading
from django.db.models.fields import FieldDoesNotExist
from django.utils.importlib import import_module
from django.utils.translation import ugettext as _
from django.conf import settings
from django.db.models.fields import NOT_PROVIDED
from django.core import exceptions
from django.utils.encoding import force_unicode

from lino.core.signals import on_ui_updated
from lino.utils.xmlgen.html import E
from lino import AFTER17

from django.core.validators import (
    validate_email, ValidationError, URLValidator)

validate_url = URLValidator()


def is_valid_url(s):
    """Returns `True` if the given string is a valid URL.  This calls
Django's `URLValidator()`, but does not raise an exception.

    """
    try:
        validate_url(s)
        return True
    except ValidationError:
        return False


def is_valid_email(s):
    """Returns `True` if the given string is a valid email.  This calls
Django's `validate_email()`, but does not raise an exception.

    """
    try:
        validate_email(s)
        return True
    except ValidationError:
        return False


def is_devserver():
    """Returns `True` if this process is running as a development server.
    
    Thanks to Aryeh Leib Taurog in `How can I tell whether my Django
    application is running on development server or not?
    <http://stackoverflow.com/questions/1291755>`_
    
    My additions:
    
    - Added the `len(sys.argv) > 1` test because in a wsgi application
      the process is called without arguments.
    - Not only for `runserver` but also for `testserver` and `test`.

    """
    #~ print 20130315, sys.argv[1]
    return len(sys.argv) > 1 and sys.argv[1] in (
        'runserver', 'testserver', 'test', "makescreenshots")


def full_model_name(model, sep='.'):
    """Returns the "full name" of the given model, e.g. "contacts.Person" etc.
    """
    return model._meta.app_label + sep + model._meta.object_name


def obj2unicode(i):
    """Returns a user-friendly unicode representation of a model instance."""
    if not isinstance(i, models.Model):
        return unicode(i)
    return '%s "%s"' % (i._meta.verbose_name, unicode(i))


def obj2str(i, force_detailed=False):
    """Returns a human-readable ascii string representation of a model
    instance, even in some edge cases.

    """
    if not isinstance(i, models.Model):
        if isinstance(i, long):
            return str(i)  # AutoField is long on mysql, int on sqlite
        if isinstance(i, datetime.date):
            return i.isoformat()
        if isinstance(i, unicode):
            return repr(i)[1:]
        return repr(i)
    if i.pk is None:
        force_detailed = True
    if not force_detailed:
        if i.pk is None:
            return '(Unsaved %s instance)' % (i.__class__.__name__)
        try:
            return u"%s #%s (%s)" % (i.__class__.__name__, str(i.pk), repr(unicode(i)))
        except Exception, e:
        #~ except TypeError,e:
            return "Unprintable %s(pk=%r,error=%r" % (
                i.__class__.__name__, i.pk, e)
            #~ return unicode(e)
    #~ names = [fld.name for (fld,model) in i._meta.get_fields_with_model()]
    #~ s = ','.join(["%s=%r" % (n, getattr(i,n)) for n in names])
    pairs = []
    for (fld, model) in i._meta.get_fields_with_model():
        #~ if fld.name == 'language':
            #~ print 20120905, model, fld
        if isinstance(fld, models.ForeignKey):
            v = getattr(i, fld.attname, None)  # 20130709 Django 1.6b1
            #~ v = getattr(i,fld.name+"_id")
            #~ if getattr(i,fld.name+"_id") is not None:
                #~ v = getattr(i,fld.name)
        else:
            try:
                v = getattr(i, fld.name, None)  # 20130709 Django 1.6b1
            except Exception as e:
                v = str(e)
        if v:
            pairs.append("%s=%s" % (fld.name, obj2str(v)))
    s = ','.join(pairs)
    #~ s = ','.join(["%s=%s" % (n, obj2str(getattr(i,n))) for n in names])
    #~ print i, i._meta.get_all_field_names()
    #~ s = ','.join(["%s=%r" % (n, getattr(i,n)) for n in i._meta.get_all_field_names()])
    return "%s(%s)" % (i.__class__.__name__, s)
    #~ return "%s(%s)" % (i.__class__,s)


def sorted_models_list():
    # trigger django.db.models.loading.cache._populate()
    models_list = models.get_models()

    def fn(a, b):
        return cmp(full_model_name(a), full_model_name(b))
    models_list.sort(fn)
    return models_list


def models_by_base(base):
    """Yields a list of installed models that are subclass of the given
    base class.

    """
    for m in models.get_models():
        if issubclass(m, base):
            yield m

#~ models_by_abc = models_by_base


def app_labels():
    return [a.__name__.split('.')[-2] for a in loading.get_apps()]


def range_filter(value, f1, f2):
    """
    Assuming a database model with two fields of same data type named 
    `f1` and `f2`, return a Q object to select those rows
    whose `f1` and `f2` encompass the given value `value`.
    """
    #~ filter = Q(**{f2+'__isnull':False}) | Q(**{f1+'__isnull':False})
    q1 = Q(**{f1 + '__isnull': True}) | Q(**{f1 + '__lte': value})
    q2 = Q(**{f2 + '__isnull': True}) | Q(**{f2 + '__gte': value})
    return Q(q1, q2)


def inrange_filter(fld, rng, **kw):
    """
    Assuming a database model with a field named  `fld`, 
    return a Q object to select those rows
    whose `fld` value is not null and within the given range `rng`.
    `rng` must be a tuple of list with two items
    """
    assert rng[0] <= rng[1]
    kw[fld + '__isnull'] = False
    kw[fld + '__gte'] = rng[0]
    kw[fld + '__lte'] = rng[1]
    return Q(**kw)


def babelkw(*args, **kw):
    return settings.SITE.babelkw(*args, **kw)


def babelattr(*args, **kw):
    return settings.SITE.babelattr(*args, **kw)
babel_values = babelkw  # old alias for backwards compatibility


class UnresolvedModel:

    """The object returned by :func:`resolve_model` if the specified model
    is not installed.
    
    We don't want :func:`resolve_model` to raise an Exception because
    there are cases of :ref:`datamig` where it would disturb.  Asking
    for a non-installed model is not a sin, but trying to use it is.
    
    I didn't yet bother very much about finding a way to make the
    `model_spec` appear in error messages such as
    :message:`AttributeError: UnresolvedModel instance has no
    attribute '_meta'`.  Current workaround is to uncomment the
    ``print`` statement below in such situations...

    """

    def __init__(self, model_spec, app_label):
        self.model_spec = model_spec
        self.app_label = app_label
        #~ print(self)

    def __repr__(self):
        return self.__class__.__name__ + '(%s,%s)' % (
            self.model_spec, self.app_label)

    #~ def __getattr__(self,name):
        #~ raise AttributeError("%s has no attribute %r" % (self,name))


def resolve_model(model_spec, app_label=None, strict=False):
    """Return the class object of the specified model. `model_spec` is
    usually the global model name (i.e. a string like
    ``'contacts.Person'``).

    If `model_spec` does not refer to a known model, the function
    returns :class:`UnresolvedModel` (unless `strict=True` is
    specified).

    Using this method is better than simply importing the class
    object, because Lino applications can override the model
    implementation.
    
    This function **does not** trigger a loading of Django's model
    cache, so you should not use it at module-level of a
    :xfile:`models.py` module.

    In general we recommend to use ``from lino import rt`` and
    ``rt.modules.contacts.Person`` over
    ``resolve_model('contacts.Person')``.

    """
    # ~ models.get_apps() # trigger django.db.models.loading.cache._populate()
    if isinstance(model_spec, basestring):
        if '.' in model_spec:
            app_label, model_name = model_spec.split(".")
        else:
            model_name = model_spec

        if AFTER17:
            from django.apps import apps
            model = apps.get_model(app_label, model_name)
        else:
            model = models.get_model(app_label, model_name, seed_cache=False)
        #~ model = models.get_model(app_label,model_name,seed_cache=seed_cache)
    else:
        model = model_spec
    if not isinstance(model, type) or not issubclass(model, models.Model):
        if strict:
            if False:
                from django.db.models import loading
                print(20130219, settings.INSTALLED_APPS)
                print(loading.get_models())
                #~ if len(loading.cache.postponed) > 0:

            if isinstance(strict, basestring):
                raise Exception(strict % model_spec)
            raise ImportError(
                "resolve_model(%r,app_label=%r) found %r "
                "(settings %s, INSTALLED_APPS=%s)" % (
                    model_spec, app_label, model,
                    settings.SETTINGS_MODULE, settings.INSTALLED_APPS))
        #~ logger.info("20120628 unresolved %r",model)
        return UnresolvedModel(model_spec, app_label)
    return model


def resolve_app(app_label, strict=False):
    """Return the `modules` module of the given `app_label` if it is
    installed.  Otherwise return either the :term:`dummy module` for
    `app_label` if it exists, or `None`.

    If the optional second argument `strict` is `True`, raise
    ImportError if the app is not installed.
    
    This function is designed for use in models modules and available
    through the shortcut ``dd.resolve_app``.
    
    For example, instead of writing::
    
        from lino.modlib.sales import models as sales
        
    it is recommended to write::
        
        sales = dd.resolve_app('sales')
        
    because it makes your code usable (1) in applications that don't
    have the 'sales' module installed and (2) in applications who have
    another implementation of the `sales` module
    (e.g. :mod:`lino.modlib.auto.sales`)

    """
    #~ app_label = app_label
    for app_name in settings.INSTALLED_APPS:
        if app_name == app_label or app_name.endswith('.' + app_label):
            return import_module('.models', app_name)
    try:
        return import_module('lino.modlib.%s.dummy' % app_label)
    except ImportError:
        if strict:
            #~ raise
            raise ImportError("No app_label %r in %s" %
                              (app_label, settings.INSTALLED_APPS))


def require_app_models(app_label):
    return resolve_app(app_label, True)


def get_field(model, name):
    """Returns the field descriptor of the named field in the specified
    model.

    """
    for vf in model._meta.virtual_fields:
        if vf.name == name:
            return vf
    fld, remote_model, direct, m2m = model._meta.get_field_by_name(name)
    # see blog/2011/0525
    #~ if remote_model is not None:
        #~ raise Exception("get_field(%r,%r) got a remote model ?!" % (model,name))
    return fld


class UnresolvedField(object):

    """
    Returned by :func:`resolve_field` if the specified field doesn't exist.
    This case happens when sphinx autodoc tries to import a module.
    See ticket :srcref:`docs/tickets/4`.
    """

    def __init__(self, name):
        self.name = name
        self.verbose_name = "Unresolved Field " + name


def resolve_field(name, app_label=None):
    """Returns the field descriptor specified by the string `name` which
    should be either `model.field` or `app_label.model.field`.

    """
    l = name.split('.')
    if len(l) == 3:
        app_label = l[0]
        del l[0]
    if len(l) == 2:
        # print "models.get_model(",app_label,l[0],False,")"
        #~ model = models.get_model(app_label,l[0],False)
        model = models.get_model(app_label, l[0])
        if model is None:
            raise FieldDoesNotExist("No model named '%s.%s'" %
                                    (app_label, l[0]))
        fld, remote_model, direct, m2m = model._meta.get_field_by_name(l[1])
        #~ try:
            #~ fld, remote_model, direct, m2m = model._meta.get_field_by_name(l[1])
        #~ except FieldDoesNotExist:
            #~ return UnresolvedField(name)
        assert remote_model is None or issubclass(model, remote_model), \
            "resolve_field(%r) : remote model is %r (expected None or base of %r)" % (
                name, remote_model, model)
        return fld
    raise FieldDoesNotExist(name)
    #~ return UnresolvedField(name)


def navinfo(qs, elem):
    """Return a dict with navigation information for the given model
    instance `elem` within the given queryset.  The dictionary
    contains the following keys:
    
    :recno:   row number (index +1) of elem in qs
    :first:   pk of the first element in qs (None if qs is empty)
    :prev:    pk of the previous element in qs (None if qs is empty)
    :next:    pk of the next element in qs (None if qs is empty)
    :last:    pk of the last element in qs (None if qs is empty)
    :message: text "Row x of y" or "No navigation"

    """
    first = None
    prev = None
    next = None
    last = None
    recno = 0
    message = None
    #~ LEN = ar.get_total_count()
    if isinstance(qs, list):
        LEN = len(qs)
        id_list = [obj.pk for obj in qs]
        #~ logger.info('20130714')
    else:
        LEN = qs.count()
        # this algorithm is clearly quicker on queries with a few thousand rows
        id_list = list(qs.values_list('pk', flat=True))
    if LEN > 0:
        """
        Uncommented the following assert because it failed in certain circumstances 
        (see `/blog/2011/1220`)
        """
        #~ assert len(id_list) == ar.total_count, \
            #~ "len(id_list) is %d while ar.total_count is %d" % (len(id_list),ar.total_count)
        #~ print 20111220, id_list
        try:
            i = id_list.index(elem.pk)
        except ValueError:
            pass
        else:
            recno = i + 1
            first = id_list[0]
            last = id_list[-1]
            if i > 0:
                prev = id_list[i - 1]
            if i < len(id_list) - 1:
                next = id_list[i + 1]
            message = _("Row %(rowid)d of %(rowcount)d") % dict(
                rowid=recno, rowcount=LEN)
    if message is None:
        message = _("No navigation")
    return dict(
        first=first, prev=prev, next=next, last=last, recno=recno,
        message=message)


class Handle:
    """Base class for :class:`lino.core.tables.TableHandle`,
    :class:`lino.core.frames.FrameHandle` etc.

    The "handle" of an actor is responsible for expanding layouts into
    sets of (renderer-specific) widgets (called "elements"). This
    operation is done once per actor per renderer.

    """
    def __init__(self):
        self.ui = settings.SITE.ui

    def setup(self, ar):
        self.ui.setup_handle(self, ar)
        #~ settings.SITE.ui.setup_handle(self,ar)


class Parametrizable(object):
    """Base class for both Actors and Actions.


    .. method:: FOO_choices

        For every parameter field named "FOO", if the action has a method
        called "FOO_choices" (which must be decorated by
        :func:`dd.chooser`), then this method will be installed as a
        chooser for this parameter field.


    """

    active_fields = None  # 20121006
    master_field = None
    known_values = None

    parameters = None
    """
    User-definable parameter fields for this actor or action.
    Set this to a `dict` of `name = models.XyzField()` pairs.

    TODO: write documentation.
    """

    params_layout = None
    """
    The layout to be used for the parameter panel.
    If this table or action has parameters, specify here how they
    should be laid out in the parameters panel.
    """

    params_panel_hidden = False
    """
    If this table has parameters, set this to True if the parameters
    panel should be initially hidden when this table is being
    displayed.

    """

    _layout_class = NotImplementedError

    def get_window_layout(self, actor):
        return self.params_layout

    def get_window_size(self, actor):
        wl = self.get_window_layout(actor)
        if wl is not None:
            return wl.window_size


class Permittable(object):

    """Base class for objects that have view permissions control.

    :class:`lino.core.actors.Actor` would be a subclass, but is a
    special case since actors never get instantiated.

    """

    required = {}
    """
    The permissions required to view this actor.
    A dict with permission requirements.
    See :func:`lino.core.perms.make_permission_handler`.
    """

    # internally needed for make_permission_handler
    workflow_state_field = None
    # internally needed for make_permission_handler
    workflow_owner_field = None
    #~ readonly = True

    debug_permissions = False
    """
    Whether to log :ref:`debug_permissions` for this action.
    
    """

    def add_requirements(self, **kw):
        return add_requirements(self, **kw)

    def get_view_permission(self, profile):
        raise NotImplementedError()


def add_requirements(obj, **kw):
    """Add the specified requirements to `obj`.  `obj` can be an
    :class:`lino.core.actors.Actor` or any :class:`Permittable`.
    Application code uses this indirectly through the shortcut methods
    :meth:`lino.core.actors.Actor.add_view_requirements` or a
    :meth:`Permittable.add_requirements`.

    """
    #~ logger.info("20120927 perms.set_required %r",kw)
    new = dict()
    #~ new.update(getattr(obj,'required',{}))
    new.update(obj.required)
    new.update(kw)
    obj.required = new


class InstanceAction(object):
    """Volatile object which wraps a given action to be run on a given
    model instance.

    """

    def __init__(self, action, actor, instance, owner):
        #~ print "Bar"
        #~ self.action = action
        self.bound_action = actor.get_action_by_name(action.action_name)
        if self.bound_action is None:
            raise Exception("%s has not action %r" % (actor, action))
            # Happened 20131020 from lino.modlib.beid.eid_info() :
            # When `use_eid_jslib` was False, then
            # `Action.attach_to_actor` returned False.
        self.instance = instance
        self.owner = owner

    def __str__(self):
        return "{0} on {1}".format(self.bound_action, obj2str(self.instance))

    def run_from_code(self, ar, **kw):
        ar.selected_rows = [self.instance]
        return self.bound_action.action.run_from_code(ar)

    def run_from_ui(self, ar, **kw):
        ar.selected_rows = [self.instance]
        self.bound_action.action.run_from_ui(ar)

    def run_from_session(self, ses, **kw):
        #~ print self,args, kw
        ar = self.bound_action.request(**kw)
        ar.setup_from(ses)
        ar.selected_rows = [self.instance]
        self.bound_action.action.run_from_code(ar)
        return ar.response

    def __call__(self, *args, **kwargs):
        return self.run_from_session(*args, **kwargs)

    def as_button_elem(self, ar, label=None, **kwargs):
        return settings.SITE.ui.row_action_button(
            self.instance, ar, self.bound_action, label, **kwargs)

    def as_button(self, *args, **kwargs):
        """Return a HTML chunk with a "button" which, when clicked, will
        execute this action on this instance.  This is being used in
        the :ref:`lino.tutorial.polls`.

        """
        return E.tostring(self.as_button_elem(*args, **kwargs))

    def get_row_permission(self, ar):
        state = self.bound_action.actor.get_row_state(self.instance)
        logger.info("20150202 ia.get_row_permission() %s using %s",
                    self, state)
        return self.bound_action.get_row_permission(ar, self.instance, state)


class ParameterPanel(object):
    """A utility class for defining reusable definitions for
    :attr:`parameters <lino.core.actors.Actor.parameters>`.

    """
    def __init__(self, **kw):
        self.fields = kw

    def values(self, *args, **kw):
        return self.fields.values(*args, **kw)

    def keys(self, *args, **kw):
        return self.fields.keys(*args, **kw)

    def __iter__(self, *args, **kw):
        return self.fields.__iter__(*args, **kw)

    def __len__(self, *args, **kw):
        return self.fields.__len__(*args, **kw)

    def __getitem__(self, *args, **kw):
        return self.fields.__getitem__(*args, **kw)

    def get(self, *args, **kw):
        return self.fields.get(*args, **kw)

    def items(self, *args, **kw):
        return self.fields.items(*args, **kw)


class Requirements(object):

    """Not yet used. TODO: implement requirements as a class.

    - handle conversions (like accepting both list and string for
      `user_groups` )
    - implement loosen_requirements as __or__()
    - implement add_requirements as __and__()

    """
    user_level = None
    user_groups = None
    states = None
    allow = None
    auth = True
    owner = None


class ChangeWatcher(object):
    """Lightweight volatile object to watch changes and send the
    :attr:`on_ui_updated <lino.core.signals.on_ui_updated>` signal.

    The receiver function can use:

    - `sender.watched` : .

    - `original_state`: a `dict` containing (fieldname --> value)
      before the change.

    """

    watched = None
    """The model instance which has been changed and caused the signal."""

    def __init__(self, watched):
        self.original_state = dict(watched.__dict__)
        self.watched = watched
        #~ self.is_new = is_new
        #~ self.request

    def get_updates(self, ignored_fields=frozenset(), watched_fields=None):
        """Yield a list of (fieldname, oldvalue, newvalue) tuples for each
        modified field. Optional argument `ignored_fields` can be a
        set of fieldnames to be ignored.

        """
        for k, old in self.original_state.iteritems():
            if not k in ignored_fields:
                if watched_fields is None or k in watched_fields:
                    new = self.watched.__dict__.get(k, NOT_PROVIDED)
                    if old != new:
                        yield k, old, new

    def is_dirty(self):
        #~ if self.is_new:
            #~ return True
        for k, v in self.original_state.iteritems():
            if v != self.watched.__dict__.get(k, NOT_PROVIDED):
                return True
        return False

    def send_update(self, request):
        #~ print "ChangeWatcher.send_update()", self.watched
        on_ui_updated.send(sender=self, request=request)


def error2str(self, e):
    """Convert the given Exception object into a string, but handling
    ValidationError specially.
    """
    if isinstance(e, exceptions.ValidationError):
        md = getattr(e, 'message_dict', None)
        if md is not None:
            def fieldlabel(name):
                de = self.get_data_elem(name)
                return force_unicode(getattr(de, 'verbose_name', name))
            return '\n'.join([
                "%s : %s" % (
                    fieldlabel(k), self.error2str(v))
                for k, v in md.items()])
        return '\n'.join(e.messages)
    return unicode(e)
