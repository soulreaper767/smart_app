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
		self.sync_commercial_status()

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

	def sync_commercial_status(self):
		"""Once a Commercial Manager assigns commercial_officer on a submitted
		Inquiry, flip commercial_status from Unassigned to Assigned. Later
		stages (Quotation Created / RFQ Created / RFQ Sent) are advanced
		elsewhere, from Quotation/Request for Quotation doc events (see
		smart_app.smart_app.utils), never walked backwards here."""
		if self.commercial_officer and self.commercial_status == "Unassigned":
			self.commercial_status = "Assigned"
		elif not self.commercial_officer and self.commercial_status == "Assigned":
			self.commercial_status = "Unassigned"


COMMERCIAL_VIEW_ROLES = {"Commercial Manager", "Commercial Officer"}
COMMERCIAL_VIEW_EXEMPT_ROLES = {"Inquiry Manager", "System Manager"}


def get_permission_query_conditions(user):
	"""Registered via hooks.py `permission_query_conditions`. The Commercial
	team only ever has a reason to look at a *submitted* Inquiry (that's the
	whole trigger for the pipeline) -- restrict Commercial Manager/Officer
	from seeing drafts at all: list view, reports, kanban, search, Number
	Card counts. Mirrors ToDo's own get_permission_query_conditions pattern
	in core Frappe. Anyone who's also Inquiry Manager/System Manager is
	exempt, same as has_permission below."""
	if not user:
		user = frappe.session.user

	roles = set(frappe.get_roles(user))
	if roles & COMMERCIAL_VIEW_EXEMPT_ROLES:
		return None
	if roles & COMMERCIAL_VIEW_ROLES:
		return "`tabInquiry`.docstatus = 1"
	return None


def has_permission(doc, ptype="read", user=None):
	"""Registered via hooks.py `has_permission`. Mirrors
	get_permission_query_conditions for direct single-document access
	(opening by URL/name bypasses list-view filters). Returns None ("no
	opinion, evaluate normally") except to explicitly deny a Commercial
	Manager/Officer a non-submitted Inquiry."""
	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))

	if roles & COMMERCIAL_VIEW_EXEMPT_ROLES:
		return None
	if roles & COMMERCIAL_VIEW_ROLES and doc.docstatus != 1:
		return False
	return None


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
def get_commercial_officers(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query: only Users with the Commercial Officer role -- used
	by the commercial_officer field so a Commercial Manager assigning it is
	only ever offered actual Commercial Officers, not any arbitrary user."""
	return frappe.db.sql(
		"""
		select u.name, u.full_name
		from `tabUser` u
		inner join `tabHas Role` hr on hr.parent = u.name and hr.parenttype = 'User'
		where hr.role = 'Commercial Officer'
			and u.enabled = 1
			and (u.name like %(txt)s or u.full_name like %(txt)s)
		order by u.full_name
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
	install.py). Only Inquiries assigned to the current Commercial Officer
	(and submitted) are offered as a source, via that button's
	get_query_filters."""

	def set_missing_values(source, target):
		quotation = frappe.get_doc(target)
		quotation.quotation_to = "Customer"
		quotation.party_name = source.inquiry_source
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


@frappe.whitelist()
def create_request_for_quotation(quotation_name):
	"""Builds a draft Request for Quotation from a Quotation's items,
	aggregating every supplier of every item (Item.supplier_items — an item
	commonly has several, trader and manufacturer alike, and all of them are
	pulled in so the RFQ can go out to multiple suppliers at once).

	Left as a draft for deliberate human review: this only prepares the RFQ
	(items + supplier/contact/email rows) -- submitting it and clicking
	"Send Supplier Emails" (both native Request for Quotation actions) is a
	separate, explicit step for whoever is generating it.

	Explicitly role-gated (not just relying on the button's client-side
	`frappe.model.can_create` check) since the RFQ itself is inserted with
	ignore_permissions=True below."""
	if not frappe.has_permission("Request for Quotation", "create"):
		frappe.throw(
			_("You do not have permission to create a Request for Quotation."), frappe.PermissionError
		)

	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("read")

	if not quotation.items:
		frappe.throw(_("This Quotation has no items to request a quotation for."))

	rfq = frappe.new_doc("Request for Quotation")
	rfq.company = quotation.company
	rfq.transaction_date = frappe.utils.today()
	if frappe.get_meta("Request for Quotation").has_field("inquiry"):
		rfq.inquiry = quotation.get("inquiry")

	suppliers_seen = set()
	for row in quotation.items:
		if not row.item_code:
			continue

		stock_uom = frappe.db.get_value("Item", row.item_code, "stock_uom")
		rfq.append(
			"items",
			{
				"item_code": row.item_code,
				"qty": row.qty,
				"schedule_date": frappe.utils.add_days(frappe.utils.today(), 7),
				"uom": stock_uom,
				"stock_uom": stock_uom,
				"conversion_factor": 1,
			},
		)

		for supplier in frappe.get_all(
			"Item Supplier", filters={"parent": row.item_code}, pluck="supplier"
		):
			suppliers_seen.add(supplier)

	if not suppliers_seen:
		frappe.throw(
			_(
				"None of the items in this Quotation have a linked Supplier yet. "
				"Add suppliers under the Item's own \"Supplier Items\" table first."
			)
		)

	for supplier in suppliers_seen:
		contact_name = get_default_contact("Supplier", supplier)
		email = frappe.db.get_value("Contact", contact_name, "email_id") if contact_name else None
		rfq.append(
			"suppliers",
			{
				"supplier": supplier,
				"contact": contact_name,
				"email_id": email,
				"send_email": 1 if email else 0,
			},
		)

	from smart_app.install import RFQ_EMAIL_TEMPLATE_NAME

	if frappe.db.exists("Email Template", RFQ_EMAIL_TEMPLATE_NAME):
		rfq.email_template = RFQ_EMAIL_TEMPLATE_NAME
		if hasattr(rfq, "set_data_for_supplier"):
			rfq.set_data_for_supplier()

	rfq.insert(ignore_permissions=True, ignore_mandatory=True)

	if quotation.get("inquiry"):
		frappe.db.set_value("Inquiry", quotation.inquiry, "commercial_status", "RFQ Created")

	return rfq.name
