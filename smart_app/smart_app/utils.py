# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt

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

	ensure_marketer_record_for_user(doc.user_id, doc.employee_name, doc.name)


def ensure_marketer_record_for_user(user, display_name, employee=None):
	"""Give a User who's just become a Marketer (auto_assign_marketer_role
	above) their own Marketer master record if they don't already have
	one -- Inquiry.marketer links to Marketer, not Employee/User directly,
	so without this a brand-new Marketer would have nothing to be assigned
	to Inquiries as. Named after the Employee's own name, falling back to
	appending the User's own name on a collision (two Employees sharing a
	display name)."""
	if frappe.db.exists("Marketer", {"user": user}):
		return

	marketer_name = display_name or user
	if frappe.db.exists("Marketer", marketer_name):
		marketer_name = f"{marketer_name} ({user})"

	frappe.get_doc(
		{
			"doctype": "Marketer",
			"marketer_name": marketer_name,
			"user": user,
			"employee": employee,
		}
	).insert(ignore_permissions=True)


def sync_marketer_user_permission(doc, method=None):
	"""Marketer.on_update: keep a Marketer's own scoped User Permission
	(restricting them, via Inquiry's `marketer` field, to Inquiries they're
	actually assigned to -- see enforce_marketer_restriction in inquiry.py
	for the server-side guard this backs up) in sync with whether the
	linked User still actually holds the Marketer role. Scoped to the
	Inquiry doctype only via `applicable_for`, so it never restricts this
	same User's access elsewhere."""
	existing = frappe.db.get_value(
		"User Permission",
		{"allow": "Marketer", "for_value": doc.name, "applicable_for": APPLICABLE_FOR},
		["name", "user"],
		as_dict=True,
	)
	should_have_permission = (
		doc.user and not doc.is_disabled and "Marketer" in frappe.get_roles(doc.user)
	)

	if should_have_permission:
		if existing and existing.user == doc.user:
			return
		if existing:
			frappe.delete_doc("User Permission", existing.name, ignore_permissions=True)
		frappe.get_doc(
			{
				"doctype": "User Permission",
				"user": doc.user,
				"allow": "Marketer",
				"for_value": doc.name,
				"applicable_for": APPLICABLE_FOR,
				"apply_to_all_doctypes": 0,
			}
		).insert(ignore_permissions=True)
	elif existing:
		frappe.delete_doc("User Permission", existing.name, ignore_permissions=True)


def sync_marketer_user_permission_for_user(doc, method=None):
	"""User.on_update: role changes may add/remove the Marketer role --
	re-sync every Marketer record linked to this User to match."""
	for marketer in frappe.get_all("Marketer", filters={"user": doc.name}, pluck="name"):
		sync_marketer_user_permission(frappe.get_doc("Marketer", marketer))


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


def get_default_warehouse_for_company(company):
	"""Best-effort resolution of a company's default Warehouse. Used both by
	ensure_item_default_warehouse below and by inquiry.py's RFQ item builder
	(create_request_for_quotation / get_request_for_quotation_data) to fill
	in a row's `warehouse` -- ERPNext's own erpnext.buying.utils.
	validate_stock_item_warehouse throws "Row #{n}: Warehouse is mandatory
	for stock Item {item}" the instant a stock Item's row has a qty but no
	warehouse, on *every* save (not just submit) of Request for Quotation,
	Supplier Quotation, or Purchase Order (see RequestForQuotation.validate /
	SupplierQuotation.validate, both of which call validate_for_items
	unconditionally)."""
	if not company:
		return None

	stock_settings_warehouse = frappe.db.get_single_value("Stock Settings", "default_warehouse")
	if (
		stock_settings_warehouse
		and frappe.db.get_value("Warehouse", stock_settings_warehouse, "company") == company
	):
		return stock_settings_warehouse

	# Every Company gets a "Stores - <abbr>" warehouse created automatically
	# by core ERPNext when the Company itself is created -- the standard
	# default target if Stock Settings doesn't name one explicitly.
	stores = frappe.db.get_value(
		"Warehouse", {"company": company, "warehouse_name": "Stores", "disabled": 0}, "name"
	)
	if stores:
		return stores

	return frappe.db.get_value(
		"Warehouse",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
		order_by="creation asc",
	)


