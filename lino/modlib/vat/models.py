# Copyright 2012-2015 Luc Saffre
# License: BSD (see file COPYING for details)

"""
Database models for `lino.modlib.excerpts`.

.. autosummary::

It defines two database models :class:`VatRule` and
:class:`PaymentTerm`, and a series of mixins which are used in
:mod:`lino.modlib.ledger`, :mod:`lino.modlib.sales` and other apps.

"""

from __future__ import unicode_literals
from __future__ import print_function

import logging
logger = logging.getLogger(__name__)

import datetime
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from django.db import models
from django.conf import settings
from django.utils.translation import ugettext_lazy as _
from django.db.models import Q

from lino.mixins.periods import DatePeriod
from lino.mixins import Sequenced
from lino.mixins import BabelNamed
from lino.modlib.system.mixins import PeriodEvents

from lino.api import dd, rt

from .utils import remove_vat

config = dd.plugins.vat


def get_default_vat_regime():
    return config.default_vat_regime


def get_default_vat_class():
    return config.default_vat_class


partners = dd.resolve_app(settings.SITE.partners_app_label)
accounts = dd.resolve_app('accounts')

ZERO = Decimal('0.00')
ONE = Decimal('1.00')


class VatClasses(dd.ChoiceList):
    """
    A VAT class is a direct or indirect property of a trade object
    (e.g. a Product) which determines the VAT *rate* to be used.  It
    does not contain the actual rate because this still varies
    depending on your country, the time and type of the operation, and
    possibly other factors.

    Typical content is as follows (but applications may redefine or
    extend this list in :meth:`lino.core.site.Site.setup_choicelists`):

    .. django2rst:: rt.show("vat.VatRegimes")

    """
    verbose_name = _("VAT Class")
add = VatClasses.add_item
add('0', _("Exempt"), 'exempt')    # post stamps, ...
add('1', _("Reduced"), 'reduced')  # food, books,...
add('2', _("Normal"), 'normal')    # everything else


class VatRegime(dd.Choice):
    "Base class for choices of :class:`VatRegimes`."

    item_vat = True
    "Whether unit prices are VAT included or not."


class VatRegimes(dd.ChoiceList):
    """
    The VAT regime is a classification of the way how VAT is being
    handled, e.g. whether and how it is to be paid.

    Typical content is as follows (but applications may redefine or
    extend this list in :meth:`lino.core.site.Site.setup_choicelists`):

    .. django2rst:: rt.show("vat.VatClasses")

    """
    verbose_name = _("VAT Regime")
    item_class = VatRegime
    help_text = _(
        "Determines how the VAT is being handled, \
        i.e. whether and how it is to be paid.")

add = VatRegimes.add_item
add('10', _("Private person"), 'private')
add('20', _("Subject to VAT"), 'subject')
add('25', _("Co-contractor"), 'cocontractor')
add('30', _("Intra-community"), 'intracom')
add('40', _("Outside EU"), 'outside')
add('50', _("Exempt"), 'exempt', item_vat=False)


class TradeType(dd.Choice):
    """
    Base class for the choices of :class:`TradeTypes`.
    
    """
    price_field_name = None
    price_field_label = None
    partner_account_field_name = None
    partner_account_field_label = None
    base_account_field_name = None
    base_account_field_label = None
    vat_account_field_name = None
    vat_account_field_label = None
    dc = accounts.DEBIT

    def get_base_account(self):
        """Return the :class:`ml.accounts.Account` into which the **base
        amount** of any operation should be booked.

        """
        if self.base_account_field_name is None:
            return None
            # raise Exception("%s has no base_account_field_name!" % self)
        return getattr(settings.SITE.site_config,
                       self.base_account_field_name)

    def get_vat_account(self):
        """Return the :class:`ml.accounts.Account` into which the **VAT
        amount** of any operation should be booked.

        """
        if self.vat_account_field_name is None:
            return None
            # raise Exception("%s has no vat_account_field_name!" % self)
        return getattr(settings.SITE.site_config, self.vat_account_field_name)

    def get_partner_account(self):
        """Return the :class:`ml.accounts.Account` into which the **total
      amount** of any operation (base + VAT) should be booked.

        """
        if self.partner_account_field_name is None:
            return None
        return getattr(
            settings.SITE.site_config, self.partner_account_field_name)

    def get_product_base_account(self, product):
        """Return the :class:`ml.accounts.Account` into which the **base
        amount** of any operation should be booked.

        """
        if self.base_account_field_name is None:
            raise Exception("%s has no base_account_field_name" % self)
        return getattr(product, self.base_account_field_name) or \
            getattr(settings.SITE.site_config, self.base_account_field_name)

    def get_catalog_price(self, product):
        """Return the catalog price of the given product for operations with
this trade type.

        """
        return getattr(product, self.price_field_name)


