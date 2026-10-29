# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

COMMERCIAL_ROLES = {"Commercial Manager", "Commercial Officer", "System Manager"}


class SupplierComparativeStatement(Document):
	def validate(self):
		self.calculate_amounts()
		self.enforce_single_selection_per_item()

	def calculate_amounts(self):
		for row in self.get("items") or []:
			row.amount = flt(row.qty) * flt(row.rate)

	def enforce_single_selection_per_item(self):
		"""At most one winning row per Item -- checking a second one
		silently unchecks the earlier one, same pattern as Item's own
		Preferred Supplier flag (enforce_single_preferred_supplier,
		utils.py)."""
		seen = set()
		for row in self.get("items") or []:
			if row.is_selected:
				if row.item_code in seen:
					row.is_selected = 0
				else:
					seen.add(row.item_code)

	def before_submit(self):
		""""Submitted and locked" only once every item actually has a
		winner -- this is the gate Quotation's own "Create > Purchase
		Order"/"Create > Indent" buttons check for (see
		_require_comparative_statement below)."""
		item_codes = {row.item_code for row in self.get("items") or []}
		selected_codes = {row.item_code for row in self.get("items") or [] if row.is_selected}
		missing = item_codes - selected_codes
		if missing:
			frappe.throw(
				_(
					"Please select a winning Supplier for every item before submitting. Missing: {0}"
				).format(", ".join(sorted(missing)))
			)

	def on_submit(self):
		# db_set, not a plain assignment -- confirmed live that a plain
		# `self.field = value` inside on_submit/on_cancel is silently lost
		# (Frappe's own _save() runs db_update() before dispatching
		# on_submit/on_cancel, so the row is already written by the time
		# this hook runs). See the identical note on Indent.on_submit.
		self.db_set("comparative_status", "Completed")

	def on_cancel(self):
		self.db_set("comparative_status", "")


def _get_rfq_quotation_rates(rfq_name):
	"""Every (item, supplier, qty, rate) combination from a SUBMITTED
	Supplier Quotation raised against this RFQ. Supplier Quotation Item's
	own `request_for_quotation` field (core ERPNext) is what ties a
	specific quoted row back to the RFQ it answers -- set automatically by
	the RFQ portal reply flow, and by core Supplier Quotation's own native
	"Get Items From > Request for Quotation" button for a manually-logged
	reply (see the Commercial team roles section of the README for that
	manual-logging path)."""
	return frappe.db.sql(
		"""
		select sqi.item_code, sqi.qty, sqi.rate, sq.supplier
		from `tabSupplier Quotation Item` sqi
		inner join `tabSupplier Quotation` sq on sq.name = sqi.parent
		where sqi.request_for_quotation = %s and sq.docstatus = 1
		order by sqi.item_code, sq.supplier
		""",
		rfq_name,
		as_dict=True,
	)


def _build_comparative_statement_from_rfq(rfq):
	"""Shared by both create_comparative_statement_from_rfq (builds a new,
	separate statement -- the "Create" button on a submitted RFQ) and
	get_comparative_statement_data_from_rfq (returns the same data as a
	plain dict for a blank statement already open in the browser -- same
	shared-builder / two-whitelisted-methods split used throughout this
	app, for the same reason: erpnext.utils.map_current_doc isn't built
	for cloning one whole source document's data onto a blank one)."""
	doc = frappe.new_doc("Supplier Comparative Statement")
	doc.company = rfq.company
	# Always US$ now -- the Quotation this statement eventually produces
	# (create_quotation_from_comparative_statement below) is forced to US$
	# regardless (force_trade_currency_quotation, utils.py), and under the
	# corrected pipeline (2026-10-30) the RFQ is built from the Inquiry
	# directly, so `rfq.quotation` (the OLD reverse-link, from when RFQ was
	# built from a Quotation) is never set to derive a currency from here.
	doc.currency = "USD"
	doc.request_for_quotation = rfq.name
	doc.inquiry = rfq.get("inquiry")

	rate_rows = _get_rfq_quotation_rates(rfq.name)
	quoted_suppliers = {row.supplier for row in rate_rows}

	for supplier_row in rfq.get("suppliers") or []:
		doc.append(
			"rfq_suppliers",
			{
				"supplier": supplier_row.supplier,
				"supplier_name": frappe.db.get_value("Supplier", supplier_row.supplier, "supplier_name"),
				"contact": supplier_row.contact,
				"email_id": supplier_row.email_id,
				"quoted": 1 if supplier_row.supplier in quoted_suppliers else 0,
			},
		)

	for row in rate_rows:
		doc.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": row.qty,
				"supplier": row.supplier,
				"rate": row.rate,
				"amount": flt(row.qty) * flt(row.rate),
			},
		)

	return doc


