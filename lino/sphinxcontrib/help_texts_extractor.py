# -*- coding: UTF-8 -*-
# Copyright 2016 Luc Saffre
# License: BSD (see file COPYING for details)
'''Causes a :xfile:`help_texts.py` file to be generated after each complete built of the doctree. 

The :xfile:`help_texts.py` file contains object descriptions to be
installed as the `help_text` attribute of certain UI widgets (actions,
database fields, ...)

Overview
========

Without help_text builder::

    class MyModel(dd.Model):
        """MyModel is an important example."""

        universe = models.CharField(_("First field"),
            blank=True, max_length=100, help_text=_("""
    The first field contains an optional answer to the
    question about life, the universe and everything.
    """))

With help_text builder::

    class MyModel(dd.Model):
        """MyModel is an important example.

        .. attribute:: universe

            The first field contains an optional answer to the
            question about life, the universe and everything.

        """

        universe = models.CharField(_("First field"),
            blank=True, max_length=100)

Advantages:

- Better readability.

- As an application developer you don't need to worry about Python
  syntax consideration when editing your help text

- Same source is used for both the API and the UI. You don't need to
  write (and maintain) these texts twice.

Note that only the *first* paragraph of the content of every
:rst:dir:`class` and :rst:dir:`attribute` directive is taken as help
text, and that any links are being removed.

Note also that any formatting is removed.


The :xfile:`help_texts.py` file
===============================


.. xfile:: help_texts.py

When a Lino :class:`Site <lino.core.site.Site>` initializes, it looks
for a file named :xfile:`help_texts.py` in every plugin directory.  If
such a file exists, Lino imports it and expects it to contain a
:class:`dict` of the form::

    from lino.api import _
    help_texts = {
        'foo': _("A foo is a bar without baz.")
    }

These files are automatically generated when a full build is being
done.

See also :blogref:`20160620`.

:meth:`lino.core.site.Site.install_help_text`
:meth:`lino.core.site.Site.load_help_texts`

Usage
=====

In your :xfile:`conf.py` file, add this line::

    from lino.sphinxcontrib.help_text_builder import setup

Or, if you have already your own :func:`setup` function defined,
import it under another name and call it from within your function::

    from lino.sphinxcontrib.help_text_builder import setup as htsetup
    def setup(app):
        ...
        htsetup(app)
        ...
    
Run sphinx-build using::

    $ sphinx-build -b help_texts . tmp

Copy the result to the right place, e.g. to the main plugin of your
application::

    $ cp tmp/help_texts.py ../lino_voga/lib/voga/


Internals
=========

This builder traverses the doctree in order to find `object
descriptions
<http://www.sphinx-doc.org/en/stable/extdev/nodes.html>`_, i.e.  text
nodes defined by Sphinx and inserted e.g. by the :rst:dir:`class` and
:rst:dir:`attribute` directives (which have been inserted by autodoc
and autosummary).

Example of a class description::

    <desc desctype="class" domain="py" noindex="False" objtype="class">
        <desc_signature class="" first="False" fullname="Plan" ids="..." module="..." names="...">
        <desc_annotation>class </desc_annotation>
            <desc_addname>lino_xl.lib.invoicing.models.</desc_addname>
            <desc_name>Plan</desc_name>
            <desc_parameterlist>
                <desc_parameter>*args</desc_parameter>
                <desc_parameter>**kwargs</desc_parameter>
            </desc_parameterlist>
        </desc_signature>
        <desc_content>
            <paragraph>Bases: <reference internal="False" reftitle="(in Lino v1.7)" refuri="http://www.lino-framework.org/api/lino.modlib.users.mixins.html#lino.modlib.users.mixins.UserAuthored"><literal classes="xref py py-class">lino.modlib.users.mixins.UserAuthored</literal></reference>
            </paragraph>
            <paragraph>An <strong>invoicing plan</strong> is a rather temporary database object which represents the plan of a given user to have Lino generate a series of invoices.
            </paragraph>
            <index entries="..."/>
        <desc desctype="attribute" objtype="attribute">
            <desc_signature class="Plan" first="False" fullname="Plan.user" ids="..." module="..." names="...">
                <desc_name>user</desc_name>
            </desc_signature>
      <desc_content/>
    </desc>
    <desc desctype="attribute" ... objtype="attribute">
        <desc_signature class="Plan" first="False" fullname="Plan.journal" ids="..." module="..." names="...">
            <desc_name>journal</desc_name>
        </desc_signature>
        <desc_content>
            <paragraph>The journal where to create invoices.  When this field is
            empty, you can fill the plan with suggestions but cannot
            execute the plan.</paragraph>
        </desc_content>
    </desc>
    ...

Example of a field description::

    <desc desctype="attribute" domain="py" noindex="False" objtype="attribute">
      <desc_signature class="Plan" first="False" fullname="Plan.journal" 
            ids="lino_xl.lib.invoicing.models.Plan.journal" 
            module="lino_xl.lib.invoicing.models" 
            names="lino_xl.lib.invoicing.models.Plan.journal">
        <desc_name>journal</desc_name>
      </desc_signature>
      <desc_content>
        <paragraph>
          The journal where to create invoices.  When this field is
          empty, you can fill the plan with suggestions but cannot
          execute the plan.
        </paragraph>
      </desc_content>
    </desc>

'''