class TradeTypes(dd.ChoiceList):
    """The **trade type** is one of the basic properties of every
operation.

    Typical content is as follows (but applications may redefine or
    extend this list in :meth:`lino.core.site.Site.setup_choicelists`):

       .. django2rst:: rt.show("vat.TradeTypes")

    """


    verbose_name = _("Trade Type")
    item_class = TradeType
    help_text = _("The type of trade: usually either `sales` or `purchases`.")

TradeTypes.add_item('S', _("Sales"), 'sales', dc=accounts.CREDIT)
TradeTypes.add_item('P', _("Purchases"), 'purchases', dc=accounts.DEBIT)
TradeTypes.add_item('W', _("Wages"), 'wages', dc=accounts.DEBIT)
TradeTypes.add_item('C', _("Clearings"), 'clearings', dc=accounts.DEBIT)

# Note that :mod:`lino.modlib.sales.models` and/or
# :mod:`lino.modlib.ledger.models` (if installed) will modify
# `TradeTypes.sales` at module level so that the following
# `inject_vat_fields` will inject the required fields to
# system.SiteConfig and products.Product (if these are installed).


@dd.receiver(dd.pre_analyze)
def inject_vat_fields(sender, **kw):
    for tt in TradeTypes.items():
        if tt.partner_account_field_name is not None:
            dd.inject_field(
                'system.SiteConfig',
                tt.partner_account_field_name,
                dd.ForeignKey(
                    'accounts.Account',
                    verbose_name=tt.partner_account_field_label,
                    related_name='configs_by_' + tt.partner_account_field_name,
                    blank=True, null=True))
        if tt.vat_account_field_name is not None:
            dd.inject_field('system.SiteConfig', tt.vat_account_field_name,
                            dd.ForeignKey(
                                'accounts.Account',
                                verbose_name=tt.vat_account_field_label,
                                related_name='configs_by_' +
                                tt.vat_account_field_name,
                                blank=True, null=True))
        if tt.base_account_field_name is not None:
            dd.inject_field('system.SiteConfig', tt.base_account_field_name,
                            dd.ForeignKey(
                                'accounts.Account',
                                verbose_name=tt.base_account_field_label,
                                related_name='configs_by_' +
                                tt.base_account_field_name,
                                blank=True, null=True))
            dd.inject_field('products.Product', tt.base_account_field_name,
                            dd.ForeignKey(
                                'accounts.Account',
                                verbose_name=tt.base_account_field_label,
                                related_name='products_by_' +
                                tt.base_account_field_name,
                                blank=True, null=True))
        if tt.price_field_name is not None:
            dd.inject_field('products.Product', tt.price_field_name,
                            dd.PriceField(verbose_name=tt.price_field_label,
                                          blank=True, null=True))


