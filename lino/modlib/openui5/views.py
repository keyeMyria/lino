# -*- coding: UTF-8 -*-
# Copyright 2009-2017 Luc Saffre
# License: BSD (see file COPYING for details)

"""Views for `lino.modlib.bootstrap3`.

"""
from __future__ import division
from past.utils import old_div

import logging
logger = logging.getLogger(__name__)

from django import http
from django.conf import settings
from django.views.generic import View
from django.core import exceptions
from django.utils.translation import ugettext as _
from django.utils.translation import get_language
# from django.contrib import auth
from lino.core import auth


# from lino.api import dd
from lino.core import constants
# from lino.core import auth
from lino.core.requests import BaseRequest
from lino.core.tablerequest import TableRequest
import json

from lino.core.views import requested_actor, action_request
from lino.core.views import json_response, json_response_kw

from lino.core.views import action_request
from lino.core.utils import navinfo
from etgen.html import E, tostring
from etgen import html as xghtml

from lino.api import rt
import re

PLAIN_PAGE_LENGTH = 15

MENUS = dict()


# Taken from lino.modlib.extjs.views
NOT_FOUND = "%s has no row with primary key %r"
def elem2rec_empty(ar, ah, elem, **rec):
    """
    Returns a dict of this record, designed for usage by an EmptyTable.
    """
    #~ rec.update(data=rh.store.row2dict(ar,elem))
    rec.update(data=elem._data)
    #~ rec = elem2rec1(ar,ah,elem)
    #~ rec.update(title=_("Insert into %s...") % ar.get_title())
    rec.update(title=ar.get_action_title())
    rec.update(id=-99998)
    #~ rec.update(id=elem.pk) or -99999)
    if ar.actor.parameters:
        rec.update(
            param_values=ar.actor.params_layout.params_store.pv2dict(
                ar, ar.param_values))
    return rec

class Restful(View):

    """
    Used to collaborate with a restful Ext.data.Store.
    """

    def post(self, request, app_label=None, actor=None, pk=None):
        rpt = requested_actor(app_label, actor)
        ar = rpt.request(request=request)

        instance = ar.create_instance()
        # store uploaded files.
        # html forms cannot send files with PUT or GET, only with POST
        if ar.actor.handle_uploaded_files is not None:
            ar.actor.handle_uploaded_files(instance, request)

        data = request.POST.get('rows')
        data = json.loads(data)
        ar.form2obj_and_save(data, instance, True)

        # Ext.ensible needs list_fields, not detail_fields
        ar.set_response(
            rows=[ar.ah.store.row2dict(
                ar, instance, ar.ah.store.list_fields)])
        return json_response(ar.response)

    # def delete(self, request, app_label=None, actor=None, pk=None):
    #     rpt = requested_actor(app_label, actor)
    #     ar = rpt.request(request=request)
    #     ar.set_selected_pks(pk)
    #     return delete_element(ar, ar.selected_rows[0])

    def get(self, request, app_label=None, actor=None, pk=None):
        """
        Works, but is ugly to get list and detail
        """
        rpt = requested_actor(app_label, actor)


        action_name = request.GET.get(constants.URL_PARAM_ACTION_NAME,
                                      rpt.default_elem_action_name)
        fmt = request.GET.get(
            constants.URL_PARAM_FORMAT,constants.URL_FORMAT_JSON)
        sr = request.GET.getlist(constants.URL_PARAM_SELECTED)
        if not sr:
            sr = [pk]
        ar = rpt.request(request=request, selected_pks=sr)
        if pk is None:
            rh = ar.ah
            rows = [
                rh.store.row2dict(ar, row, rh.store.all_fields)
                for row in ar.sliced_data_iterator]
            kw = dict(count=ar.get_total_count(), rows=rows)
            kw.update(title=str(ar.get_title()))
            return json_response(kw)

        else: #action_name=="detail": #ba.action.opens_a_window:

            ba = rpt.get_url_action(action_name)
            ah = ar.ah
            ar = ba.request(request=request, selected_pks=sr)
            elem = ar.selected_rows[0]
            if fmt == constants.URL_FORMAT_JSON:
                if pk == '-99999':
                    elem = ar.create_instance()
                    datarec = ar.elem2rec_insert(ah, elem)
                elif pk == '-99998':
                    elem = ar.create_instance()
                    datarec = elem2rec_empty(ar, ah, elem)
                elif elem is None:
                    datarec = dict(
                        success=False, message=NOT_FOUND % (rpt, pk))
                else:
                    datarec = ar.elem2rec_detailed(elem)
                return json_response(datarec)


    def put(self, request, app_label=None, actor=None, pk=None):
        rpt = requested_actor(app_label, actor)
        ar = rpt.request(request=request)
        ar.set_selected_pks(pk)
        elem = ar.selected_rows[0]
        rh = ar.ah

        data = http.QueryDict(request.body).get('rows')
        data = json.loads(data)
        a = rpt.get_url_action(rpt.default_list_action_name)
        ar = rpt.request(request=request, action=a)
        ar.renderer = settings.SITE.kernel.extjs_renderer
        ar.form2obj_and_save(data, elem, False)
        # Ext.ensible needs list_fields, not detail_fields
        ar.set_response(
            rows=[rh.store.row2dict(ar, elem, rh.store.list_fields)])
        return json_response(ar.response)


