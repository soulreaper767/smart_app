# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt


class Indent(Document):
	def validate(self):
		self.calculate_totals()

	def calculate_totals(self):
		"""Same shape as every other item-table total in this app -- computed
		server-side rather than relying on client JS, so it's correct even for
		a row added via "Get Items From > Sales Invoice"."""
		total_qty = 0.0
		total_amount = 0.0
		for row in self.get("items") or []:
			row.amount = flt(row.qty) * flt(row.rate)
			total_qty += flt(row.qty)
			total_amount += flt(row.amount)
		self.total_qty = total_qty
		self.total_amount = total_amount

	def on_submit(self):
		"""Status is entirely automatic from here on -- no manual "mark as"
		button (see close_indents_on_full_payment in utils.py for the other
		end of it): Submitted always means "In Process", and the only thing
		that ever moves it to "Closed" is the linked Sales Invoice actually
		being paid in full."""
		self.indent_status = "In Process"

	def on_cancel(self):
		self.indent_status = ""


@frappe.whitelist()
def get_sales_invoices_for_indent(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for the "Get Items From > Sales Invoice" button on a
	blank Indent (indent.js) -- mirrors get_quotations_for_rfq in inquiry.py:
	a Commercial Officer only ever sees their own submitted Sales Invoices,
	Commercial Manager/System Manager see every submitted one."""
	conditions = ["docstatus = 1", "(name like %(txt)s or customer_name like %(txt)s)"]
	values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

	roles = frappe.get_roles(frappe.session.user)
	if not ({"Commercial Manager", "System Manager"} & set(roles)):
		conditions.append("owner = %(user)s")
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		select name, customer_name
		from `tabSales Invoice`
		where {" and ".join(conditions)}
		order by modified desc
		limit %(page_len)s offset %(start)s
		""",
		values,
	)


# Item master fieldnames that might hold an HS/customs tariff code, tried in
# order -- ERPNext ships no single guaranteed field for this across editions/
# regional modules, so this is a best-effort auto-fill only; hs_code on
# Indent Item is always a plain editable field regardless (see its own
# description), never something a blank lookup here should block on.
HS_CODE_CANDIDATE_FIELDS = ("gst_hsn_code", "customs_tariff_number", "hs_code", "custom_hs_code")


def _best_effort_hs_code(item_code):
	meta = frappe.get_meta("Item")
	for fieldname in HS_CODE_CANDIDATE_FIELDS:
		if meta.has_field(fieldname):
			value = frappe.db.get_value("Item", item_code, fieldname)
			if value:
				return value
	return None


def _build_indent_from_sales_invoice(si):
	"""Shared by both create_indent_from_sales_invoice (builds a new,
	separate Indent -- the "Create" button on a submitted Sales Invoice) and
	get_indent_data_from_sales_invoice (returns the same data as a plain
	dict for a blank Indent already open in the browser to pull in via its
	own "Get Items From" button -- see RFQ's identical two-function split in
	inquiry.py, for the same reason: erpnext.utils.map_current_doc's
	MultiSelectDialog + row-mapper pipeline isn't built for cloning one
	whole source document's data onto a blank one)."""
	indent = frappe.new_doc("Indent")
	indent.company = si.company
	indent.currency = si.currency
	indent.sales_invoice = si.name
	indent.sales_order = next((d.sales_order for d in si.items if d.get("sales_order")), None)
	indent.inquiry = si.get("inquiry")
	indent.customer = si.customer
	indent.customer_address_display = si.get("address_display")
	indent.tc_name = si.get("tc_name")
	indent.terms = si.get("terms")

	for row in si.items:
		if not row.item_code:
			continue
		indent.append(
			"items",
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"description": row.description,
				"hs_code": _best_effort_hs_code(row.item_code),
				"qty": row.qty,
				"uom": row.uom,
				"rate": row.rate,
				"amount": row.amount,
			},
		)

	return indent


@frappe.whitelist()
def create_indent_from_sales_invoice(sales_invoice_name):
	"""Builds a brand new, separate draft Indent from a submitted Sales
	Invoice -- the "Create > Indent" button added to the core Sales Invoice
	form (see setup_sales_pipeline_integration in install.py). Left as a
	draft: the Commercial team still has to pick which Supplier is actually
	fulfilling this shipment (bank details/seller address then auto-fill
	from that Supplier's own record) and fill in the trade-terms grid before
	this is ready to send anywhere."""
	if not frappe.has_permission("Indent", "create"):
		frappe.throw(_("You do not have permission to create an Indent."), frappe.PermissionError)

	si = frappe.get_doc("Sales Invoice", sales_invoice_name)
	si.check_permission("read")

	if not si.items:
		frappe.throw(_("This Sales Invoice has no items to build an Indent from."))

	indent = _build_indent_from_sales_invoice(si)
	indent.insert(ignore_permissions=True, ignore_mandatory=True)
	return indent.name


@frappe.whitelist()
def get_indent_data_from_sales_invoice(sales_invoice_name):
	"""Used by the "Get Items From > Sales Invoice" button on a blank Indent
	(indent.js). Returns the same data create_indent_from_sales_invoice
	would build, as plain data for the client to merge into the form
	that's already open (frm.set_value / clear_table / add_child)."""
	si = frappe.get_doc("Sales Invoice", sales_invoice_name)
	si.check_permission("read")

	if not si.items:
		frappe.throw(_("This Sales Invoice has no items to build an Indent from."))

	indent = _build_indent_from_sales_invoice(si)

	return {
		"company": indent.company,
		"currency": indent.currency,
		"sales_invoice": indent.sales_invoice,
		"sales_order": indent.sales_order,
		"inquiry": indent.inquiry,
		"customer": indent.customer,
		"customer_address_display": indent.customer_address_display,
		"tc_name": indent.tc_name,
		"terms": indent.terms,
		"items": [
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"description": d.description,
				"hs_code": d.hs_code,
				"qty": d.qty,
				"uom": d.uom,
				"rate": d.rate,
				"amount": d.amount,
			}
			for d in indent.items
		],
	}