class VatRule(Sequenced, DatePeriod):
    """Example data see :mod:`lino.modlib.vat.fixtures.euvatrates`

    .. attribute:: country
    .. attribute:: vat_class
    .. attribute:: vat_regime
    .. attribute:: rate
    
    The VAT rate to be applied. Note that a VAT rate of 20 percent is
    stored as `0.20` (not `20`).

    .. attribute:: can_edit

    Whether the VAT amount can be modified by the user. This applies
    only for documents with :attr:`VatTotal.auto_compute_totals` set
    to `False`.

    """
    class Meta:
        verbose_name = _("VAT rule")
        verbose_name_plural = _("VAT rules")

    country = dd.ForeignKey('countries.Country', blank=True, null=True)
    # trade_type = TradeTypes.field(blank=True)
    vat_class = VatClasses.field(blank=True)
    vat_regime = VatRegimes.field(blank=True)
    rate = models.DecimalField(default=ZERO, decimal_places=4, max_digits=7)
    can_edit = models.BooleanField(_("Editable amount"), default=True)

    @classmethod
    def get_vat_rule(cls, vat_regime, vat_class, country, date):
        """Return the one and only VatRule object to be applied for the given
criteria.

        """
        qs = cls.objects.order_by('seqno')
        qs = qs.filter(Q(country__isnull=True) | Q(country=country))
        if vat_class is not None:
            qs = qs.filter(Q(vat_class='') | Q(vat_class=vat_class))
        if vat_regime is not None:
            qs = qs.filter(
                Q(vat_regime='') | Q(vat_regime=vat_regime))
        qs = PeriodEvents.active.add_filter(qs, date)
        if qs.count() == 1:
            return qs[0]
        rt.show(VatRules)
        msg = _("Found {num} VAT rules for %{context}!)").format(
            num=qs.count(), context=dict(
                vat_regime=vat_regime, vat_class=vat_class,
                country=country.isocode, date=dd.fds(date)))
        # msg += " (SQL query was {0})".format(qs.query)
        logger.info(msg)
        # raise Warning(msg)
        return None

    def __unicode__(self):
        kw = dict(
            vat_regime=self.vat_regime,
            vat_class=self.vat_class,
            rate=self.rate,
            country=self.country, seqno=self.seqno)
        return "{country} {vat_class} {rate}".format(**kw)


class VatRules(dd.Table):
    model = 'vat.VatRule'
    column_names = "seqno country vat_class vat_regime \
    start_date end_date rate can_edit *"
    hide_sums = True
    auto_fit_column_widths = True


class PaymentTerm(BabelNamed):
    """A convention on how an invoice should be paid.

    """

    class Meta:
        verbose_name = _("Payment Term")
        verbose_name_plural = _("Payment Terms")

    days = models.IntegerField(default=0)
    months = models.IntegerField(default=0)
    end_of_month = models.BooleanField(default=False)

    def get_due_date(self, date1):
        assert isinstance(date1, datetime.date), \
            "%s is not a date" % date1
        #~ print type(date1),type(relativedelta(months=self.months,days=self.days))
        d = date1 + relativedelta(months=self.months, days=self.days)
        if self.end_of_month:
            d = datetime.date(d.year, d.month + 1, 1)
            d = relativedelta(d, days=-1)
        return d


class PaymentTerms(dd.Table):
    model = PaymentTerm
    order_by = ["id"]