def ensure_item_default_warehouse(doc, method=None):
	"""Item.validate: give a stock Item a default Warehouse for the site's
	default Company if it doesn't have one, so it never trips ERPNext's own
	"Warehouse is mandatory for stock Item" validation the moment it's used
	with a qty on a Request for Quotation / Supplier Quotation / Purchase
	Order (see get_default_warehouse_for_company above for exactly which
	core check this is).

	Every Item quick-created from an Item Link field in this app (Inquiry
	Item / Quotation Item / RFQ Item -- see grant_master_data_access in
	install.py, "a NPD Inquiry is often about an item that doesn't exist
	yet") defaults "Maintain Stock" ON with an empty Item Defaults table --
	core ERPNext's own backfill for that (update_defaults_from_item_group in
	erpnext/stock/doctype/item/item.py) only pulls from the *current user's*
	personal default warehouse (frappe.defaults.get_defaults()), which no
	Inquiry/Commercial role here has ever had a reason to set. Filled in here
	instead, for the site's global default Company only -- least-surprise,
	and doesn't invent defaults for companies this app was never told about."""
	if not doc.is_stock_item:
		return

	company = frappe.defaults.get_global_default("company")
	if not company:
		return
	if any(d.company == company for d in doc.get("item_defaults") or []):
		return

	warehouse = get_default_warehouse_for_company(company)
	if warehouse:
		doc.append("item_defaults", {"company": company, "default_warehouse": warehouse})


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


def ensure_customer_for_supplier(supplier_name):
	"""Commission Invoice (see that doctype's own submit logic) bills the
	Supplier for this app's actual revenue -- the commission on an Indent
	they fulfilled, not the trade's own full value (that's between Buyer
	and Supplier directly; Smart Chemicals is never paid it). Core
	ERPNext's Sales Invoice always bills a *Customer*, never a Supplier
	directly, so the Supplier needs a matching Customer record to stand in
	as the actual billing party -- created once, reused every time after
	(via the `represents_supplier` Custom Field, setup_commission_invoice
	in install.py), never duplicated."""
	existing = frappe.db.get_value("Customer", {"represents_supplier": supplier_name}, "name")
	if existing:
		return existing

	supplier = frappe.db.get_value(
		"Supplier", supplier_name, ["supplier_name", "supplier_group"], as_dict=True
	)
	customer_name = supplier.supplier_name or supplier_name
	if frappe.db.exists("Customer", customer_name):
		customer_name = f"{customer_name} (Commission)"

	customer = frappe.get_doc(
		{
			"doctype": "Customer",
			"customer_name": customer_name,
			"customer_type": "Company",
			"customer_group": frappe.db.get_single_value("Selling Settings", "customer_group"),
			"territory": frappe.db.get_single_value("Selling Settings", "territory"),
			"represents_supplier": supplier_name,
		}
	)
	customer.insert(ignore_permissions=True, ignore_mandatory=True)
	return customer.name


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


# ---------------------------------------------------------------------------
# Indent: Supplier bank details, and Sales Invoice -> Inquiry traceability.
# ---------------------------------------------------------------------------

# The pipe-delimited "Key: Value | Key: Value" shape smart_app.supplier_import
# writes into Supplier.supplier_details, e.g. "Contact Person: X | Office
# Address: Y | Beneficiary Name: Z | Bank Name: W | Bank Address: V |
# Account No: U | SWIFT Code: T" -- and that manually-entered Suppliers tend
# to follow too, since it's what this app's own Customer Details section
# shows as an example. Keys are matched case-insensitively.
BANK_DETAIL_KEYS = {
	"beneficiary name": "bank_beneficiary_name",
	"bank name": "bank_name",
	"bank address": "bank_address",
	"account no": "bank_account_no",
	"swift code": "swift_code",
}
ADDRESS_KEYS = ("office address", "factory address")


