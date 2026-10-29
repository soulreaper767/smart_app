# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
One-shot (but safe to re-run) switch of the site's default currency,
applied everywhere this app touches currency -- including already-created
and already-**submitted** documents.

    bench --site <site> execute smart_app.currency_migration.switch_default_currency

Runs once automatically via smart_app/patches/switch_currency_to_usd.py on
the first `bench migrate` after this app is pulled.

This is a **relabel, not a conversion**: every rate/amount number is left
exactly as typed -- only the currency tag changes. `conversion_rate` /
`plc_conversion_rate` / `base_*` fields are deliberately left untouched,
since recomputing them without a real exchange rate would be a guess, not a
fix (the task this was built for explicitly chose "relabel only, numbers
stay the same" over converting the numbers).

Company.default_currency and the two transaction doctypes below are updated
via direct SQL/`frappe.db.set_value`, not `doc.save()`:
  - Company.validate() refuses to change default_currency once the company
    has any GL Entry -- this was explicitly asked for despite that.
  - Frappe blocks editing a field on an already-submitted document through
    the normal save path by design; a raw update is the only way to
    relabel a submitted Quotation/Supplier Quotation at all, and is a
    deliberate one-off correction, not a live edit through the UI.

Scope, deliberately: Company, Global Defaults, every Price List, every Item
Price, and the two BuyingController/SellingController doctypes this app's
own pipeline creates records in -- **Quotation** and **Supplier Quotation**
(Request for Quotation has no `currency` field of its own -- it's a
request, sent before any party has quoted a price). Purchase Order / Sales
Invoice / Purchase Invoice / Payment Entry are NOT touched: this app never
creates or owns those records (Purchase Order is granted select+read only,
for reference -- see grant_commercial_access in install.py), and relabeling
a *posted* accounting document's currency without also reworking its GL
Entries is a books-integrity risk outside what was asked for here.
"""

import frappe

DEFAULT_TARGET_CURRENCY = "USD"

# Doctypes with their own header-level `currency` (and, where present,
# `price_list_currency`) field that this app's pipeline creates records in.
TRANSACTION_DOCTYPES = ["Quotation", "Supplier Quotation"]


def _ensure_currency_enabled(currency):
	if not frappe.db.exists("Currency", currency):
		frappe.get_doc({"doctype": "Currency", "currency_name": currency, "enabled": 1}).insert(
			ignore_permissions=True
		)
	elif not frappe.db.get_value("Currency", currency, "enabled"):
		frappe.db.set_value("Currency", currency, "enabled", 1)


def switch_default_currency(target_currency=DEFAULT_TARGET_CURRENCY):
	_ensure_currency_enabled(target_currency)

	changed = {}

	if frappe.db.get_single_value("Global Defaults", "default_currency") != target_currency:
		frappe.db.set_single_value("Global Defaults", "default_currency", target_currency)

	changed["companies"] = 0
	for company in frappe.get_all("Company", fields=["name", "default_currency"]):
		if company.default_currency != target_currency:
			frappe.db.set_value(
				"Company", company.name, "default_currency", target_currency, update_modified=False
			)
			changed["companies"] += 1

	# Every Price List -- the ones this app auto-creates per Customer/
	# Supplier (see ensure_default_price_list in utils.py), the two core
	# Standard Buying/Selling lists, and any other Price List the site has.
	# Raw SQL (not frappe.get_all's `!=` filter) so a NULL currency is
	# caught too -- `!= target_currency` alone is never true against NULL.
	price_lists = frappe.db.sql(
		"select name from `tabPrice List` where currency is null or currency != %s", target_currency
	)
	for (price_list,) in price_lists:
		frappe.db.set_value("Price List", price_list, "currency", target_currency, update_modified=False)
	changed["price_lists"] = len(price_lists)

	changed["item_prices"] = frappe.db.sql(
		"select count(*) from `tabItem Price` where currency is null or currency != %s", target_currency
	)[0][0]
	frappe.db.sql(
		"update `tabItem Price` set currency = %s where currency is null or currency != %s",
		(target_currency, target_currency),
	)

	# Quotation / Supplier Quotation, at every docstatus (draft, submitted,
	# cancelled) -- see module docstring for why this bypasses doc.save().
	for doctype in TRANSACTION_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		set_clauses = []
		if meta.has_field("currency"):
			set_clauses.append("currency = %(cur)s")
		if meta.has_field("price_list_currency"):
			set_clauses.append("price_list_currency = %(cur)s")
		if not set_clauses:
			continue

		table = f"`tab{doctype}`"
		changed[doctype] = frappe.db.sql(
			f"select count(*) from {table} where currency is null or currency != %(cur)s",
			{"cur": target_currency},
		)[0][0]
		frappe.db.sql(
			f"update {table} set {', '.join(set_clauses)} where currency is null or currency != %(cur)s",
			{"cur": target_currency},
		)

	frappe.db.commit()
	frappe.clear_cache()

	print(f"[smart_app] default currency switched to {target_currency}: {changed}")
	return changed


# ---------------------------------------------------------------------------
# 2026-10-30 correction: Quotation, Purchase Order, and Indent now always
# transact in US$ going forward (force_trade_currency_quotation /
# force_trade_currency_purchase_order in utils.py, Indent.force_trade_
# currency in indent.py) -- but those only ever apply the moment a record
# is next saved. backfill_trade_currency below is the one-time companion
# that relabels every EXISTING record of those three doctypes, the same
# way switch_default_currency above already relabels existing Quotation/
# Supplier Quotation.
# ---------------------------------------------------------------------------


def backfill_trade_currency(target_currency=DEFAULT_TARGET_CURRENCY):
	"""Relabels every existing Quotation / Purchase Order / Indent record to
	`target_currency` (USD by default) -- same relabel-not-conversion
	approach as switch_default_currency above: every rate/amount number is
	left exactly as typed, only the currency tag changes (`conversion_rate`
	/ `plc_conversion_rate` / `base_*` deliberately untouched, for the same
	reason -- recomputing them without a real exchange rate would be a
	guess, not a fix).

		bench --site <your-site> execute smart_app.currency_migration.backfill_trade_currency
		# a different target currency:
		bench --site <your-site> execute smart_app.currency_migration.backfill_trade_currency --kwargs "{'target_currency': 'EUR'}"

	Unlike switch_default_currency, this DOES now touch Purchase Order --
	this app creates and owns Purchase Orders (create_purchase_orders_from_
	quotation, supplier_comparative_statement.py), unlike when that
	function's own scope note was written. Still deliberately leaves Sales
	Order, Sales Invoice, Purchase Invoice, Payment Entry, and GL Entry
	alone, for the identical books-integrity reasoning switch_default_
	currency's own docstring already gives for those. Commission Invoice is
	ALSO deliberately left alone here, on top of that -- see
	_build_commission_invoice_from_indent (commission_invoice.py): its
	billing Customer is a separate, auto-created stand-in for the Supplier
	that stays on whatever currency its own resolved account uses, not the
	Indent's, so there's nothing to relabel there consistent with the
	going-forward fix.

	Also provisions the USD Party Account override (ensure_usd_party_
	account, utils.py) for every distinct Customer/Supplier found on an
	affected Quotation/Purchase Order, *before* the raw SQL relabel below --
	without this, simply re-opening and re-saving one of these relabeled
	records later would hit the exact InvalidCurrency error this whole fix
	was for, the moment its own before_validate hook runs. A party that
	already has GL history in a different currency can't get this override
	(ERPNext's own accounting-integrity limit -- see ensure_usd_party_
	account's own docstring) and is silently left alone here too, exactly
	as it would be going forward -- its Quotation/Purchase Order still gets
	relabeled (this is a relabel-only script, not a validation pass), but
	that one party's records would need a real currency decision from a
	human, not something this script can safely resolve on its own.

	Idempotent -- every query only ever touches rows that aren't already
	`target_currency`, so re-running (including with a different target
	currency later) is always safe."""
	from smart_app.smart_app.utils import ensure_usd_party_account

	_ensure_currency_enabled(target_currency)
	changed = {}

	if frappe.db.exists("DocType", "Quotation"):
		customers = frappe.db.sql(
			"""
			select distinct company, party_name
			from `tabQuotation`
			where quotation_to = 'Customer' and party_name is not null
				and (currency is null or currency != %s)
			""",
			target_currency,
		)
		for company, customer in customers:
			if company and customer:
				ensure_usd_party_account("Customer", customer, company)

	if frappe.db.exists("DocType", "Purchase Order"):
		suppliers = frappe.db.sql(
			"""
			select distinct company, supplier
			from `tabPurchase Order`
			where supplier is not null and (currency is null or currency != %s)
			""",
			target_currency,
		)
		for company, supplier in suppliers:
			if company and supplier:
				ensure_usd_party_account("Supplier", supplier, company)

	# Quotation / Purchase Order, at every docstatus (draft, submitted,
	# cancelled) -- raw SQL for the same reason switch_default_currency
	# uses it above: Frappe blocks editing a field on an already-submitted
	# document through the normal save path.
	for doctype in ("Quotation", "Purchase Order"):
		if not frappe.db.exists("DocType", doctype):
			continue
		meta = frappe.get_meta(doctype)
		set_clauses = []
		if meta.has_field("currency"):
			set_clauses.append("currency = %(cur)s")
		if meta.has_field("price_list_currency"):
			set_clauses.append("price_list_currency = %(cur)s")
		if not set_clauses:
			continue

		table = f"`tab{doctype}`"
		changed[doctype] = frappe.db.sql(
			f"select count(*) from {table} where currency is null or currency != %(cur)s",
			{"cur": target_currency},
		)[0][0]
		frappe.db.sql(
			f"update {table} set {', '.join(set_clauses)} where currency is null or currency != %(cur)s",
			{"cur": target_currency},
		)

	# Indent -- smart_app's own doctype, no GL/party-currency check at all
	# (see Indent.force_trade_currency, indent.py), so a plain relabel with
	# no Party Account provisioning needed.
	if frappe.db.exists("DocType", "Indent"):
		changed["Indent"] = frappe.db.sql(
			"select count(*) from `tabIndent` where currency is null or currency != %(cur)s",
			{"cur": target_currency},
		)[0][0]
		frappe.db.sql(
			"update `tabIndent` set currency = %(cur)s where currency is null or currency != %(cur)s",
			{"cur": target_currency},
		)

	frappe.db.commit()
	frappe.clear_cache()

	print(f"[smart_app] trade currency backfilled to {target_currency}: {changed}")
	return changed