class VatTotal(dd.Model):
    """
    Model mixin which defines the fields `total_incl`, `total_base`
    and `total_vat`.  Used for both the document header
    (:class:`VatDocument`) and for each item (:class:`VatItemBase`).

    .. attribute:: total_incl
    
    A :class:`dd.PriceField` which stores the total amount VAT
    *included*.

    .. attribute:: total_base

    A :class:`dd.PriceField` which stores the total amount VAT
    *excluded*.

    .. attribute:: total_vat

    A :class:`dd.PriceField` which stores the amount of VAT.


    """
    class Meta:
        abstract = True

    #~ price = dd.PriceField(_("Total"),blank=True,null=True)
    total_incl = dd.PriceField(_("Total incl. VAT"), blank=True, null=True)
    total_base = dd.PriceField(_("Total excl. VAT"), blank=True, null=True)
    total_vat = dd.PriceField(_("VAT"), blank=True, null=True)

    _total_fields = set('total_vat total_base total_incl'.split())
    # For internal use.  This is the list of field names to disable
    # when `auto_compute_totals` is True.

    auto_compute_totals = False
    """Set this to `True` on subclasses who compute their totals
    automatically, i.e. the fields :attr:`total_base`,
    :attr:`total_vat` and :attr:`total_incl` are disabled.  This is
    set to `True` for :class:`lino.modlib.sales.models.SalesDocument`.

    """

    def disabled_fields(self, ar):
        """Disable all three total fields if `auto_compute_totals` is set,
        otherwise disable :attr:`total_vat` if
        :attr:`VatRule.can_edit` is False.

        """
        fields = super(VatTotal, self).disabled_fields(ar)
        if self.auto_compute_totals:
            fields |= self._total_fields
        else:
            rule = self.get_vat_rule()
            if rule is not None and not rule.can_edit:
                fields.add('total_vat')
        return fields

    def reset_totals(self, ar):
        pass

    def get_vat_rule(self):
        """Called when user edits a total field in the document header when
        `auto_compute_totals` is False.

        """
        return None

    def total_base_changed(self, ar):
        """Called when user has edited the `total_base` field.  If total_base
        has been set to blank, then Lino fills it using
        :meth:`reset_totals`. If user has entered a value, compute
        :attr:`total_vat` and :attr:`total_incl` from this value using
        the vat rate. If there is no VatRule, `total_incl` and
        `total_vat` are set to None.

        If there are rounding differences, `total_vat` will get them.

        """
        logger.info("20150128 total_base_changed %r", self.total_base)
        if self.total_base is None:
            self.reset_totals(ar)
            if self.total_base is None:
                return

        rule = self.get_vat_rule()
        logger.info("20150128 %r", rule)
        if rule is None:
            self.total_incl = None
            self.total_vat = None
        else:
            self.total_incl = self.total_base * (ONE + rule.rate)
            self.total_vat = self.total_incl - self.total_base

    def total_vat_changed(self, ar):
        """Called when user has edited the `total_vat` field.  If it has been
        set to blank, then Lino fills it using
        :meth:`reset_totals`. If user has entered a value, compute
        :attr:`total_incl`. If there is no VatRule, `total_incl` is
        set to None.

        """
        if self.total_vat is None:
            self.reset_totals(ar)
            if self.total_vat is None:
                return

        if self.total_base is None:
            self.total_base = ZERO
        self.total_incl = self.total_vat + self.total_base

    def total_incl_changed(self, ar):
        """Called when user has edited the `total_incl` field.  If total_incl
        has been set to blank, then Lino fills it using
        :meth:`reset_totals`. If user enters a value, compute
        :attr:`total_base` and :attr:`total_vat` from this value using
        the vat rate. If there is no VatRule, `total_incl` should be
        disabled, so this method will never be called.

        If there are rounding differences, `total_vat` will get them.

        """
        if self.total_incl is None:
            self.reset_totals(ar)
            if self.total_incl is None:
                return
        #~ assert not isinstance(self.total_incl,basestring)
        rule = self.get_vat_rule()
        if rule is None:
            self.total_base = None
            self.total_vat = None
        else:
            self.total_base = self.total_incl / (ONE + rule.rate)
            self.total_vat = self.total_incl - self.total_base


