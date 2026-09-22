# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import add_to_date, flt, get_datetime

from smart_app.smart_app.utils import ensure_customer_for_supplier

COMMISSION_ROLES = {"Commercial Manager", "Commercial Officer", "System Manager"}
COMMISSION_INCOME_ITEM = "Commission Income"


class CommissionInvoice(Document):
	def validate(self):
		self.calculate_commission()
		self.calculate_due_date()

	def calculate_commission(self):
		"""Every component (percentage of the Indent's own value, a rate per
		unit of a specific item, a flat fixed amount -- any mix of them) adds
		up to the gross commission; a discount (percentage or fixed) then
		brings that down to the net commission -- the amount actually
		invoiced on submit. All computed server-side, not relied on from
		client JS, so it's correct regardless of how the components were
		entered."""
		gross = 0.0
		for row in self.get("components") or []:
			if row.component_type == "Percentage of Indent Value":
				row.amount = flt(self.indent_value) * flt(row.percentage) / 100
			elif row.component_type == "Rate per UOM":
				row.amount = flt(row.qty) * flt(row.rate)
			elif row.component_type == "Fixed Amount":
				row.amount = flt(row.fixed_amount)
			else:
				row.amount = 0
			gross += flt(row.amount)

		self.gross_commission = gross

		if self.discount_type == "Percentage":
			self.discount_amount = flt(gross) * flt(self.discount_percentage) / 100
		elif self.discount_type != "Fixed Amount":
			self.discount_amount = 0

		self.net_commission = flt(gross) - flt(self.discount_amount)
		if self.net_commission < 0:
			frappe.throw(_("Discount cannot bring the commission below zero."))

	def calculate_due_date(self):
		if self.swift_copy_received_on:
			due = add_to_date(get_datetime(self.swift_copy_received_on), hours=self.payment_due_hours or 48)
			self.due_date = due.date()
		else:
			self.due_date = None

	def before_submit(self):
		if not self.net_commission:
			frappe.throw(_("Net Commission must be greater than zero to submit."))
		if not self.billing_customer:
			self.billing_customer = ensure_customer_for_supplier(self.supplier)

	def on_submit(self):
		"""Creates and submits the real, GL-posting Sales Invoice for the
		Net Commission amount -- this, not the Indent's own trade value, is
		this app's actual revenue (see the module docstring context in
		indent.py: Indent moved to sourcing from Quotation specifically so
		it never depends on a Sales Invoice for the trade's full value)."""
		self.create_and_submit_sales_invoice()
		self.commission_status = "Submitted"

	def create_and_submit_sales_invoice(self):
		if self.sales_invoice:
			return

		item_code = ensure_commission_income_item()
		si = frappe.new_doc("Sales Invoice")
		si.customer = self.billing_customer
		si.company = self.company
		si.currency = self.currency
		si.posting_date = self.posting_date
		if self.due_date:
			si.due_date = self.due_date
		si.append(
			"items",
			{
				"item_code": item_code,
				"item_name": COMMISSION_INCOME_ITEM,
				"description": _("Commission on Indent {0}").format(self.indent),
				"qty": 1,
				"rate": self.net_commission,
			},
		)
		si.run_method("set_missing_values")
		si.run_method("calculate_taxes_and_totals")
		if self.due_date:
			si.due_date = self.due_date
		si.insert(ignore_permissions=True, ignore_mandatory=True)
		si.submit()

		self.db_set("sales_invoice", si.name)

	def on_cancel(self):
		"""Cascades to the Sales Invoice this Commission Invoice created --
		Frappe's own LinkExistsError (e.g. an unreconciled Payment Entry
		still referencing it) surfaces as-is rather than being swallowed,
		since silently leaving a stray Sales Invoice behind would be worse."""
		if self.sales_invoice:
			si = frappe.get_doc("Sales Invoice", self.sales_invoice)
			if si.docstatus == 1:
				si.cancel()
		self.commission_status = ""


def ensure_commission_income_item():
	"""The one Item every Commission Invoice's underlying Sales Invoice
	bills against -- a non-stock service item, created once."""
	if frappe.db.exists("Item", COMMISSION_INCOME_ITEM):
		return COMMISSION_INCOME_ITEM

	item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": COMMISSION_INCOME_ITEM,
			"item_name": COMMISSION_INCOME_ITEM,
			"item_group": item_group,
			"is_stock_item": 0,
			"is_sales_item": 1,
			"stock_uom": "Nos",
			"description": "Commission income on indenting/brokering an Indent -- this app's actual revenue.",
		}
	).insert(ignore_permissions=True, ignore_mandatory=True)
	return COMMISSION_INCOME_ITEM


def _build_commission_invoice_from_indent(indent):
	commission_invoice = frappe.new_doc("Commission Invoice")
	commission_invoice.company = indent.company
	commission_invoice.currency = indent.currency
	commission_invoice.indent = indent.name
	commission_invoice.billing_customer = ensure_customer_for_supplier(indent.supplier)
	return commission_invoice