def http_response(ar, tplname, context):
    "Deserves a docstring"
    u = ar.get_user()
    lang = get_language()
    k = (u.user_type, lang)
    menu = MENUS.get(k, None)
    if menu is None:
        menu = settings.SITE.get_site_menu(None, u.user_type)
        ui5 = settings.SITE.plugins.openui5
        if False:  # 20150803 home button now in base.html
            assert ui5.renderer is not None
            url = ui5.build_plain_url()
            menu.add_url_button(url, label=_("Home"))
        e = ui5.renderer.show_menu(ar, menu)
        menu = tostring(e)
        MENUS[k] = menu
    context.update(menu=menu)
    context = ar.get_printable_context(**context)
    context['ar'] = ar
    context['memo'] = ar.parse_memo  # MEMO_PARSER.parse
    env = settings.SITE.plugins.jinja.renderer.jinja_env
    template = env.get_template(tplname)

    response = http.HttpResponse(
        template.render(**context),
        content_type='text/html;charset="utf-8"')

    return response


def XML_response(ar, tplname, context):
    "Deserves a docstring"
    # u = ar.get_user()
    # lang = get_language()
    # k = (u.user_type, lang)
    # menu = MENUS.get(k, None)
    # if menu is None:
    #     menu = settings.SITE.get_site_menu(None, u.user_type)
    #     ui5 = settings.SITE.plugins.openui5
    #     if False:  # 20150803 home button now in base.html
    #         assert ui5.renderer is not None
    #         url = ui5.build_plain_url()
    #         menu.add_url_button(url, label=_("Home"))
    #     e = ui5.renderer.show_menu(ar, menu)
    #     menu = tostring(e)
    #     MENUS[k] = menu
    # context.update(menu=menu)
    context = ar.get_printable_context(**context)
    # context['ar'] = ar
    # context['memo'] = ar.parse_memo  # MEMO_PARSER.parse
    env = settings.SITE.plugins.jinja.renderer.jinja_env
    template = env.get_template(tplname)
    def bind(*args):
        return "{" + escape("".join(args)) + "}"
    context.update(
        # Because it's a pain to excape {x} in jinja
        bind=bind
    )
    def p(*args):
        print(args),
        return ""

    env.filters.update(
        p=p)

    response = http.HttpResponse(
        template.render(**context),
        content_type='text/html;charset="utf-8"')

    return response


def buttons2pager(buttons, title=None):
    items = []
    if title:
        items.append(E.li(E.span(title)))
    for symbol, label, url in buttons:
        if url is None:
            items.append(E.li(E.span(symbol), **{'class':"disabled"}))
        else:
            items.append(E.li(E.a(symbol, href=url)))
    # Bootstrap version 2.x
    # return E.div(E.ul(*items), class_='pagination')
    return E.ul(*items, **{'class':'pagination pagination-sm'})