def parse_supplier_details_text(text):
	"""Best-effort parse of Supplier.supplier_details' free text (see
	BANK_DETAIL_KEYS above) into the structured bank_*/seller_address_display
	fields Indent fetches from directly (see setup_supplier_bank_fields in
	install.py). Returns only the keys it actually found -- never guesses,
	never overwrites (see ensure_supplier_bank_details below, which only
	fills a field that's still blank)."""
	result = {}
	if not text:
		return result

	for segment in text.split("|"):
		if ":" not in segment:
			continue
		key, _, value = segment.partition(":")
		key = key.strip().lower()
		value = value.strip()
		if not value:
			continue
		if key in BANK_DETAIL_KEYS:
			result[BANK_DETAIL_KEYS[key]] = value
		elif key in ADDRESS_KEYS and "seller_address_display" not in result:
			result["seller_address_display"] = value

	return result


def ensure_supplier_bank_details(doc, method=None):
	"""Supplier.validate: self-healing fill of the structured bank_*/
	seller_address_display fields from supplier_details' free text,
	whenever one of them is still blank -- covers both the bulk import
	(supplier_import.py, which writes exactly this pipe-delimited shape) and
	anyone typing a new Supplier's details by hand the same way. Only ever
	fills a blank field; a value entered directly (by import backfill or by
	hand) always wins and is never overwritten."""
	parsed = parse_supplier_details_text(doc.get("supplier_details"))
	for fieldname, value in parsed.items():
		if not doc.get(fieldname):
			doc.set(fieldname, value)


def set_inquiry_from_quotation(doc, method=None):
	"""Sales Order.validate: best-effort carry-over of the `inquiry` Custom
	Field (see setup_sales_pipeline_integration in install.py) from
	whichever Quotation this Sales Order was created from. Sales Order is
	deliberately built from Quotation, not Inquiry directly -- core
	ERPNext already provides that completely natively, both directions
	(Quotation's own "Create > Sales Order" button, and the reverse "Get
	Items From > Quotation" on a blank Sales Order) -- but neither knows
	about a Custom Field added after the fact, so `inquiry` never carries
	over on its own. The native mapper does set `prevdoc_docname` on each
	Sales Order Item to the source Quotation's name regardless (see
	erpnext.selling.doctype.quotation.quotation._make_sales_order's
	field_map), which is enough to look `inquiry` up from there."""
	if doc.get("inquiry"):
		return

	quotation = next(
		(d.prevdoc_docname for d in doc.get("items") or [] if d.get("prevdoc_docname")), None
	)
	if quotation:
		doc.inquiry = frappe.db.get_value("Quotation", quotation, "inquiry")


def set_inquiry_from_sales_order(doc, method=None):
	"""Sales Invoice.validate: best-effort carry-over of the `inquiry`
	Custom Field (see setup_sales_pipeline_integration in install.py) from
	whichever Sales Order this Sales Invoice's items were raised against --
	core ERPNext's own Sales Order -> Sales Invoice mapper
	(erpnext.selling.doctype.sales_order.sales_order.make_sales_invoice) has
	a fixed field_map we can't edit and doesn't know about a Custom Field we
	added after the fact, so it never carries `inquiry` over on its own.
	Needed so Indent (built from a submitted Sales Invoice) can still trace
	all the way back to the originating Inquiry, the same way Request for
	Quotation's own `inquiry` field does for the buying side."""
	if doc.get("inquiry"):
		return

	sales_order = next((d.sales_order for d in doc.get("items") or [] if d.get("sales_order")), None)
	if sales_order:
		doc.inquiry = frappe.db.get_value("Sales Order", sales_order, "inquiry")