@frappe.whitelist()
def create_comparative_statement_from_rfq(rfq_name):
	"""Builds a brand new, separate draft Supplier Comparative Statement
	from a submitted Request for Quotation -- the "Create > Supplier
	Comparative Statement" button (RFQ_CLIENT_SCRIPT_JS, install.py). Can
	be created (and refreshed, see refresh_rates below) at any point after
	the RFQ is sent -- it doesn't need every supplier to have replied yet."""
	if not frappe.has_permission("Supplier Comparative Statement", "create"):
		frappe.throw(
			_("You do not have permission to create a Supplier Comparative Statement."),
			frappe.PermissionError,
		)

	rfq = frappe.get_doc("Request for Quotation", rfq_name)
	rfq.check_permission("read")
	if rfq.docstatus != 1:
		frappe.throw(_("Only a submitted Request for Quotation can have a Comparative Statement."))

	doc = _build_comparative_statement_from_rfq(rfq)
	doc.insert(ignore_permissions=True, ignore_mandatory=True)
	return doc.name


@frappe.whitelist()
def get_comparative_statement_data_from_rfq(rfq_name):
	"""Used by the "Get Items From > Request for Quotation" button on a
	blank Supplier Comparative Statement (supplier_comparative_statement.js)."""
	rfq = frappe.get_doc("Request for Quotation", rfq_name)
	rfq.check_permission("read")
	if rfq.docstatus != 1:
		frappe.throw(_("Only a submitted Request for Quotation can have a Comparative Statement."))

	doc = _build_comparative_statement_from_rfq(rfq)
	return {
		"company": doc.company,
		"currency": doc.currency,
		"request_for_quotation": doc.request_for_quotation,
		"quotation": doc.get("quotation"),
		"inquiry": doc.inquiry,
		"rfq_suppliers": [
			{
				"supplier": d.supplier,
				"supplier_name": d.supplier_name,
				"contact": d.contact,
				"email_id": d.email_id,
				"quoted": d.quoted,
			}
			for d in doc.rfq_suppliers
		],
		"items": [
			{
				"item_code": d.item_code,
				"qty": d.qty,
				"supplier": d.supplier,
				"rate": d.rate,
				"amount": d.amount,
			}
			for d in doc.items
		],
	}


@frappe.whitelist()
def refresh_rates(comparative_statement_name):
	"""Re-pulls (item, supplier, rate) rows from any Supplier Quotation
	submitted against this statement's RFQ since it was first built, adding
	only genuinely new combinations and never touching an existing row's
	own selection -- lets a Commercial Officer start comparing early and
	keep refreshing as more supplier replies come in, without losing work
	already done."""
	doc = frappe.get_doc("Supplier Comparative Statement", comparative_statement_name)
	doc.check_permission("write")
	if doc.docstatus != 0:
		frappe.throw(_("Only a draft Supplier Comparative Statement can be refreshed."))

	existing = {(row.item_code, row.supplier) for row in doc.items}
	rate_rows = _get_rfq_quotation_rates(doc.request_for_quotation)
	quoted_suppliers = {row.supplier for row in rate_rows}
	added = 0

	for row in rate_rows:
		if (row.item_code, row.supplier) in existing:
			continue
		doc.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": row.qty,
				"supplier": row.supplier,
				"rate": row.rate,
				"amount": flt(row.qty) * flt(row.rate),
			},
		)
		added += 1

	for supplier_row in doc.rfq_suppliers:
		if supplier_row.supplier in quoted_suppliers:
			supplier_row.quoted = 1

	doc.save(ignore_permissions=True)
	return added