@frappe.whitelist()
def create_commission_invoice_from_indent(indent_name):
	"""Builds a brand new, separate draft Commission Invoice from a
	submitted Indent -- the "Create > Commission Invoice" button on Indent
	(indent.js). Left as a draft with no components yet: the Commercial
	team still has to decide how commission is actually calculated for
	this deal (percentage, per-unit rate, fixed, or a mix) before this is
	ready to submit."""
	if not (COMMISSION_ROLES & set(frappe.get_roles(frappe.session.user))):
		frappe.throw(_("You are not allowed to create a Commission Invoice."), frappe.PermissionError)

	indent = frappe.get_doc("Indent", indent_name)
	indent.check_permission("read")
	if indent.docstatus != 1:
		frappe.throw(_("Only a submitted Indent can have a Commission Invoice raised against it."))
	if not indent.supplier:
		frappe.throw(_("This Indent has no Supplier set -- commission is owed by the Supplier."))

	commission_invoice = _build_commission_invoice_from_indent(indent)
	commission_invoice.insert(ignore_permissions=True, ignore_mandatory=True)
	return commission_invoice.name


@frappe.whitelist()
def get_commission_invoice_data_from_indent(indent_name):
	"""Used by the "Get Items From > Indent" button on a blank Commission
	Invoice. Same shared-builder shape as Indent's own Quotation pickers."""
	indent = frappe.get_doc("Indent", indent_name)
	indent.check_permission("read")
	if indent.docstatus != 1:
		frappe.throw(_("Only a submitted Indent can have a Commission Invoice raised against it."))
	if not indent.supplier:
		frappe.throw(_("This Indent has no Supplier set -- commission is owed by the Supplier."))

	commission_invoice = _build_commission_invoice_from_indent(indent)
	return {
		"company": commission_invoice.company,
		"currency": commission_invoice.currency,
		"indent": commission_invoice.indent,
		"billing_customer": commission_invoice.billing_customer,
	}


@frappe.whitelist()
def get_indents_for_commission_invoice(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for the "Get Items From > Indent" button on a blank
	Commission Invoice -- submitted Indents only, scoped the same way
	Indent's own Quotation picker is (own, unless Commercial Manager/
	System Manager)."""
	conditions = ["docstatus = 1", "(name like %(txt)s or supplier_name like %(txt)s)"]
	values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

	roles = frappe.get_roles(frappe.session.user)
	if not ({"Commercial Manager", "System Manager"} & set(roles)):
		conditions.append("owner = %(user)s")
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		select name, supplier_name
		from `tabIndent`
		where {" and ".join(conditions)}
		order by modified desc
		limit %(page_len)s offset %(start)s
		""",
		values,
	)


@frappe.whitelist()
def write_off_and_close(commission_invoice_name, reason):
	"""For a partial commission receipt where the remaining balance is
	unlikely to ever come in: writes off the linked Sales Invoice's
	outstanding balance via a zero-payment Payment Entry (the same native
	mechanism ERPNext's own "Create > Payment" dialog uses when you leave a
	write-off difference -- get_payment_entry does all the real account/
	party/currency resolution; only the amounts are overridden here), then
	closes both this Commission Invoice and its Indent."""
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	if not (COMMISSION_ROLES & set(frappe.get_roles(frappe.session.user))):
		frappe.throw(_("You are not allowed to write off a Commission Invoice."), frappe.PermissionError)
	if not reason:
		frappe.throw(_("Please give a reason for writing this off."))

	doc = frappe.get_doc("Commission Invoice", commission_invoice_name)
	doc.check_permission("write")
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted Commission Invoice can be written off."))
	if not doc.sales_invoice:
		frappe.throw(_("No linked Sales Invoice to write off."))

	si = frappe.get_doc("Sales Invoice", doc.sales_invoice)
	outstanding = flt(si.outstanding_amount)
	if outstanding <= 0:
		frappe.throw(_("Nothing outstanding on the linked Sales Invoice to write off."))

	write_off_account = frappe.db.get_value(
		"Company", si.company, "write_off_account"
	) or frappe.db.get_single_value("Accounts Settings", "write_off_account")
	if not write_off_account:
		frappe.throw(
			_("Please set a default Write Off Account (Company or Accounts Settings) before writing off.")
		)

	pe = get_payment_entry("Sales Invoice", si.name)
	pe.paid_amount = 0
	pe.received_amount = 0
	pe.write_off_amount = outstanding
	pe.write_off_account = write_off_account
	for row in pe.references:
		row.allocated_amount = outstanding
	pe.reference_no = _("Write-off: {0}").format(reason)[:140]
	pe.reference_date = frappe.utils.today()
	pe.insert(ignore_permissions=True)
	pe.submit()

	doc.db_set("write_off_reason", reason)
	doc.db_set("commission_status", "Written Off")
	if doc.indent:
		frappe.db.set_value("Indent", doc.indent, "indent_status", "Closed", update_modified=False)

	return pe.name


@frappe.whitelist()
def send_commission_reminder(commission_invoice_name):
	"""Manual "Send Reminder" button (commission_invoice.js) -- emails the
	Supplier's default contact about an outstanding commission. Same
	underlying email as the automatic scheduled sweep
	(send_overdue_commission_reminders, utils.py), just triggered on demand."""
	from smart_app.smart_app.utils import send_commission_reminder_email

	doc = frappe.get_doc("Commission Invoice", commission_invoice_name)
	doc.check_permission("read")
	return send_commission_reminder_email(doc)
