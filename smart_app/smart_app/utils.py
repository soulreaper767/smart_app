# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe

APPLICABLE_FOR = "Inquiry"
INQUIRY_ROLES = {"Inquiry Officer", "Marketer", "Inquiry Manager"}
UMBRELLA_ROLE = "Inquiry User"
MODULE_PROFILE_NAME = "Inquiry Team"
# Roles that don't count as "this user also needs access elsewhere" when
# deciding whether to restrict their sidebar to just Smart App.
NON_RESTRICTIVE_ROLES = {"All", "Guest", "Desk User", "Employee", UMBRELLA_ROLE} | INQUIRY_ROLES
# Who needs the Inquiry User umbrella role (see sync_inquiry_user_role) --
# deliberately a SEPARATE set from INQUIRY_ROLES, not a superset of it,
# because INQUIRY_ROLES also drives sync_module_profile (restricted sidebar)
# and auto_assign_marketer_role, and Commercial Manager must never trigger
# either of those, only the workflow-edit gate below.
INQUIRY_USER_ROLE_TRIGGERS = INQUIRY_ROLES | {"Commercial Manager"}


def sync_module_profile(doc, method=None):
	"""User.validate: give users whose roles are *entirely* Inquiry-related a
	focused sidebar (Smart App only) via a shared Module Profile, hiding every
	other workspace. Deliberately skipped for System Manager and for anyone
	who also holds a role outside this app (e.g. Sales User) so their access
	elsewhere is never touched — and only ever applied/removed if this is the
	profile we set in the first place, so a manually chosen Module Profile is
	always left alone."""
	if not frappe.db.exists("Module Profile", MODULE_PROFILE_NAME):
		return

	current_roles = {r.role for r in doc.get("roles")}
	if "System Manager" in current_roles:
		return

	has_inquiry_role = bool(current_roles & INQUIRY_ROLES)
	has_other_roles = bool(current_roles - NON_RESTRICTIVE_ROLES)

	if has_inquiry_role and not has_other_roles:
		if not doc.module_profile:
			doc.module_profile = MODULE_PROFILE_NAME
	elif doc.module_profile == MODULE_PROFILE_NAME and has_other_roles:
		doc.module_profile = None


def sync_inquiry_user_role(doc, method=None):
	"""User.validate: keep the internal "Inquiry User" umbrella role (used
	only to satisfy the Inquiry Workflow's single-role `allow_edit` slot) in
	sync with whether this user needs it -- any of the three real Inquiry
	roles, OR Commercial Manager (who must be able to edit an Inquiry -- to
	set commercial_officer -- no matter what inquiry_status/workflow state
	it's currently in). Runs in `validate` (not `on_update`) so the role
	list is fixed up as part of the same save instead of triggering a
	second, recursive save."""
	if not frappe.db.exists("Role", UMBRELLA_ROLE):
		return

	current_roles = {r.role for r in doc.get("roles")}
	needs_umbrella_role = bool(current_roles & INQUIRY_USER_ROLE_TRIGGERS)
	has_umbrella_role = UMBRELLA_ROLE in current_roles

	if needs_umbrella_role and not has_umbrella_role:
		doc.append("roles", {"role": UMBRELLA_ROLE})
	elif has_umbrella_role and not needs_umbrella_role:
		doc.set("roles", [r for r in doc.get("roles") if r.role != UMBRELLA_ROLE])


def auto_assign_marketer_role(doc, method=None):
	"""Employee.on_update: Employee carries full create+write for Inquiry
	Officer/Marketer/Inquiry Manager so the Marketer link field's own
	"+ Create a New Employee" quick-create works the same way every other
	Link field in this app does — but that generic Employee form has no way
	to also assign a role. So: whenever an Employee gets a `user_id` linked
	by someone holding one of our Inquiry roles, auto-grant that user the
	Marketer role, since linking a user from this app's context only makes
	sense if they're meant to become a Marketer. Left alone for anyone
	editing Employee without any Inquiry role (e.g. HR staff), so this never
	surprises an unrelated Employee edit."""
	if not doc.user_id:
		return

	session_roles = set(frappe.get_roles(frappe.session.user))
	if not (session_roles & INQUIRY_ROLES):
		return

	user = frappe.get_doc("User", doc.user_id)
	if "Marketer" not in [r.role for r in user.roles]:
		user.append("roles", {"role": "Marketer"})
		user.save(ignore_permissions=True)


def sync_marketer_user_permission(doc, method=None):
	"""Employee.on_update: keep the Marketer -> Employee User Permission in sync."""
	sync_marketer_permission_for_employee(doc.name)