@frappe.whitelist()
def get_rfqs_for_comparative_statement(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for "Get Items From > Request for Quotation" --
	submitted RFQs only, scoped the same way this app's other pickers are
	(own, unless Commercial Manager/System Manager)."""
	conditions = ["docstatus = 1", "name like %(txt)s"]
	values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

	roles = frappe.get_roles(frappe.session.user)
	if not ({"Commercial Manager", "System Manager"} & set(roles)):
		conditions.append("owner = %(user)s")
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		select name
		from `tabRequest for Quotation`
		where {" and ".join(conditions)}
		order by modified desc
		limit %(page_len)s offset %(start)s
		""",
		values,
	)


# ---------------------------------------------------------------------------
# The gate on Quotation: "Create > Purchase Order" and "Create > Indent"
# both require a submitted Supplier Comparative Statement, and both source
# their items/rates/supplier from the exact same place -- its winning
# selection, grouped by Supplier (usually just one; more than one only if
# different items went to different winning Suppliers, in which case one
# Purchase Order/Indent is created per Supplier automatically).
# ---------------------------------------------------------------------------


def get_submitted_comparative_statement_for_quotation(quotation_name):
	return frappe.db.get_value(
		"Supplier Comparative Statement", {"quotation": quotation_name, "docstatus": 1}, "name"
	)


def _require_comparative_statement(quotation_name):
	name = get_submitted_comparative_statement_for_quotation(quotation_name)
	if not name:
		frappe.throw(
			_(
				"Supplier Comparative Statement not submitted yet. Compare the supplier "
				"quotations for this Quotation's Request for Quotation and select a winning "
				"Supplier for every item first."
			)
		)
	return frappe.get_doc("Supplier Comparative Statement", name)


def _require_approved_quotation(quotation):
	"""Purchase Order/Indent creation now also requires the Quotation itself
	to be approved first -- the corrected pipeline's own order (Inquiry
	Manager correction, 2026-10-30): "the Quotation ... will be approved
	and shared to marketer", which this app reads as the real gate before
	anything is actually ordered against a winning Supplier, not merely a
	display label. See approve_quotation (inquiry.py)."""
	if quotation.get("quotation_approval_status") != "Approved":
		frappe.throw(
			_(
				"This Quotation has not been approved yet. A Commercial Manager must approve it "
				"before a Purchase Order or Indent can be created."
			)
		)


def _selected_rows_by_supplier(comparative_statement):
	grouped = {}
	for row in comparative_statement.get("items") or []:
		if row.is_selected:
			grouped.setdefault(row.supplier, []).append(row)
	return grouped


def build_indent_doc_for_supplier(quotation, supplier, rows):
	"""Shared by create_indents_from_quotation below and Indent's own
	get_indent_data_from_quotation (indent.py, the reverse "Get Items
	From" button on a blank Indent) -- one Indent's worth of data for one
	winning Supplier's selected rows. Item rate/qty come from the
	Comparative Statement's own selection, not the Quotation's original
	rate -- that's the actual agreed sourcing price once suppliers have
	replied, which supersedes whatever estimate the Quotation first quoted
	the Buyer. Buyer/address/terms still come from the Quotation itself."""
	from smart_app.smart_app.doctype.indent.indent import _best_effort_hs_code

	indent = frappe.new_doc("Indent")
	indent.company = quotation.company
	indent.currency = quotation.currency
	indent.quotation = quotation.name
	indent.inquiry = quotation.get("inquiry")
	indent.customer = quotation.party_name
	indent.customer_address_display = quotation.get("address_display")
	indent.tc_name = quotation.get("tc_name")
	indent.terms = quotation.get("terms")
	indent.supplier = supplier

	item_meta = {d.item_code: d for d in quotation.items}
	for row in rows:
		source_item = item_meta.get(row.item_code)
		indent.append(
			"items",
			{
				"item_code": row.item_code,
				"item_name": source_item.item_name if source_item else None,
				"description": source_item.description if source_item else None,
				"custom_pharmacopeia": source_item.get("custom_pharmacopeia") if source_item else None,
				"custom_item_grade": source_item.get("custom_item_grade") if source_item else None,
				"hs_code": _best_effort_hs_code(row.item_code),
				"qty": row.qty,
				"uom": source_item.uom if source_item else None,
				"rate": row.rate,
				"amount": flt(row.qty) * flt(row.rate),
			},
		)

	return indent


