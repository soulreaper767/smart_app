# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.contacts.doctype.contact.contact import get_default_contact
from frappe.contacts.doctype.address.address import get_default_address

from smart_app.smart_app.utils import get_default_warehouse_for_company

INQUIRY_EDIT_ROLES = {"Inquiry Officer", "Marketer", "Inquiry Manager"}


class Inquiry(Document):
	def validate(self):
		self.set_marketer_from_customer_or_user()
		self.enforce_marketer_restriction()
		self.pull_customer_contact_details()
		self.log_marketer_change()
		self.enforce_status_change_reason()
		self.sync_commercial_status()

	def before_insert(self):
		self.set_marketer_from_customer_or_user()

	def before_update_after_submit(self):
		"""Frappe only runs the controller's validate() for a plain "save"
		or "submit" action (see run_before_save_methods in frappe/model/
		document.py) -- when a document is already submitted (docstatus=1)
		and gets saved again with no docstatus change, that's a distinct
		"update_after_submit" action, and the ONLY controller hook Frappe
		calls for it is before_update_after_submit/on_update_after_submit.
		validate() never runs -- so anything validate() would otherwise
		catch (marketer reassignment logging, the mandatory status-change
		reason, commercial_status syncing) needs repeating here too, since
		every one of these can still happen on an already-submitted Inquiry
		(assign_commercial_officer always hits this path, and workflow
		transitions like Replied -> Convert commonly happen well after
		submission)."""
		self.log_marketer_change()
		self.enforce_status_change_reason()
		self.sync_commercial_status()

	def set_marketer_from_customer_or_user(self):
		"""Auto-fill Marketer, in priority order: (1) leave alone if already
		set; (2) the Customer's own default Marketer, if it has one -- a
		Customer with an assigned Marketer should default every new Inquiry
		to them; (3) the current user's own Marketer record, if they hold
		the Marketer role -- so a Marketer creating their own Inquiry for a
		Customer with no default yet doesn't have to pick themselves."""
		if self.marketer:
			return

		if self.inquiry_source:
			customer_marketer = frappe.db.get_value("Customer", self.inquiry_source, "marketer")
			if customer_marketer:
				self.marketer = customer_marketer
				return

		if "Marketer" not in frappe.get_roles(frappe.session.user):
			return

		own_marketer = get_marketer_for_user(frappe.session.user)
		if own_marketer:
			self.marketer = own_marketer

	def enforce_marketer_restriction(self):
		"""A user with only the Marketer role (no manager rights) may only
		create/keep Inquiries where they are the assigned Marketer."""
		user_roles = frappe.get_roles(frappe.session.user)
		if "Inquiry Manager" in user_roles or "System Manager" in user_roles:
			return
		if "Marketer" not in user_roles:
			return

		own_marketer = get_marketer_for_user(frappe.session.user)
		if own_marketer and self.marketer and self.marketer != own_marketer:
			frappe.throw(
				_("You can only create or update Inquiries where you are the assigned Marketer.")
			)

	def log_marketer_change(self):
		"""Every assignment/reassignment of Marketer is recorded (not just
		overwritten) -- see marketer_history (Inquiry Marketer Log) and the
		"update the Customer's own default too?" prompt this drives
		client-side (inquiry.js, update_customer_marketer below)."""
		before = self.get_doc_before_save()
		previous_marketer = before.marketer if before else None
		if self.marketer == previous_marketer:
			return
		if not self.marketer and not previous_marketer:
			return
		self.append(
			"marketer_history",
			{
				"previous_marketer": previous_marketer,
				"marketer": self.marketer,
				"changed_by": frappe.session.user,
				"changed_on": frappe.utils.now_datetime(),
			},
		)

	def enforce_status_change_reason(self):
		"""Status changes are Inquiry Manager/System Manager only (see
		inquiry_status's own permlevel 2, and every Workflow transition
		being manager_only -- setup_workflow in install.py) -- but even a
		Manager must give a reason, logged to the timeline rather than a
		single field that would just get overwritten next time."""
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or before.inquiry_status == self.inquiry_status:
			return
		if not self.status_change_reason:
			frappe.throw(_("Please provide a reason for changing the Inquiry status."))
		self.add_comment(
			"Info",
			_("Status changed from {0} to {1}: {2}").format(
				before.inquiry_status, self.inquiry_status, self.status_change_reason
			),
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
		smart_app.smart_app.utils), never walked backwards here.

		Treats a blank/null commercial_status the same as "Unassigned" --
		any Inquiry that existed before this field was added to the doctype
		has NULL here, not the literal string "Unassigned" (Frappe doesn't
		retroactively backfill a new field's default onto existing rows),
		so an exact-string check alone silently never fires for those."""
		is_unassigned = self.commercial_status in (None, "", "Unassigned")
		if self.commercial_officer and is_unassigned:
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
	Manager/Officer *read* of a non-submitted Inquiry.

	Deliberately scoped to ptype == "read" only, never write/submit/etc:
	Frappe's own Document.check_permission() calls this same hook for every
	permission type it evaluates, including internally as part of a save
	(e.g. `frappe.client.set_value`, used by the Assign button) -- returning
	False for a non-read ptype here caused a save that should have been
	allowed (Commercial Manager writing to an already-submitted Inquiry) to
	be rejected with a generic "does not have doctype access" error. The
	actual goal -- Commercial Manager/Officer never see a draft at all --
	is already fully achieved by gating just the read/list path; there's
	nothing to additionally deny once someone has legitimately reached a
	document via read access. get_permission_query_conditions above is
	unaffected by this -- it only ever applies to list-style queries, never
	to a direct save."""
	if ptype != "read":
		return None

	user = user or frappe.session.user
	roles = set(frappe.get_roles(user))

	if roles & COMMERCIAL_VIEW_EXEMPT_ROLES:
		return None
	if roles & COMMERCIAL_VIEW_ROLES and doc.docstatus != 1:
		return False
	return None


def get_marketer_for_user(user):
	return frappe.db.get_value("Marketer", {"user": user, "is_disabled": 0}, "name")


@frappe.whitelist()
def get_my_marketer():
	"""Used by inquiry.js to auto-fill the Marketer field for the current
	user on a new Inquiry. Deliberately a narrow whitelisted lookup rather
	than a plain frappe.db.get_list client call, matching the same
	least-privilege reasoning grant_master_data_access uses elsewhere."""
	if "Marketer" not in frappe.get_roles(frappe.session.user):
		return None
	return get_marketer_for_user(frappe.session.user)


@frappe.whitelist()
def get_customer_contact_details(customer):
	"""Return the default contact/address/marketer info for a Customer --
	used both to fill in a new Inquiry's contact fields and (via `marketer`)
	to default its Marketer to whoever this Customer is already assigned to
	(see set_marketer_from_customer_or_user, the server-side equivalent of
	this for anything that doesn't go through the form, e.g. a Data Import)."""
	if not customer:
		return {}

	out = {
		"contact_person": None,
		"contact_display": None,
		"contact_email": None,
		"contact_mobile": None,
		"customer_address": None,
		"address_display": None,
		"marketer": frappe.db.get_value("Customer", customer, "marketer"),
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
	"""Link-field query for the Marketer field -- active Marketers only."""
	return frappe.db.sql(
		"""
		select name, marketer_name
		from `tabMarketer`
		where is_disabled = 0
			and (name like %(txt)s or marketer_name like %(txt)s)
		order by marketer_name
		limit %(page_len)s offset %(start)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def update_customer_marketer(customer, marketer):
	"""Called from inquiry.js when a user changes an Inquiry's Marketer and
	confirms they also want the Customer's own default Marketer updated to
	match -- keeps the Customer master in step going forward, without ever
	silently overwriting it (the confirm dialog is what "asks" per the task
	this was built for; nothing here bypasses that -- it only runs once the
	user has already agreed).

	Explicit role check + ignore_permissions, the same pattern already
	proven elsewhere in this app (assign_commercial_officer,
	create_customer_from_referred_party) -- generic Customer `write` is
	deliberately Inquiry Manager only (see grant_master_data_access,
	"Inquiry Manager also gets write, for corrections"), but anyone who can
	edit Inquiries at all is exactly who this feature is for."""
	if not (customer and marketer):
		return
	if not (set(frappe.get_roles(frappe.session.user)) & (INQUIRY_EDIT_ROLES | {"System Manager"})):
		frappe.throw(_("You do not have permission to update this Customer."), frappe.PermissionError)
	frappe.db.set_value("Customer", customer, "marketer", marketer)


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
def assign_commercial_officer(inquiry_name, commercial_officer=None):
	"""Used by the Assign/Reassign button on the Inquiry form. Deliberately
	bypasses the generic permission stack (Document.check_permission /
	frappe.client.set_value both route through has_permission ->
	get_doc_permissions -> has_user_permission -> several layers of
	evaluation that proved hard to pin down precisely from outside a live
	site) via an explicit role check plus ignore_permissions=True instead --
	the same proven pattern already used by create_marketer and
	create_customer_from_referred_party above, both of which work reliably
	for exactly this reason."""
	if not ({"Commercial Manager", "System Manager"} & set(frappe.get_roles(frappe.session.user))):
		frappe.throw(
			_("Only a Commercial Manager can assign a Commercial Officer."), frappe.PermissionError
		)

	if commercial_officer and "Commercial Officer" not in frappe.get_roles(commercial_officer):
		frappe.throw(_("{0} does not have the Commercial Officer role.").format(commercial_officer))

	doc = frappe.get_doc("Inquiry", inquiry_name)
	if doc.docstatus != 1:
		frappe.throw(_("Only a submitted Inquiry can be assigned to a Commercial Officer."))

	doc.commercial_officer = commercial_officer
	doc.save(ignore_permissions=True)

	return doc.commercial_officer


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


def _append_rfq_item(rfq, source_row):
	"""Shared by both create_request_for_quotation and
	get_request_for_quotation_data below: append one Quotation Item's data
	as a Request for Quotation Item row.

	Sets `warehouse` deliberately -- ERPNext's own
	erpnext.buying.utils.validate_stock_item_warehouse throws "Row #{n}:
	Warehouse is mandatory for stock Item {item}" on *every* save (not just
	submit) of a Request for Quotation whose Item is a stock Item with a qty
	but no warehouse on its row (RequestForQuotation.validate calls
	validate_for_items unconditionally). Every Item quick-created from this
	app's own Item Link fields defaults "Maintain Stock" on (see
	ensure_item_default_warehouse in utils.py), so a row built without a
	warehouse here would fail that check immediately on insert."""
	item = frappe.db.get_value(
		"Item", source_row.item_code, ["stock_uom", "is_stock_item"], as_dict=True
	)
	if not item:
		return

	warehouse = None
	if item.is_stock_item:
		warehouse = frappe.db.get_value(
			"Item Default", {"parent": source_row.item_code, "company": rfq.company}, "default_warehouse"
		) or get_default_warehouse_for_company(rfq.company)

	rfq.append(
		"items",
		{
			"item_code": source_row.item_code,
			"qty": source_row.qty,
			"schedule_date": frappe.utils.add_days(frappe.utils.today(), 7),
			"uom": item.stock_uom,
			"stock_uom": item.stock_uom,
			"conversion_factor": 1,
			"warehouse": warehouse,
		},
	)


def _populate_rfq_suppliers_and_template(rfq):
	"""Shared by both directions of Quotation <-> Request for Quotation
	generation (create_request_for_quotation and make_request_for_quotation
	below): given an RFQ whose `items` table is already filled in,
	aggregate every supplier of every one of those items
	(Item.supplier_items — an item commonly has several, trader and
	manufacturer alike, and all of them are pulled in so the RFQ can go out
	to multiple suppliers at once) and wire in the corporate email
	template. Throws if not one single item has a supplier on file at all —
	an RFQ with nobody to send it to isn't useful, and this way the
	deliberately-missing "who to send this to" problem surfaces up front
	rather than as a silently supplier-less draft."""
	suppliers_seen = {row.supplier for row in rfq.get("suppliers") or []}

	for row in rfq.get("items") or []:
		if not row.item_code:
			continue
		for supplier in frappe.get_all(
			"Item Supplier", filters={"parent": row.item_code}, pluck="supplier"
		):
			if supplier in suppliers_seen:
				continue
			suppliers_seen.add(supplier)
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

	if not suppliers_seen:
		frappe.throw(
			_(
				"None of the items in this Quotation have a linked Supplier yet. "
				"Add suppliers under the Item's own \"Supplier Items\" table first."
			)
		)

	from smart_app.install import RFQ_EMAIL_TEMPLATE_NAME

	if frappe.db.exists("Email Template", RFQ_EMAIL_TEMPLATE_NAME):
		rfq.email_template = RFQ_EMAIL_TEMPLATE_NAME
		if hasattr(rfq, "set_data_for_supplier"):
			rfq.set_data_for_supplier()


@frappe.whitelist()
def create_request_for_quotation(quotation_name):
	"""Builds a brand new, separate draft Request for Quotation from a
	Quotation's items -- the "create a new document" direction, used by the
	"Create > Request for Quotation" button on an already-open Quotation.
	See make_request_for_quotation below for the reverse "Get Items From"
	direction, used from a blank Request for Quotation instead.

	Left as a draft for deliberate human review: this only prepares the RFQ
	(items + supplier/contact/email rows) -- submitting it (which also
	sends it, see the "Submit & Send to Suppliers" button) is a separate,
	explicit step for whoever is generating it.

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
	if frappe.get_meta("Request for Quotation").has_field("quotation"):
		rfq.quotation = quotation.name
	if frappe.get_meta("Request for Quotation").has_field("inquiry"):
		rfq.inquiry = quotation.get("inquiry")

	for row in quotation.items:
		if not row.item_code:
			continue
		_append_rfq_item(rfq, row)

	_populate_rfq_suppliers_and_template(rfq)

	rfq.insert(ignore_permissions=True, ignore_mandatory=True)

	if quotation.get("inquiry"):
		frappe.db.set_value("Inquiry", quotation.inquiry, "commercial_status", "RFQ Created")

	return rfq.name


@frappe.whitelist()
def get_quotations_for_rfq(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query for the "Get Items From > Quotation" button on a
	blank Request for Quotation (RFQ_CLIENT_SCRIPT_JS). A Commercial
	Officer should only ever be offered their OWN submitted Quotations to
	build an RFQ from, never anyone else's -- Quotation has no
	commercial_officer field of its own (only Inquiry does), so `owner` is
	the accurate proxy: a Commercial Officer only ever creates a Quotation
	for an Inquiry already scoped to themselves in the first place.
	Commercial Manager/System Manager (oversight roles) see every
	submitted Quotation."""
	conditions = ["docstatus = 1", "(name like %(txt)s or party_name like %(txt)s)"]
	values = {"txt": f"%{txt}%", "start": start, "page_len": page_len}

	roles = frappe.get_roles(frappe.session.user)
	if not ({"Commercial Manager", "System Manager"} & set(roles)):
		conditions.append("owner = %(user)s")
		values["user"] = frappe.session.user

	return frappe.db.sql(
		f"""
		select name, party_name
		from `tabQuotation`
		where {" and ".join(conditions)}
		order by modified desc
		limit %(page_len)s offset %(start)s
		""",
		values,
	)


@frappe.whitelist()
def get_request_for_quotation_data(quotation_name):
	"""Used by the "Get Items From > Quotation" button on a blank Request
	for Quotation (RFQ_CLIENT_SCRIPT_JS in install.py). Builds the exact
	same items/suppliers/email_template as create_request_for_quotation,
	but returns them as plain data for the client to merge into the form
	that's already open (frm.set_value / clear_table / add_child), rather
	than inserting a separate document -- erpnext.utils.map_current_doc's
	generic MultiSelectDialog + frappe.model.mapper.map_docs pipeline
	(the mechanism make_quotation's own Inquiry-mapping button uses) is
	built around picking one-or-more *source rows*, not a single parent
	document to clone data from, and didn't suit this direction well."""
	quotation = frappe.get_doc("Quotation", quotation_name)
	quotation.check_permission("read")

	if not quotation.items:
		frappe.throw(_("This Quotation has no items to request a quotation for."))

	rfq = frappe.new_doc("Request for Quotation")
	rfq.company = quotation.company
	rfq.transaction_date = frappe.utils.today()
	if frappe.get_meta("Request for Quotation").has_field("quotation"):
		rfq.quotation = quotation.name
	if frappe.get_meta("Request for Quotation").has_field("inquiry"):
		rfq.inquiry = quotation.get("inquiry")

	for row in quotation.items:
		if not row.item_code:
			continue
		_append_rfq_item(rfq, row)

	_populate_rfq_suppliers_and_template(rfq)

	return {
		"company": rfq.company,
		"transaction_date": rfq.transaction_date,
		"quotation": rfq.get("quotation"),
		"inquiry": rfq.get("inquiry"),
		"email_template": rfq.get("email_template"),
		"message_for_supplier": rfq.get("message_for_supplier"),
		"mfs_html": rfq.get("mfs_html"),
		"use_html": rfq.get("use_html"),
		"subject": rfq.get("subject"),
		"items": [
			{
				"item_code": d.item_code,
				"qty": d.qty,
				"schedule_date": d.schedule_date,
				"uom": d.uom,
				"stock_uom": d.stock_uom,
				"conversion_factor": d.conversion_factor,
				"warehouse": d.warehouse,
			}
			for d in rfq.items
		],
		"suppliers": [
			{
				"supplier": d.supplier,
				"contact": d.contact,
				"email_id": d.email_id,
				"send_email": d.send_email,
			}
			for d in rfq.suppliers
		],
	}