class VatDocument(VatTotal):
    """
    Abstract base class for invoices, offers and other vouchers.

    .. attribute:: refresh_after_item_edit = False

    See :srcref:`docs/tickets/68`

    .. attribute:: partner

    The recipient of this document. A pointer to
    :class:`ml.contacts.Partner`.

    .. attribute:: vat_regime

    The VAT regime to be used in this document.  A pointer to
    :class:`VatRegimes`.

    .. attribute:: payment_term

    The payment terms to be used in this document.  A pointer to
    :class:`PaymentTerm`.

    """

    auto_compute_totals = True

    refresh_after_item_edit = False

    class Meta:
        abstract = True

    partner = dd.ForeignKey('contacts.Partner')
    vat_regime = VatRegimes.field()
    payment_term = dd.ForeignKey(PaymentTerm, blank=True, null=True)

    @classmethod
    def get_registrable_fields(cls, site):
        for f in super(VatDocument, cls).get_registrable_fields(site):
            yield f
        yield 'partner'
        yield 'vat_regime'
        yield 'payment_term'

    if False:
        # this didn't work as expected because __init__() is called
        # also when an existing instance is being retrieved from database
        def __init__(self, *args, **kw):
            super(VatDocument, self).__init__(*args, **kw)
            self.item_vat = settings.SITE.get_item_vat(self)

    def get_recipient(self):
        return self.partner
    recipient = property(get_recipient)

    def compute_totals(self):
        if self.pk is None:
            return
        base = Decimal()
        vat = Decimal()
        for i in self.items.all():
            if i.total_base is not None:
                base += i.total_base
                vat += i.total_vat
        self.total_base = base
        self.total_vat = vat
        self.total_incl = vat + base

    def get_vat_sums(self):
        sums_dict = dict()

        def book(account, amount):
            if account in sums_dict:
                sums_dict[account] += amount
            else:
                sums_dict[account] = amount
        #~ if self.journal.type == JournalTypes.purchases:
        tt = self.get_trade_type()
        vat_account = tt.get_vat_account()
        if vat_account is None:
            raise Exception("No vat account for %s." % tt)
        for i in self.items.order_by('seqno'):
            if i.total_base:
                b = i.get_base_account(tt)
                if b is None:
                    raise Exception(
                        "No base account for %s (total_base is %r)" % (
                            i, i.total_base))
                book(b, i.total_base)
            if i.total_vat:
                book(vat_account, i.total_vat)
        return sums_dict

    def get_wanted_movements(self):
        sums_dict = self.get_vat_sums()
        #~ logger.info("20120901 get_wanted_movements %s",sums_dict)
        sum = Decimal()
        for a, m in sums_dict.items():
            if m:
                yield self.create_movement(a, not self.journal.dc, m)
                sum += m
        if self.match:
            match = self.match
        else:
            match = "%s#%s" % (self.journal.ref, self.pk)

        a = self.get_trade_type().get_partner_account()
        if a is not None:
            yield self.create_movement(
                a, self.journal.dc, sum, partner=self.partner, match=match)

    def fill_defaults(self):
        if not self.payment_term:
            self.payment_term = self.partner.payment_term
        if not self.vat_regime:
            self.vat_regime = self.partner.vat_regime
        if not self.vat_regime:
            self.vat_regime = get_default_vat_regime()

    def full_clean(self, *args, **kw):
        self.fill_defaults()
        self.compute_totals()
        super(VatDocument, self).full_clean(*args, **kw)

    def before_state_change(self, ar, old, new):
        if new.name == 'registered':
            self.compute_totals()
        elif new.name == 'draft':
            pass
        super(VatDocument, self).before_state_change(ar, old, new)