@frappe.whitelist()
def create_purchase_orders_from_quotation(quotation_name):
	"""The "Create > Purchase Order" button on a submitted Quotation
	(QUOTATION_CLIENT_SCRIPT_JS) -- one Purchase Order per distinct
	winning Supplier in the linked Supplier Comparative Statement's
	selection. Left as drafts for review before submitting."""
	if not (COMMERCIAL_ROLES & set(frappe.get_roles(frappe.session.user))):
		frappe.throw(_("You are not allowed to create a Purchase Order."), frappe.PermissionError)
	if not frappe.has_permission("Purchase Order", "create"):
		frappe.throw(_("You do not have permission to create a Purchase Order."), frappe.PermissionError)

	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("read")
	_require_approved_quotation(quotation)

	comparative_statement = _require_comparative_statement(quotation_name)
	grouped = _selected_rows_by_supplier(comparative_statement)
	if not grouped:
		frappe.throw(_("No Supplier selections found on {0}.").format(comparative_statement.name))

	created = []
	for supplier, rows in grouped.items():
		po = frappe.new_doc("Purchase Order")
		po.supplier = supplier
		po.company = comparative_statement.company
		po.currency = comparative_statement.currency
		schedule_date = frappe.utils.add_days(frappe.utils.today(), 7)
		for row in rows:
			po.append(
				"items",
				{"item_code": row.item_code, "qty": row.qty, "rate": row.rate, "schedule_date": schedule_date},
			)
		po.run_method("set_missing_values")
		po.insert(ignore_permissions=True, ignore_mandatory=True)
		created.append(po.name)

	return created


@frappe.whitelist()
def create_indents_from_quotation(quotation_name):
	"""The "Create > Indent" button on a submitted Quotation -- one Indent
	per distinct winning Supplier, same grouping
	create_purchase_orders_from_quotation uses (this is the "same links to
	get items from" the task this was built for asked for -- both read the
	exact same Comparative Statement selection)."""
	if not frappe.has_permission("Indent", "create"):
		frappe.throw(_("You do not have permission to create an Indent."), frappe.PermissionError)

	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("read")
	if quotation.quotation_to != "Customer":
		frappe.throw(_("Only a Quotation addressed to a Customer can be used to build an Indent."))
	_require_approved_quotation(quotation)

	comparative_statement = _require_comparative_statement(quotation_name)
	grouped = _selected_rows_by_supplier(comparative_statement)
	if not grouped:
		frappe.throw(_("No Supplier selections found on {0}.").format(comparative_statement.name))

	created = []
	for supplier, rows in grouped.items():
		indent = build_indent_doc_for_supplier(quotation, supplier, rows)
		indent.insert(ignore_permissions=True, ignore_mandatory=True)
		created.append(indent.name)

	return created


# ---------------------------------------------------------------------------
# Quotation is now built FROM a submitted Supplier Comparative Statement,
# never the other way round (Inquiry Manager correction, 2026-10-30):
# "Inquiry will be assigned 1st and then commercial officer will send the
# RFQ to the suppliers. After comparison of prices he will prepare the
# Quotation that will be approved and shared to marketer." Every selected
# (winning) row across every Supplier goes onto the one Quotation -- it
# addresses the Buyer, not any particular Supplier, and the rate quoted is
# the Comparative Statement's own winning rate directly, no markup (same
# no-markup sourcing Indent/Purchase Order already use -- see
# build_indent_doc_for_supplier above: this app's only real revenue is the
# commission on the Indent, never a margin baked into the trade itself).
# ---------------------------------------------------------------------------