def table2html(ar, as_main=True):
    """Represent the given table request as an HTML table.

    `ar` is the request to be rendered, an instance of
    :class:`lino.core.tablerequest.TableRequest`.

    The returned HTML enclosed in a ``<div>`` tag and generated using
    :mod:`etgen.html`.

    If `as_main` is True, include additional elements such as a paging
    toolbar. (This argument is currently being ignored.)

    """
    # as_main = True
    t = xghtml.Table()
    t.set('class', "table table-striped table-hover")
    if ar.limit is None:
        ar.limit = PLAIN_PAGE_LENGTH
    pglen = ar.limit
    if ar.offset is None:
        page = 1
    else:
        """
        (assuming pglen is 5)
        offset page
        0      1
        5      2
        """
        page = int(old_div(ar.offset, pglen)) + 1

    ar.dump2html(t, ar.sliced_data_iterator)
    if not as_main:
        url = ar.get_request_url()  # open in own window
        return E.div(
            E.div(
                E.div(
                    E.a(
                        E.span(**{'class':"glyphicon glyphicon-folder-open"}),
                        href=url, style="margin-left: 4px;",
                        **{'class':"btn btn-default pull-right"}),
                    E.h5(ar.get_title(), style="display: inline-block;"), **{'class':"panel-title"}),
                      **{'class':"panel-heading"}),
                t.as_element(),
            style="display: inline-block;",
            **{'class':"panel panel-default"})

    buttons = []
    kw = dict()
    kw = {}
    if pglen != PLAIN_PAGE_LENGTH:
        kw[constants.URL_PARAM_LIMIT] = pglen

    if page > 1:
        kw[constants.URL_PARAM_START] = pglen * (page - 2)
        prev_url = ar.get_request_url(**kw)
        kw[constants.URL_PARAM_START] = 0
        first_url = ar.get_request_url(**kw)
    else:
        prev_url = None
        first_url = None
    buttons.append(('<<', _("First page"), first_url))
    buttons.append(('<', _("Previous page"), prev_url))

    next_start = pglen * page
    if next_start < ar.get_total_count():
        kw[constants.URL_PARAM_START] = next_start
        next_url = ar.get_request_url(**kw)
        last_page = int(old_div((ar.get_total_count() - 1), pglen))
        kw[constants.URL_PARAM_START] = pglen * last_page
        last_url = ar.get_request_url(**kw)
    else:
        next_url = None
        last_url = None
    buttons.append(('>', _("Next page"), next_url))
    buttons.append(('>>', _("Last page"), last_url))

    return E.div(buttons2pager(buttons), t.as_element())


def layout2html(ar, elem):

    wl = ar.bound_action.get_window_layout()
    #~ print 20120901, wl.main
    lh = wl.get_layout_handle(settings.SITE.kernel.default_ui)

    items = list(lh.main.as_plain_html(ar, elem))
    # if navigator:
    #     items.insert(0, navigator)
    #~ print tostring(E.div())
    #~ if len(items) == 0: return ""
    return E.form(*items)
    #~ print 20120901, lh.main.__html__(ar)

class Tickets(View):
    """
    Static View for Tickets,
    Uses a template for generating the UI rather then layouts
    """
    def get(self, request, app_label="tickets", actor="AllTickets"):
        ar = action_request(app_label, actor, request, request.GET, True)
        ar.renderer = settings.SITE.plugins.openui5.renderer

        # ui = settings.SITE.plugins.openui5
        # main = settings.SITE.get_main_html(ar.request, extjs=ui)
        # main = ui.renderer.html_text(main)
        # print(main)
        context = dict(
            title=ar.get_title(),
            heading=ar.get_title(),
            # main=main,
        )

        if isinstance(ar, TableRequest):
            context.update(main=table2html(ar))
        else:
            context.update(main=layout2html(ar, None))

        context.update(ar=ar)
        return http_response(ar,"openui5/tickets_ui5.html", context)


class MainHtml(View):

    def get(self, request, *args, **kw):
        #~ logger.info("20130719 MainHtml")
        settings.SITE.startup()
        #~ raise Exception("20131023")
        ar = BaseRequest(request)
        html = settings.SITE.get_main_html(
            request, extjs=settings.SITE.plugins.openui5)
        html = settings.SITE.plugins.openui5.renderer.html_text(html)
        ar.success(html=html)
        return json_response(ar.response, ar.content_type)