def close_indents_on_full_payment(doc, method=None):
	"""Sales Invoice.on_update: an Indent's `indent_status` is entirely
	automatic (see Indent.on_submit in indent.py) -- Submitted always means
	"In Process", and the only thing that ever moves it on to "Closed" is
	its own Commission Invoice's Sales Invoice (the commission amount --
	this app's actual revenue, never the trade's own full value, see
	Commission Invoice) being paid in full, checked here every time that
	Sales Invoice is saved (a Payment Entry reconciling against it updates
	and re-saves it, which is what actually re-fires this). No manual
	"mark as" button for this path -- keeps the lifecycle tied to real
	payment status; a Commission Officer can still write off a stalled
	balance and close both manually (Commission Invoice.write_off_and_close)
	for the "unlikely to ever be received" case."""
	if not frappe.db.exists("DocType", "Commission Invoice"):
		return
	if doc.docstatus != 1 or flt(doc.outstanding_amount) != 0:
		return

	for ci in frappe.get_all(
		"Commission Invoice",
		filters={"sales_invoice": doc.name, "docstatus": 1, "commission_status": ["!=", "Received"]},
		fields=["name", "indent"],
	):
		frappe.db.set_value("Commission Invoice", ci.name, "commission_status", "Received")
		if ci.indent:
			frappe.db.set_value(
				"Indent",
				ci.indent,
				"indent_status",
				"Closed",
				update_modified=False,
			)


def send_commission_reminder_email(commission_invoice):
	"""Emails the Supplier's default contact about an outstanding
	commission -- used both by the manual "Send Reminder" button
	(commission_invoice.py, on demand) and send_overdue_commission_reminders
	below (the daily scheduled sweep). Returns False rather than throwing
	when there's simply no contact/email on file, since the scheduled sweep
	calls this in a loop and one missing contact shouldn't stop the rest."""
	from frappe.contacts.doctype.contact.contact import get_default_contact

	if not commission_invoice.supplier:
		return False

	contact_name = get_default_contact("Supplier", commission_invoice.supplier)
	email = frappe.db.get_value("Contact", contact_name, "email_id") if contact_name else None
	if not email:
		return False

	frappe.sendmail(
		recipients=[email],
		subject=frappe._("Commission payment reminder — {0}").format(commission_invoice.name),
		message=frappe.render_template(
			"""
			<p>Dear {{ supplier_name }},</p>
			<p>This is a reminder that a commission of {{ currency }} {{ "%.2f"|format(outstanding) }}
			is outstanding against Indent {{ indent }}{% if due_date %} (due {{ due_date }}){% endif %}.</p>
			<p>Please arrange payment at your earliest convenience.</p>
			""",
			{
				"supplier_name": commission_invoice.supplier_name,
				"currency": commission_invoice.currency,
				"outstanding": flt(commission_invoice.outstanding_amount),
				"indent": commission_invoice.indent,
				"due_date": frappe.utils.formatdate(commission_invoice.due_date)
				if commission_invoice.due_date
				else None,
			},
		),
		reference_doctype="Commission Invoice",
		reference_name=commission_invoice.name,
	)
	return True


def send_overdue_commission_reminders():
	"""Scheduled daily (see hooks.py scheduler_events) -- emails a reminder
	for every submitted, not-yet-Received/Written-Off Commission Invoice
	whose due date has passed and still has an outstanding balance. The
	manual "Send Reminder" button (commission_invoice.py) uses the same
	underlying email for an on-demand nudge."""
	if not frappe.db.exists("DocType", "Commission Invoice"):
		return

	overdue = frappe.get_all(
		"Commission Invoice",
		filters={
			"docstatus": 1,
			"commission_status": ["not in", ["Received", "Written Off"]],
			"due_date": ["<", frappe.utils.today()],
		},
		pluck="name",
	)
	for name in overdue:
		doc = frappe.get_doc("Commission Invoice", name)
		if flt(doc.outstanding_amount) > 0:
			send_commission_reminder_email(doc)
