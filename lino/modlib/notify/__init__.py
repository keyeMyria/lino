# Copyright 2008-2016 Luc Saffre
# License: BSD (see file COPYING for details)

"""Adds functionality for managing notification messages.

See :doc:`/specs/notify`.

.. autosummary::
   :toctree:

    models
    choicelists
    actions
    mixins
    utils
    fixtures.demo2

Templates used by this plugin
=============================

.. xfile:: notify/body.eml

    A Jinja template used for generating the body of the email when
    sending a message per email to its recipient.

    Available context variables:

    - ``obj`` -- The :class:`Message
      <lino.modlib.notify.models.Message>` instance being sent.

    - ``E`` -- The html namespace :mod:`lino.utils.xmlgen.html`

    - ``rt`` -- The runtime API :mod:`lino.api.rt`

    - ``ar`` -- The action request which caused the message. a
      :class:`BaseRequest <lino.core.requests.BaseRequest>` instance.

"""

from lino.api import ad, _

# from django.conf import settings

try:
    import redis
except:
    redis = False


class Plugin(ad.Plugin):
    "See :class:`lino.core.plugin.Plugin`."

    verbose_name = _("Messages")

    needs_plugins = ['lino.modlib.users', 'lino.modlib.gfks']

    media_name = 'js'

    # email_subject_template = "Message about {obj.owner}"
    # """The template used to build the subject lino of message emails.

    # :obj: is the :class:`Message
    #       <lino.modlib.notify.models.Message>` object.

    # """

    def get_used_libs(self, html=None):
        try:
            import channels
            version = channels.__version__
        except ImportError:
            version = self.site.not_found_msg
        name = "Channels ({})".format(
            "active" if self.site.use_websockets else "inactive")

        yield (name, version, "https://github.com/django/channels")

    def on_init(self):
        if self.site.use_websockets:
            self.needs_plugins.append('channels')

            sd = self.site.django_settings
            # the dict which will be used to create settings
            cld = {}
            sd['CHANNEL_LAYERS'] = {"default": cld}
            cld["BACKEND"] = "asgiref.inmemory.ChannelLayer"
            cld["ROUTING"] = "lino.modlib.notify.routing.channel_routing"
            if redis:
                try:
                    cld['BACKEND'] = "asgi_redis.RedisChannelLayer"
                    cld['CONFIG'] = {"hosts": [("localhost", 6379)], }
                except redis.ConnectionError:
                    pass

    def get_js_includes(self, settings, language):
        if self.site.use_websockets:
            if settings.DEBUG:
                yield self.build_lib_url(('push.js/push.min.js'))
            else:
                yield self.build_lib_url(('push.js/push.js'))

    def setup_main_menu(self, site, profile, m):
        p = site.plugins.office
        m = m.add_menu(p.app_label, p.verbose_name)
        m.add_action('notify.MyMessages')

    def setup_explorer_menu(self, site, profile, m):
        p = site.plugins.system
        m = m.add_menu(p.app_label, p.verbose_name)
        m.add_action('notify.AllMessages')

    def get_head_lines(self, site, request):
        from lino.utils.jsgen import py2js
        if not self.site.use_websockets:
            return
        user_name = "anony"
        if request.user.authenticated:
            user_name = request.user.username
        site_title = site.title or 'Lino-framework'

        js_to_add = """
    <script type="text/javascript">
    Ext.onReady(function() {
        // Note that the path doesn't matter for routing; any WebSocket
        // connection gets bumped over to WebSocket consumers
        var ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
        var ws_path = window.location.pathname + "lino/";
        console.log("Connecting to " + ws_path);
        var webSocketBridge = new channels.WebSocketBridge();
        var username = '%s' ;
        webSocketBridge.connect();
        lino_connecting = function() {
            console.log("lino_connecting");
            webSocketBridge.send({
                        "command": "user_connect",
                        "username": username
                    });
        }
        webSocketBridge.socket.addEventListener('open', function() {
            lino_connecting();
        });
        // Helpful debugging
        webSocketBridge.socket.onclose = function () {
            console.log("Disconnected from chat socket");
        }

        onGranted = console.log("onGranted");
        onDenied = console.log("onDenied");
        // Ask for permission if it's not already granted
        Push.Permission.request(onGranted,onDenied);

        webSocketBridge.listen(function(action, stream) {
        console.log(action, stream);
            try {
                Push.create( %s , {
                    body: action['body'],
                    icon: '/static/img/lino-logo.png',
                    onClick: function () {
                        window.focus();
                        Lino.viewport.refresh();
                        this.close();
                    }
                });
                if (false && Number.isInteger(action["id"])){
                    webSocketBridge.stream('lino').send({message_id: action["id"]})
                    webSocketBridge.send(JSON.stringify({
                                    "command": "seen",
                                    "message_id": action["id"],
                                }));
                            }
                }
            catch(err) {
                console.log(err.message);
            }
        })});
    // end of onReady()"
    </script>
        """ % (user_name, py2js(site_title))
        yield js_to_add

    def get_dashboard_items(self, user):
        if user.authenticated:
            # yield ActorItem(
            #     self.actors.notify.MyMessages, header_level=None)
            yield self.site.actors.notify.MyMessages
