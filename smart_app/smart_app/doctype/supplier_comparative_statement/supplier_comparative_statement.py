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
		self.comparative_status = "Completed"

	def on_cancel(self):
		self.comparative_status = ""


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
	doc.currency = (
		frappe.db.get_value("Quotation", rfq.get("quotation"), "currency")
		if rfq.get("quotation")
		else frappe.db.get_single_value("Global Defaults", "default_currency")
	)
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