class VatItemBase(Sequenced, VatTotal):
    """Model mixin for items of a :class:`VatTotal`.

    Abstract Base class for
    :class:`lino.modlib.ledger.models.InvoiceItem`, i.e. the lines of
    invoices *without* unit prices and quantities.

    Subclasses must define a field called "voucher" which must be a
    ForeignKey with related_name="items" to the "owning document",
    which in turn must be a subclass of :class:`VatDocument`).

    .. attribute:: vat_class

    The VAT class to be applied for this item. A pointer to
    :class:`VatClasses`.

    """

    class Meta:
        abstract = True

    vat_class = VatClasses.field(blank=True, default=get_default_vat_class)

    def get_vat_class(self, tt):
        return dd.plugins.vat.get_vat_class(tt, self)

    def vat_class_changed(self, ar):
        #~ logger.info("20121204 vat_class_changed")
        if self.voucher.vat_regime.item_vat:
            self.total_incl_changed(ar)
        else:
            self.total_base_changed(ar)

    def get_base_account(self, tt):
        raise NotImplementedError

    #~ def unit_price_includes_vat(self):
        #~ return True

    def get_siblings(self):
        return self.voucher.items.all()

    def get_vat_rule(self):
        if self.vat_class is None:
            tt = self.voucher.get_trade_type()
            self.vat_class = self.get_vat_class(tt)
        rule = VatRule.get_vat_rule(
            self.voucher.vat_regime, self.vat_class,
            self.voucher.partner.country or
            dd.plugins.countries.get_my_country(),
            self.voucher.date)
        return rule

    #~ def save(self,*args,**kw):
        #~ super(VatItemBase,self).save(*args,**kw)
        #~ self.voucher.full_clean()
        #~ self.voucher.save()

    def set_amount(self, ar, amount):
        self.voucher.fill_defaults()
        rule = self.get_vat_rule()
        if rule is None:
            rate = ZERO
        else:
            rate = rule.rate
        if self.voucher.vat_regime.item_vat:  # unit_price_includes_vat
            self.total_incl = amount
            self.total_incl_changed(ar)
        else:
            self.total_base = amount
            self.total_base_changed(ar)

    def reset_totals(self, ar):
        """
        """
        if not self.voucher.auto_compute_totals:
            total = Decimal()
            for item in self.voucher.items.exclude(id=self.id):
                total += item.total_incl
            #~ if total != self.voucher.total_incl:
            self.total_incl = self.voucher.total_incl - total
            self.total_incl_changed(ar)

        super(VatItemBase, self).reset_totals(ar)

    def before_ui_save(self, ar):
        if self.total_incl is None:
            self.reset_totals(ar)
        super(VatItemBase, self).before_ui_save(ar)

    def after_ui_save(self, ar):
        """
        After editing a grid cell automatically show new invoice totals.
        See :srcref:`docs/tickets/68`
        """
        kw = super(VatItemBase, self).after_ui_save(ar)
        if self.voucher.refresh_after_item_edit:
            ar.set_response(refresh_all=True)
            self.voucher.compute_totals()
            self.voucher.full_clean()
            self.voucher.save()
        return kw


class QtyVatItemBase(VatItemBase):
    """Model mixin for items of a :class:`VatTotal`, adds `unit_price` and
`qty`.

    Abstract Base class for :class:`lino.modlib.sales.InvoiceItem` and
    :class:`lino.modlib.sales.OrderItem`, i.e. the lines of invoices
    *with* unit prices and quantities.

    """

    class Meta:
        abstract = True

    unit_price = dd.PriceField(_("Unit price"), blank=True, null=True)
    qty = dd.QuantityField(_("Quantity"), blank=True, null=True)

    def unit_price_changed(self, ar):
        self.reset_totals(ar)

    def qty_changed(self, ar):
        self.reset_totals(ar)

    def reset_totals(self, ar):
        super(QtyVatItemBase, self).reset_totals(ar)
        #~ if not self.voucher.auto_compute_totals:
            #~ if self.qty:
                #~ if self.voucher.item_vat:
                    #~ self.unit_price = self.total_incl / self.qty
                #~ else:
                    #~ self.unit_price = self.total_base / self.qty

        if self.unit_price is not None and self.qty is not None:
            self.set_amount(ar, self.unit_price * self.qty)


if False:
    """Install a post_init signal listener for each concrete subclass of
    VatDocument.  The following trick worked...  but best is to store
    it in VatRegime, not per voucher.

    """

    def set_default_item_vat(sender, instance=None, **kwargs):
        instance.item_vat = settings.SITE.get_item_vat(instance)
        #~ print("20130902 set_default_item_vat", instance)

    @dd.receiver(dd.post_analyze)
    def on_post_analyze(sender, **kw):
        for m in rt.models_by_base(VatDocument):
            dd.post_init.connect(set_default_item_vat, sender=m)
            #~ print('20130902 on_post_analyze installed receiver for',m)


dd.inject_field(
    'contacts.Partner',
    'vat_regime',
    VatRegimes.field(
        blank=True,
        help_text=_("The default VAT regime for \
        sales and purchases of this partner.")))

dd.inject_field(
    'contacts.Company',
    'vat_id',
    models.CharField(_("VAT id"), max_length=200, blank=True))

dd.inject_field(
    'contacts.Partner',
    'payment_term',
    models.ForeignKey(
        PaymentTerm,
        blank=True, null=True,
        help_text=_("The default payment term for "
                    "sales invoices to this customer.")))
