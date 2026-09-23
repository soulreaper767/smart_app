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
		a row added via "Get Items From > Quotation"."""
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


@frappe.whitelist()
def get_indent_data_from_quotation(quotation_name):
	"""Used by the "Get Items From > Quotation" button on a blank Indent
	(indent.js). The forward direction -- "Create > Indent" on a submitted
	Quotation itself -- lives in supplier_comparative_statement.py now
	(create_indents_from_quotation), since building an Indent requires the
	same submitted Supplier Comparative Statement that button requires:
	item rate/qty/Supplier come from its own winning selection, not the
	Quotation's original (now possibly outdated) estimate.

	If the Comparative Statement's selection spans more than one winning
	Supplier, this can't fill a single blank form -- points you at
	Quotation's own "Create > Indent" button instead, which creates one
	Indent per Supplier automatically (build_indent_doc_for_supplier is
	the shared builder both this and that use, so they always source
	identically)."""
	from smart_app.smart_app.doctype.supplier_comparative_statement.supplier_comparative_statement import (
		_require_comparative_statement,
		_selected_rows_by_supplier,
		build_indent_doc_for_supplier,
	)

	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("read")
	if quotation.quotation_to != "Customer":
		frappe.throw(_("Only a Quotation addressed to a Customer can be used to build an Indent."))

	comparative_statement = _require_comparative_statement(quotation_name)
	grouped = _selected_rows_by_supplier(comparative_statement)
	if not grouped:
		frappe.throw(_("No Supplier selections found on {0}.").format(comparative_statement.name))
	if len(grouped) > 1:
		frappe.throw(
			_(
				"This Quotation's Comparative Statement has more than one winning Supplier ({0}). "
				"Use the \"Create > Indent\" button on the Quotation itself instead -- it builds "
				"one Indent per Supplier automatically."
			).format(", ".join(grouped.keys()))
		)

	supplier, rows = next(iter(grouped.items()))
	indent = build_indent_doc_for_supplier(quotation, supplier, rows)

	return {
		"company": indent.company,
		"currency": indent.currency,
		"quotation": indent.quotation,
		"inquiry": indent.inquiry,
		"customer": indent.customer,
		"customer_address_display": indent.customer_address_display,
		"tc_name": indent.tc_name,
		"terms": indent.terms,
		"supplier": indent.supplier,
		"items": [
			{
				"item_code": d.item_code,
				"item_name": d.item_name,
				"description": d.description,
				"custom_pharmacopeia": d.custom_pharmacopeia,
				"custom_item_grade": d.custom_item_grade,
				"hs_code": d.hs_code,
				"qty": d.qty,
				"uom": d.uom,
				"rate": d.rate,
				"amount": d.amount,
			}
			for d in indent.items
		],
	}
