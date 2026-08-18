# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.contacts.doctype.contact.contact import get_default_contact
from frappe.contacts.doctype.address.address import get_default_address


class Inquiry(Document):
	def validate(self):
		self.set_marketer_from_user()
		self.enforce_marketer_restriction()
		self.pull_customer_contact_details()

	def before_insert(self):
		self.set_marketer_from_user()

	def set_marketer_from_user(self):
		"""Auto-select the Marketer field for users who hold the Marketer role."""
		if self.marketer:
			return

		if "Marketer" not in frappe.get_roles(frappe.session.user):
			return

		employee = get_employee_for_user(frappe.session.user)
		if employee:
			self.marketer = employee

	def enforce_marketer_restriction(self):
		"""A user with only the Marketer role (no manager rights) may only
		create/keep Inquiries where they are the assigned Marketer."""
		user_roles = frappe.get_roles(frappe.session.user)
		if "Inquiry Manager" in user_roles or "System Manager" in user_roles:
			return
		if "Marketer" not in user_roles:
			return

		employee = get_employee_for_user(frappe.session.user)
		if employee and self.marketer and self.marketer != employee:
			frappe.throw(
				_("You can only create or update Inquiries where you are the assigned Marketer.")
			)

	def pull_customer_contact_details(self):
		"""Refresh cached contact/address display fields from the linked Customer."""
		if not self.inquiry_source:
			for f in (
				"contact_person",
				"contact_display",
				"contact_email",
				"contact_mobile",
				"customer_address",
				"address_display",
			):
				self.set(f, None)
			return

		if self.contact_person and self.customer_address:
			return

		details = get_customer_contact_details(self.inquiry_source)
		for key, value in details.items():
			if not self.get(key):
				self.set(key, value)


def get_employee_for_user(user):
	return frappe.db.get_value("Employee", {"user_id": user, "status": "Active"}, "name")


@frappe.whitelist()
def get_my_marketer_employee():
	"""Used by inquiry.js to auto-fill the Marketer field for the current
	user on a new Inquiry. Deliberately a narrow whitelisted lookup rather
	than a plain frappe.db.get_list client call, since Marketer only holds
	`select` (not `read`) on Employee — see grant_master_data_access in
	install.py for why."""
	if "Marketer" not in frappe.get_roles(frappe.session.user):
		return None
	return get_employee_for_user(frappe.session.user)


@frappe.whitelist()
def get_customer_contact_details(customer):
	"""Return the default contact & address display info for a Customer."""
	if not customer:
		return {}

	out = {
		"contact_person": None,
		"contact_display": None,
		"contact_email": None,
		"contact_mobile": None,
		"customer_address": None,
		"address_display": None,
	}

	contact_name = get_default_contact("Customer", customer)
	if contact_name:
		contact = frappe.get_cached_doc("Contact", contact_name)
		out["contact_person"] = contact_name
		out["contact_display"] = " ".join(filter(None, [contact.first_name, contact.last_name]))
		out["contact_email"] = contact.email_id
		out["contact_mobile"] = contact.mobile_no or contact.phone

	address_name = get_default_address("Customer", customer)
	if address_name:
		address = frappe.get_cached_doc("Address", address_name)
		out["customer_address"] = address_name
		out["address_display"] = address.get_display()

	return out


@frappe.whitelist()
def get_marketers(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query: only Employees whose linked User has the Marketer role."""
	return frappe.db.sql(
		"""
		select e.name, e.employee_name
		from `tabEmployee` e
		inner join `tabHas Role` hr on hr.parent = e.user_id and hr.parenttype = 'User'
		where hr.role = 'Marketer'
			and e.status = 'Active'
			and (e.name like %(txt)s or e.employee_name like %(txt)s)
		order by e.employee_name
		limit %(page_len)s offset %(start)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def create_customer_from_referred_party(inquiry_name):
	"""Create a new Customer from the referred-party details captured on an Inquiry."""
	doc = frappe.get_doc("Inquiry", inquiry_name)
	doc.check_permission("write")

	if not doc.is_for_referred_party:
		frappe.throw(_("This Inquiry is not marked for a referred party."))
	if not doc.referred_party_name:
		frappe.throw(_("Referred Party Name is required to create a Customer."))
	if doc.new_customer:
		frappe.throw(_("A Customer has already been created for this referral: {0}").format(doc.new_customer))

	customer = frappe.new_doc("Customer")
	customer.customer_name = doc.referred_party_name
	customer.customer_type = "Individual"
	customer.customer_group = frappe.db.get_single_value("Selling Settings", "customer_group") or _(
		"Individual"
	)
	customer.territory = frappe.db.get_single_value("Selling Settings", "territory") or _("All Territories")
	customer.insert(ignore_permissions=True, ignore_mandatory=True)

	if doc.referred_party_contact_person or doc.referred_party_email or doc.referred_party_phone:
		contact = frappe.new_doc("Contact")
		contact.first_name = doc.referred_party_contact_person or doc.referred_party_name
		if doc.referred_party_email:
			contact.append("email_ids", {"email_id": doc.referred_party_email, "is_primary": 1})
		if doc.referred_party_phone:
			contact.append("phone_nos", {"phone": doc.referred_party_phone, "is_primary_mobile_no": 1})
		contact.append("links", {"link_doctype": "Customer", "link_name": customer.name})
		contact.insert(ignore_permissions=True, ignore_mandatory=True)

	doc.new_customer = customer.name
	doc.save(ignore_permissions=True)

	frappe.msgprint(_("Customer {0} created from the referred party details.").format(customer.name))
	return customer.name


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
	"""Mirrors erpnext.crm.doctype.opportunity.opportunity.make_quotation --
	called from the "Get Items From" > "Inquiry" button added to the core
	Quotation form via a Client Script (see setup_quotation_integration in
	install.py). Only Inquiries with inquiry_status "Quotation" are offered
	as a source, via that button's get_query_filters."""

	def set_missing_values(source, target):
		from erpnext.setup.utils import get_exchange_rate

		quotation = frappe.get_doc(target)
		quotation.quotation_to = "Customer"
		quotation.party_name = source.inquiry_source

		company_currency = frappe.get_cached_value("Company", quotation.company, "default_currency")
		if quotation.currency and quotation.currency != company_currency:
			quotation.conversion_rate = get_exchange_rate(
				quotation.currency, company_currency, quotation.transaction_date, args="for_selling"
			)

		quotation.run_method("set_missing_values")
		quotation.run_method("calculate_taxes_and_totals")

	def update_item(source_row, target_row, source_parent):
		target_row.item_code = source_row.item
		target_row.qty = source_row.qty

	doclist = get_mapped_doc(
		"Inquiry",
		source_name,
		{
			"Inquiry": {
				"doctype": "Quotation",
				"field_map": {
					"company": "company",
					"currency": "currency",
					"name": "inquiry",
				},
			},
			"Inquiry Item": {
				"doctype": "Quotation Item",
				"field_map": {"item": "item_code", "qty": "qty"},
				"postprocess": update_item,
				"add_if_empty": True,
			},
		},
		target_doc,
		set_missing_values,
	)

	return doclist