from __future__ import print_function
from __future__ import unicode_literals

from collections import OrderedDict

import six

from docutils import nodes
from docutils import core
from sphinx import addnodes

from importlib import import_module

from unipath import Path

useless_starts = set(['lino.core'])
useless_endings = set(['.My', '.ByUser'])
# useless_endings = set(['.VentilatingTable', '.My', '.ByUser',
#                        '.Table', '.AbstractTable', '.VirtualTable',
#                        '.Actor'])


def node2html(node):
    parts = core.publish_from_doctree(node, writer_name="html")
    return parts['body']


class HelpTextExtractor(object):

    def initialize(self, app):
        self.name2dict = dict()
        self.name2file = dict()
        # we must write our files only when all documents have been
        # processed (i.e. usually after a "clean")
        self.docs_processed = 0
        
        targets = app.env.config.help_texts_builder_targets
        # print(20160725, targets)
        for root, modname in targets.items():
            mod = import_module(modname)
            htf = Path(mod.__file__).parent.child('help_texts.py')
            # if not htf.exists():
            #     raise Exception("No such file: {}".format(htf))
            self.name2file[root] = htf
            self.name2dict[root] = OrderedDict()
            
        print("Collecting help texts for {}".format(
            ' '.join(self.name2file.values())))

    def extract_help_texts(self, app, doctree):
        # if docname != 'api/lino_xl.lib.invoicing.models':
        #     return
        # print(doctree)
        # return

        # for node in doctree.traverse():
        #     self.node_classes.add(node.__class__)
        for node in doctree.traverse(addnodes.desc):
            if node['domain'] == 'py':
                if node['objtype'] == 'class':
                    self.store_content(node)
                elif node['objtype'] == 'attribute':
                    self.store_content(node)
        # for node in doctree.traverse(nodes.field):
        #     self.fields.add(node.__class__)
        self.docs_processed += 1

    def write_help_texts_files(self, app, exception):
        if exception:
            return
        if self.docs_processed < len(app.env.found_docs):
            app.info(
                "Don't write help_texts.py files because "
                "only {0} of {1} docs have been processed".format(
                    self.docs_processed,
                    len(app.env.found_docs)))
            return
        for k, fn in self.name2file.items():
            texts = self.name2dict.get(k, None)
            if not texts:
                app.info("No help texts for %s", k)
                continue
            # fn = os.path.join(self.outdir, 'help_texts.py')
            print("Writing {} help texts for {} to {}".format(
                len(texts), k, fn))

            fd = file(fn, "w")

            def writeln(s):
                s = s.encode('utf-8')
                fd.write(s)
                fd.write("\n")

            writeln("# -*- coding: UTF-8 -*-")
            writeln("# generated by lino.sphinxcontrib.help_text_builder")
            writeln("from __future__ import unicode_literals")
            writeln("from django.utils.translation import ugettext_lazy as _")
            writeln("help_texts = {")
            for k, v in texts.items():
                writeln('''    '{}' : _("""{}"""),'''.format(k, v))
            writeln("}")
            fd.close()

    def store_content(self, node):
        sig = []
        content = []
        for c in node.children:
            if isinstance(c, addnodes.desc_content):
                for cc in c.children:
                    if isinstance(cc, nodes.paragraph):
                        p = cc.astext()
                        if not p.startswith("Bases:"):
                            if len(content) == 0:
                                content.append(p)
            elif isinstance(c, addnodes.desc_signature):
                sig.append(c)
        # if len(sig) != 1:
        #     raise Exception("sig is {}!".format(sig))
        sig = sig[0]
        # sig = list(node.traverse(addnodes.desc_signature))[0]
        # content = [
        #     p.astext() for p in node.traverse(addnodes.desc_content)]
        # content = [p for p in content if not p.startswith("Bases:")]
        if not content:
            return
        content = '\n'.join(content)
        if '"""' in content:
            msg = '{} : First paragraph of content may not contain \'"""\'. '
            raise Exception(msg.format(sig['names'][0]))
        if content.startswith('"'):
            content = " " + content
        if content.endswith('"'):
            content += " "
            # msg = '{} : First paragraph of content may not end with \'"\'.'
            # self.warn(msg.format(sig['names'][0]))
        for name in sig['names']:
            self.sig2dict(name, content)

    def sig2dict(self, name, value):
        for e in useless_starts:
            if name.startswith(e):
                return
        for e in useless_endings:
            if name.endswith(e):
                return
        for root, d in self.name2dict.items():
            if name.startswith(root):
                d[name] = value


def setup(app):
    hte = HelpTextExtractor()
    app.add_config_value('help_texts_builder_targets', {}, 'env')
    app.connect(six.binary_type('builder-inited'),
                hte.initialize)
    app.connect(six.binary_type('doctree-read'),
                hte.extract_help_texts)

    app.connect(six.binary_type('build-finished'),
                hte.write_help_texts_files)