def sync_marketer_user_permission_for_user(doc, method=None):
	"""User.on_update: role changes may add/remove the Marketer role."""
	for employee in frappe.get_all("Employee", filters={"user_id": doc.name}, pluck="name"):
		sync_marketer_permission_for_employee(employee)


COMMERCIAL_STATUS_ORDER = ["Unassigned", "Assigned", "Quotation Created", "RFQ Created", "RFQ Sent"]


def sync_commercial_officer_user_permission(doc, method=None):
	"""User.on_update: a Commercial Officer's `commercial_officer` value on
	Inquiry is a direct Link to User (not via Employee like Marketer), so a
	single standing User Permission — scoped to the Inquiry doctype only via
	`applicable_for`, exactly like the Marketer one — is enough to restrict
	them to Inquiries assigned to themselves. Inquiry's own `inquiry_officer`
	field has `ignore_user_permissions` set specifically so this doesn't
	also filter by that unrelated field."""
	existing = frappe.db.get_value(
		"User Permission",
		{"user": doc.name, "allow": "User", "for_value": doc.name, "applicable_for": APPLICABLE_FOR},
		"name",
	)
	has_role = "Commercial Officer" in [r.role for r in doc.get("roles")]

	if has_role and not existing:
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": doc.name,
				"allow": "User",
				"for_value": doc.name,
				"applicable_for": APPLICABLE_FOR,
				"apply_to_all_doctypes": 0,
			}
		).insert(ignore_permissions=True)
	elif not has_role and existing:
		frappe.delete_doc("User Permission", existing, ignore_permissions=True)


def advance_inquiry_commercial_status(inquiry_name, new_status):
	"""Only ever moves commercial_status forward (Unassigned -> Assigned ->
	Quotation Created -> RFQ Created -> RFQ Sent), never backward — e.g. a
	second Quotation created after an RFQ has already gone out shouldn't
	reset the status to "Quotation Created"."""
	if not inquiry_name:
		return

	current_status = frappe.db.get_value("Inquiry", inquiry_name, "commercial_status")
	if current_status is None:
		return

	try:
		is_forward = COMMERCIAL_STATUS_ORDER.index(new_status) > COMMERCIAL_STATUS_ORDER.index(
			current_status
		)
	except ValueError:
		return

	if is_forward:
		frappe.db.set_value("Inquiry", inquiry_name, "commercial_status", new_status)


def update_inquiry_on_quotation_created(doc, method=None):
	"""Quotation.after_insert: advance the source Inquiry's commercial_status."""
	if doc.get("inquiry"):
		advance_inquiry_commercial_status(doc.inquiry, "Quotation Created")


def update_inquiry_on_rfq_submit(doc, method=None):
	"""Request for Quotation.on_submit: advance the source Inquiry's
	commercial_status once the RFQ is actually submitted (not just drafted),
	since submission is the precondition for send_supplier_emails to work."""
	if doc.get("inquiry"):
		advance_inquiry_commercial_status(doc.inquiry, "RFQ Sent")


def enforce_single_preferred_supplier(doc, method=None):
	"""Item.validate: an Item can carry several Suppliers on file (see
	setup_item_supplier_customization in install.py, which adds
	`supplier_type` and `is_preferred_supplier` to the native "Supplier
	Items" table) -- only one of them should ever be flagged preferred at a
	time, so there's one unambiguous default to point to. If a user checks
	a second row, silently uncheck the earlier one(s) rather than blocking
	the save with a validation error."""
	seen_preferred = False
	for row in doc.get("supplier_items") or []:
		if row.get("is_preferred_supplier"):
			if seen_preferred:
				row.is_preferred_supplier = 0
			else:
				seen_preferred = True


def ensure_default_price_list(party_doctype, party_name, display_name):
	"""Give a Customer/Supplier its own dedicated Price List, so "multiple
	sales and purchase prices for the same item" falls out naturally --
	each party's own Price List holds its own rate for a given Item,
	entirely via native Price List + Item Price (Customer/Supplier both
	already have a `default_price_list` Link field in core ERPNext; nothing
	custom needed there). Idempotent: a party that already has one (set
	manually, or by an earlier run of this same function) is left alone.
	Called both from the Customer/Supplier `after_insert` hooks below (so
	every new party gets one automatically) and from
	backfill_party_price_lists in install.py (so this also applies to every
	party that already existed before this feature was added)."""
	existing = frappe.db.get_value(party_doctype, party_name, "default_price_list")
	if existing:
		return existing

	is_selling = party_doctype == "Customer"
	suffix = "Selling" if is_selling else "Buying"
	price_list_name = f"{display_name} - {suffix}"

	if frappe.db.exists("Price List", price_list_name):
		# Name collision with an unrelated Price List (e.g. two parties that
		# happen to share a display name) -- fall back to a name that's
		# guaranteed unique by including the party's own document name.
		price_list_name = f"{display_name} - {suffix} ({party_name})"

	if not frappe.db.exists("Price List", price_list_name):
		currency = frappe.db.get_single_value("Global Defaults", "default_currency")
		frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": price_list_name,
				"currency": currency,
				"buying": 0 if is_selling else 1,
				"selling": 1 if is_selling else 0,
				"enabled": 1,
			}
		).insert(ignore_permissions=True)

	frappe.db.set_value(party_doctype, party_name, "default_price_list", price_list_name)
	return price_list_name