def _build_quotation_from_comparative_statement(comparative_statement):
	if not comparative_statement.inquiry:
		frappe.throw(
			_("{0} has no linked Inquiry -- cannot determine the Buyer to quote.").format(
				comparative_statement.name
			)
		)

	selected_rows = [row for row in comparative_statement.get("items") or [] if row.is_selected]
	if not selected_rows:
		frappe.throw(_("No winning Supplier selected for any item on {0}.").format(comparative_statement.name))

	inquiry = frappe.get_doc("Inquiry", comparative_statement.inquiry)

	quotation = frappe.new_doc("Quotation")
	quotation.quotation_to = "Customer"
	quotation.party_name = inquiry.inquiry_source
	quotation.company = comparative_statement.company
	quotation.inquiry = inquiry.name
	quotation.comparative_statement = comparative_statement.name
	quotation.quotation_approval_status = "Pending Approval"

	for row in selected_rows:
		item = frappe.db.get_value(
			"Item", row.item_code, ["item_name", "description", "stock_uom"], as_dict=True
		)
		quotation.append(
			"items",
			{
				"item_code": row.item_code,
				"item_name": item.item_name if item else row.item_code,
				"description": item.description if item else None,
				"uom": item.stock_uom if item else row.uom,
				"qty": row.qty,
				"rate": row.rate,
				"amount": flt(row.qty) * flt(row.rate),
			},
		)

	quotation.run_method("set_missing_values")
	quotation.run_method("calculate_taxes_and_totals")
	return quotation


@frappe.whitelist()
def create_quotation_from_comparative_statement(comparative_statement_name):
	"""Builds a brand new, separate draft Quotation from a submitted
	Supplier Comparative Statement -- the "Create > Quotation" button
	(install.py's client script for Supplier Comparative Statement). Left
	as a draft: approve_quotation (inquiry.py) is the separate, explicit
	next step, same "prepare first, approve second" split as everywhere
	else in this app."""
	if not (COMMERCIAL_ROLES & set(frappe.get_roles(frappe.session.user))):
		frappe.throw(_("You are not allowed to create a Quotation."), frappe.PermissionError)
	if not frappe.has_permission("Quotation", "create"):
		frappe.throw(_("You do not have permission to create a Quotation."), frappe.PermissionError)

	comparative_statement = frappe.get_doc("Supplier Comparative Statement", comparative_statement_name)
	comparative_statement.check_permission("read")
	if comparative_statement.docstatus != 1:
		frappe.throw(_("Only a submitted Supplier Comparative Statement can be used to build a Quotation."))
	if comparative_statement.quotation:
		frappe.throw(
			_("A Quotation ({0}) already exists for this Comparative Statement.").format(
				comparative_statement.quotation
			)
		)

	quotation = _build_quotation_from_comparative_statement(comparative_statement)
	quotation.insert(ignore_permissions=True, ignore_mandatory=True)

	frappe.db.set_value("Supplier Comparative Statement", comparative_statement.name, "quotation", quotation.name)

	return quotation.name


@frappe.whitelist()
def get_quotation_data_from_comparative_statement(comparative_statement_name):
	"""Used by the "Get Items From > Supplier Comparative Statement" button
	on a blank Quotation (QUOTATION_CLIENT_SCRIPT_JS, install.py)."""
	comparative_statement = frappe.get_doc("Supplier Comparative Statement", comparative_statement_name)
	comparative_statement.check_permission("read")
	if comparative_statement.docstatus != 1:
		frappe.throw(_("Only a submitted Supplier Comparative Statement can be used to build a Quotation."))

	quotation = _build_quotation_from_comparative_statement(comparative_statement)
	return {
		"quotation_to": quotation.quotation_to,
		"party_name": quotation.party_name,
		"company": quotation.company,
		"inquiry": quotation.inquiry,
		"comparative_statement": quotation.comparative_statement,
		"items": [
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"description": d.description,
				"uom": d.uom,
				"qty": d.qty,
				"rate": d.rate,
				"amount": d.amount,
			}
			for d in quotation.items
		],
	}


@frappe.whitelist()
def get_comparative_statements_for_quotation(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for the "Get Items From > Supplier Comparative
	Statement" button on a blank Quotation -- submitted Comparative
	Statements that don't already have a Quotation built from them yet,
	scoped the same way this app's other pickers are (own, unless
	Commercial Manager/System Manager)."""
	conditions = ["docstatus = 1", "(quotation is null or quotation = '')", "name like %(txt)s"]
	values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

	roles = frappe.get_roles(frappe.session.user)
	if not ({"Commercial Manager", "System Manager"} & set(roles)):
		conditions.append("owner = %(user)s")
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		select name
		from `tabSupplier Comparative Statement`
		where {" and ".join(conditions)}
		order by modified desc
		limit %(page_len)s offset %(start)s
		""",
		values,
	)