class Connector(View):
    """
    Static View for Tickets,
    Uses a template for generating the XML views  rather then layouts
    """
    def get(self, request, name=None):
        # ar = action_request(None, None, request, request.GET, True)
        ar = BaseRequest(
            # user=user,
            request=request,
            renderer=settings.SITE.plugins.openui5.renderer)
        u = ar.get_user()

        context = dict(
            menu=settings.SITE.get_site_menu(None, u.user_type)
        )

        print(u)
        # print name
        if name.startswith("view/"):
            tplname = "openui5/" + name

        elif name.startswith("dialog/SignInActionFormPanel"):
            tplname = "openui5/fragment/SignInActionFormPanel.fragment.xml"

        elif name.startswith("menu/user/user.fragment.xml"):
            tplname = "openui5/fragment/UserMenu.fragment.xml"

        elif name.startswith("menu/"):
            tplname = "openui5/fragment/Menu.fragment.xml"
            sel_menu = name.split("/",1)[1].split('.',1)[0]
            # [05/Feb/2018 09:32:25] "GET /ui/menu/mailbox.fragment.xml HTTP/1.1" 200 325
            for i in context['menu'].items:
                if i.name == sel_menu:
                    context.update(dict(
                        opened_menu=i
                    ))
                    break
            else:
                raise Exception("No Menu with name %s"%sel_menu)
        elif name.startswith("grid/"): # Table/grid view
            # todo Get table data
            # "grid/tickets/AllTickets.view.xml"
            app_label, actor = re.match(r"grid\/(.+)\/(.+).view.xml$", name).groups()
            actor = rt.models.resolve(app_label + "." + actor)
            context.update({
                "actor": actor,
                "columns": actor.get_handle().get_columns(),
                "actions": actor.get_actions(),
                "title": actor.label,

            })
            tplname = "openui5/view/table.view.xml" # Change to "grid" to match action?
            # ar = action_request(app_label, actor, request, request.GET, True)
            # add to context

        elif name.startswith("detail"):  # Detail view
            # "detail/tickets/AllTickets.view.xml"
            app_label, actor = re.match(r"detail\/(.+)\/(.+).view.xml$", name).groups()
            actor = rt.models.resolve(app_label + "." + actor)
            detail_action = actor.  actions['detail']
            window_layout = detail_action.get_window_layout()
            layout_handle = window_layout.get_layout_handle(settings.SITE.plugins.openui5)
            layout_handle.main.elements # elems # Refactor into actor get method?
            context.update({
                "actor": actor,
                # "columns": actor.get_handle().get_columns(),
                "actions": actor.get_actions(),
                "title": actor.label, #
                # "main_elems": layout_handle.main.elements,
                "main": layout_handle.main,
                "layout_handle": layout_handle

            })
            tplname = "openui5/view/detail.view.xml"  # Change to "grid" to match action?
            # ar = action_request(app_label, actor, request, request.GET, True)
            # add to context

        else:
            raise Exception("Can't find a view for path: {}".format(name))

        return XML_response(ar, tplname, context)


class List(View):
    """Render a list of records.

    """
    def get(self, request, app_label=None, actor=None):
        ar = action_request(app_label, actor, request, request.GET, True)
        ar.renderer = settings.SITE.plugins.bootstrap3.renderer

        context = dict(
            title=ar.get_title(),
            heading=ar.get_title(),
        )

        if isinstance(ar, TableRequest):
            context.update(main=table2html(ar))
        else:
            context.update(main=layout2html(ar, None))

        context.update(ar=ar)
        return http_response(ar, ar.actor.list_html_template, context)