def create_default_price_list_for_customer(doc, method=None):
	"""Customer.after_insert."""
	ensure_default_price_list("Customer", doc.name, doc.customer_name or doc.name)


def create_default_price_list_for_supplier(doc, method=None):
	"""Supplier.after_insert."""
	ensure_default_price_list("Supplier", doc.name, doc.supplier_name or doc.name)


def _upsert_item_price(item_code, price_list, rate):
	"""Keep at most one current Item Price per (item, price_list) pair --
	update its rate in place rather than inserting a new dated row every
	time, since Item Price's own duplicate check (same item/price
	list/UOM/valid-from/customer/supplier) would otherwise throw on a
	same-day repeat and interrupt whatever submit triggered this."""
	if not item_code or not price_list or rate in (None, 0):
		return

	name = frappe.db.get_value(
		"Item Price", {"item_code": item_code, "price_list": price_list}, "name"
	)
	if name:
		item_price = frappe.get_doc("Item Price", name)
		if item_price.price_list_rate != rate:
			item_price.price_list_rate = rate
			item_price.save(ignore_permissions=True)
	else:
		frappe.get_doc(
			{
				"doctype": "Item Price",
				"item_code": item_code,
				"price_list": price_list,
				"price_list_rate": rate,
			}
		).insert(ignore_permissions=True)


def sync_item_prices_from_quotation(doc, method=None):
	"""Quotation.on_submit: the selling side of automated multi-price
	management -- once a Quotation to a Customer is submitted, push each
	item's quoted rate into that Customer's own dedicated Price List (see
	ensure_default_price_list), so their current selling price is always
	up to date with no manual Item Price entry required."""
	if doc.quotation_to != "Customer" or not doc.party_name:
		return

	customer_name = frappe.db.get_value("Customer", doc.party_name, "customer_name")
	price_list = ensure_default_price_list("Customer", doc.party_name, customer_name or doc.party_name)
	for row in doc.get("items") or []:
		_upsert_item_price(row.item_code, price_list, row.rate)


def sync_item_prices_from_supplier_quotation(doc, method=None):
	"""Supplier Quotation.on_submit: the buying side -- once a supplier's
	reply to an RFQ is submitted, push each item's quoted rate into that
	Supplier's own dedicated Price List, so "last quoted buying price" is
	always current without manual entry."""
	if not doc.supplier:
		return

	supplier_name = frappe.db.get_value("Supplier", doc.supplier, "supplier_name")
	price_list = ensure_default_price_list("Supplier", doc.supplier, supplier_name or doc.supplier)
	for row in doc.get("items") or []:
		_upsert_item_price(row.item_code, price_list, row.rate)


def sync_marketer_permission_for_employee(employee_name):
	"""Ensure a Marketer only ever sees/edits Inquiries where they are the
	assigned Marketer. This is done with a standard Frappe User Permission,
	scoped to the Inquiry doctype only via `applicable_for`, so it never
	restricts the same user's access to Employee/HR records elsewhere."""
	employee = frappe.db.get_value(
		"Employee", employee_name, ["user_id", "status"], as_dict=True
	)
	if not employee:
		return

	existing = frappe.db.get_value(
		"User Permission",
		{
			"allow": "Employee",
			"for_value": employee_name,
			"applicable_for": APPLICABLE_FOR,
		},
		["name", "user"],
		as_dict=True,
	)

	should_have_permission = (
		employee.user_id
		and employee.status == "Active"
		and "Marketer" in frappe.get_roles(employee.user_id)
	)

	if should_have_permission:
		if existing and existing.user == employee.user_id:
			return
		if existing:
			frappe.delete_doc("User Permission", existing.name, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": employee.user_id,
				"allow": "Employee",
				"for_value": employee_name,
				"applicable_for": APPLICABLE_FOR,
				"apply_to_all_doctypes": 0,
			}
		).insert(ignore_permissions=True)
	elif existing:
		frappe.delete_doc("User Permission", existing.name, ignore_permissions=True)