class Element(View):
    """Render a single record.

    """
    def get(self, request, app_label=None, actor=None, pk=None):
        # print(request, app_label, actor, pk)
        ar = action_request(app_label, actor, request, request.GET, False)
        ar.renderer = settings.SITE.plugins.bootstrap3.renderer

        navigator = None
        if pk and pk != '-99999' and pk != '-99998':
            elem = ar.get_row_by_pk(pk)
            if elem is None:
                raise http.Http404("%s has no row with primary key %r" %
                                   (ar.actor, pk))
                #~ raise Exception("20120327 %s.get_row_by_pk(%r)" % (rpt,pk))
            if ar.actor.show_detail_navigator:

                ni = navinfo(ar.data_iterator, elem)
                if ni:
                    # m = elem.__class__
                    buttons = []
                    #~ buttons.append( ('*',_("Home"), '/' ))

                    buttons.append(
                        ('<<', _("First page"), ar.pk2url(ni['first'])))
                    buttons.append(
                        ('<', _("Previous page"), ar.pk2url(ni['prev'])))
                    buttons.append(
                        ('>', _("Next page"), ar.pk2url(ni['next'])))
                    buttons.append(
                        ('>>', _("Last page"), ar.pk2url(ni['last'])))

                    navigator = buttons2pager(buttons)
                else:
                    navigator = E.p("No navinfo")
        else:
            elem = None


        # main = E.div(
        #     E.div(E.div(E.h5(ar.get_title(),
        #              style="display: inline-block;"),
        #         class_="panel-title"),
        #         class_="panel-heading"),
        #     E.div(layout2html(ar, elem),class_="panel-body"), # Content
        #     class_="panel panel-default",
        #     # style="display: inline-block;"
        # )


        main = layout2html(ar, elem)

        # The `method="html"` argument isn't available in Python 2.6,
        # only 2.7.  It is useful to avoid side effects in case of
        # empty elements: the default method (xml) writes an empty
        # E.div() as "<div/>" while in HTML5 it must be "<div></div>"
        # (and the ending / is ignored).

        #~ return tostring(main, method="html")
        #~ return tostring(main)
        # return main

        context = dict(
            title=ar.get_action_title(),
            obj=elem,
            form=main,
            navigator=navigator,
        )
        #~ template = web.jinja_env.get_template('detail.html')
        context.update(ar=ar)
        return http_response(ar, ar.actor.detail_html_template, context)

class Authenticate(View):
    def get(self, request, *args, **kw):
        action_name = request.GET.get(constants.URL_PARAM_ACTION_NAME)
        if action_name == 'logout':
            username = request.session.pop('username', None)
            auth.logout(request)
            # request.user = settings.SITE.user_model.get_anonymous_user()
            # request.session.pop('password', None)
            #~ username = request.session['username']
            #~ del request.session['password']
            target = '/'
            return http.HttpResponseRedirect(target)


            # ar = BaseRequest(request)
            # ar.success("User %r logged out." % username)
            # return ar.renderer.render_action_response(ar)
        raise http.Http404()

    def post(self, request, *args, **kw):
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = auth.authenticate(
            request, username=username, password=password)
        auth.login(request, user, backend=u'lino.core.auth.backends.ModelBackend')
        target = '/'
        return http.HttpResponseRedirect(target)
        # ar = BaseRequest(request)
        # mw = auth.get_auth_middleware()
        # msg = mw.authenticate(username, password, request)
        # if msg:
        #     request.session.pop('username', None)
        #     ar.error(msg)
        # else:
        #     request.session['username'] = username
        #     # request.session['password'] = password
        #     # ar.user = request....
        #     ar.success(("Now logged in as %r" % username))
        #     # print "20150428 Now logged in as %r (%s)" % (username, user)
        # return ar.renderer.render_action_response(ar)


class Index(View):
    """
    Render the main page.
    """
    def get(self, request, *args, **kw):
        # raise Exception("20171122 {} {}".format(
        #     get_language(), settings.MIDDLEWARE_CLASSES))
        ui = settings.SITE.plugins.bootstrap3
        # print("20170607", request.user)
        # assert ui.renderer is not None
        ar = BaseRequest(
            # user=user,
            request=request,
            renderer=ui.renderer)
        return index_response(ar)

def index_response(ar):
    ui = settings.SITE.plugins.openui5

    main = settings.SITE.get_main_html(ar.request, extjs=ui)
    main = ui.renderer.html_text(main)
    context = dict(
        title=settings.SITE.title,
        main=main,
    )
    # if settings.SITE.user_model is None:
    #     user = auth.AnonymousUser.instance()
    # else:
    #     user = request.subst_user or request.user
    # context.update(ar=ar)
    return http_response(ar, 'bootstrap3/index.html', context)
