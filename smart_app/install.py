# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
Everything needed to make Smart App feel like a native, fully independent
ERPNext workspace is set up here, idempotently, so it can run both on
`after_install` and on every `after_migrate` (self-healing on upgrades).
"""

import json

import frappe

MODULE = "Smart App"

STATUSES = ["Open", "Quotation", "Replied", "Converted", "Lost", "Closed"]

CHART_NAMES = [
	"Inquiries by Status",
	"Inquiries by Marketer",
	"Inquiries by Category",
]

CARD_NAMES = [
	"Open Inquiries",
	"Converted Inquiries",
	"Lost Inquiries",
]

COMMERCIAL_CARD_NAMES = [
	"Submitted Inquiries",
	"Unassigned Inquiries",
	"Assigned Inquiries",
	"Total Suppliers",
	"Open Indents",
]

# Commercial-side Dashboard Charts (not Inquiry-based, so built separately from
# CHART_NAMES / setup_dashboard_charts).
COMMERCIAL_CHART_NAMES = [
	"Suppliers by Country",
	"Indents by Status",
]

COMMERCIAL_STATUSES = ["Unassigned", "Assigned", "Quotation Created", "RFQ Created", "RFQ Sent"]

WORKFLOW_ACTIONS = [
	"Send for Quotation",
	"Mark as Replied",
	"Mark as Lost",
	"Convert",
	"Close",
	"Reopen",
]

MODULE_PROFILE_NAME = "Inquiry Team"

# Only these known ERPNext/HRMS/Webshop/Payments *business* modules are
# hidden for the restricted sidebar. Deliberately a blocklist, not "every
# module except Smart App" — this app has no way to know every module a
# given site has (including ones from apps it's never heard of), and a
# blocklist means an unrecognised module defaults to STAYING VISIBLE rather
# than being silently hidden.
#
# NOTE: on ERPNext v15 the Home workspace's own module is "Setup" (verified
# against a live site), not one of Frappe's core Desk/Core modules as you'd
# expect — so "Setup" must NEVER be in this list, or Home disappears along
# with it. The unavoidable tradeoff: ERP Settings/ERPNext Settings (also
# module "Setup") stay visible in the sidebar too, since Frappe blocks by
# module, not by individual workspace. That's a cosmetic leak, not a real
# access leak — actual permission on those settings doctypes is untouched.
BUSINESS_MODULES_TO_HIDE = [
	"Accounts",
	"Buying",
	"Selling",
	"Stock",
	"CRM",
	"Support",
	"Projects",
	"Assets",
	"Manufacturing",
	"Quality Management",
	"Maintenance",
	"Subcontracting",
	"Bulk Transaction",
	"Loan Management",
	"Regional",
	"HR",
	"Payroll",
	"Recruitment",
	"Performance",
	"Webshop",
	"Payments",
]

SHORTCUTS = [
	{"label": "New Inquiry", "type": "DocType", "link_to": "Inquiry", "doc_view": "New", "color": "#3B82F6"},
	{"label": "Inquiry List", "type": "DocType", "link_to": "Inquiry", "doc_view": "List", "color": "#3B82F6"},
	{
		"label": "Inquiry Kanban",
		"type": "DocType",
		"link_to": "Inquiry",
		"doc_view": "Kanban",
		"kanban_board": "Inquiry Status Board",
		"color": "#22C55E",
	},
	{"label": "Inquiry Report", "type": "DocType", "link_to": "Inquiry", "doc_view": "Report Builder", "color": "#22C55E"},
	{"label": "Inquiry Dashboard", "type": "Dashboard", "link_to": "Inquiry Dashboard", "color": "#F97316"},
	{"label": "Marketer Performance", "type": "Report", "link_to": "Marketer Performance", "color": "#F97316"},
	{"label": "Inquiry Status Summary", "type": "Report", "link_to": "Inquiry Status Summary", "color": "#F97316"},
	{"label": "Customers", "type": "DocType", "link_to": "Customer", "doc_view": "List", "color": "#A855F7"},
	{
		"label": "Inquiry Workflow",
		"type": "URL",
		"url": "/app/workflow/Inquiry Workflow",
		"color": "#A855F7",
	},
	{
		"label": "Mode of Shipment",
		"type": "DocType",
		"link_to": "Inquiry Shipment Mode",
		"doc_view": "List",
		"color": "#94A3B8",
	},
	{
		"label": "Mode of Payment",
		"type": "DocType",
		"link_to": "Inquiry Payment Mode",
		"doc_view": "List",
		"color": "#94A3B8",
	},
	{
		"label": "Incoterms",
		"type": "DocType",
		"link_to": "Inquiry Incoterm",
		"doc_view": "List",
		"color": "#94A3B8",
	},
	{
		"label": "Inquiry Category",
		"type": "DocType",
		"link_to": "Inquiry Category",
		"doc_view": "List",
		"color": "#94A3B8",
	},
]

COMMERCIAL_SHORTCUTS = [
	{
		"label": "Commercial Pipeline",
		"type": "DocType",
		"link_to": "Inquiry",
		"doc_view": "Kanban",
		"kanban_board": "Commercial Pipeline",
		"color": "#3B82F6",
	},
	{
		"label": "Commercial Assignment Overview",
		"type": "Report",
		"link_to": "Commercial Assignment Overview",
		"color": "#3B82F6",
	},
	{"label": "Suppliers", "type": "DocType", "link_to": "Supplier", "doc_view": "List", "color": "#22C55E"},
	{"label": "Quotations", "type": "DocType", "link_to": "Quotation", "doc_view": "List", "color": "#22C55E"},
	{
		"label": "Requests for Quotation",
		"type": "DocType",
		"link_to": "Request for Quotation",
		"doc_view": "List",
		"color": "#22C55E",
	},
	{
		"label": "Supplier Quotations",
		"type": "DocType",
		"link_to": "Supplier Quotation",
		"doc_view": "List",
		"color": "#22C55E",
	},
	{"label": "Sales Orders", "type": "DocType", "link_to": "Sales Order", "doc_view": "List", "color": "#A855F7"},
	{
		"label": "Sales Invoices",
		"type": "DocType",
		"link_to": "Sales Invoice",
		"doc_view": "List",
		"color": "#A855F7",
	},
	{"label": "Indents", "type": "DocType", "link_to": "Indent", "doc_view": "List", "color": "#A855F7"},
	{
		"label": "Indent Register",
		"type": "Report",
		"link_to": "Indent Register",
		"color": "#F97316",
	},
	{
		"label": "Commercial Dashboard",
		"type": "Dashboard",
		"link_to": "Commercial Dashboard",
		"color": "#F97316",
	},
	{
		"label": "Item Purchase History",
		"type": "Report",
		"link_to": "Item-wise Purchase History",
		"color": "#F97316",
	},
	{
		"label": "Supplier Quotation Comparison",
		"type": "Report",
		"link_to": "Supplier Quotation Comparison",
		"color": "#F97316",
	},
]


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	run_step(cleanup_retired_artifacts, "cleanup of retired estimated_value chart/card")
	run_step(ensure_roles, "roles")
	run_step(grant_master_data_access, "customer/item/employee access")
	run_step(grant_commercial_access, "commercial team access")
	run_step(seed_master_data, "master data")
	run_step(setup_indent_masters, "indent trade term master data")
	run_step(setup_supplier_bank_fields, "supplier bank detail fields (for Indent)")
	run_step(setup_workflow, "workflow")
	run_step(setup_kanban_board, "kanban board")
	run_step(setup_dashboard_charts, "dashboard charts")
	run_step(setup_commercial_charts, "commercial dashboard charts (suppliers, indents)")
	run_step(setup_number_cards, "number cards")
	run_step(setup_commercial_overview, "commercial overview (cards + kanban + report)")
	run_step(setup_dashboard, "dashboard")
	run_step(setup_commercial_dashboard, "commercial dashboard")
	run_step(setup_reports, "reports")
	run_step(setup_print_format, "print format")
	run_step(setup_indent_print_format, "indent print format")
	run_step(setup_workspace, "workspace")
	run_step(add_home_workspace_shortcut, "home workspace shortcut")
	run_step(grant_inquiry_manager_workflow_access, "inquiry manager workflow access")
	run_step(setup_module_profile, "restricted module profile")
	run_step(setup_quotation_integration, "quotation get-items-from + create-rfq integration")
	run_step(setup_sales_pipeline_integration, "sales order/invoice get-items-from + create-indent integration")
	run_step(setup_item_master_columns, "item master columns (UOM/pharmacopeia/grade)")
	run_step(setup_item_supplier_customization, "multi-supplier management on Item (type/preferred)")
	run_step(setup_test_users, "test users")
	run_step(backfill_commercial_manager_inquiry_user_role, "backfill Inquiry User role for Commercial Manager")
	run_step(backfill_commercial_status, "backfill blank/stuck commercial_status on existing Inquiries")
	run_step(backfill_party_price_lists, "backfill default Price Lists for existing Customers/Suppliers")
	run_step(backfill_item_default_warehouse, "backfill default warehouse on existing stock Items")
	run_step(backfill_supplier_bank_details, "backfill supplier bank details (for Indent)")
	run_step(backfill_rfq_quotation_links, "backfill quotation link on existing Requests for Quotation")
	run_step(setup_email_branding, "email footer branding")
	run_step(setup_email_templates, "RFQ email template")

	frappe.db.commit()
	frappe.clear_cache()


def run_step(fn, label):
	try:
		fn()
		frappe.db.commit()
	except Exception:
		frappe.db.rollback()
		frappe.log_error(title=f"Smart App setup: {label} failed")
		print(f"[smart_app] WARNING: could not set up {label} automatically. See Error Log for details.")


# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------


def ensure_roles():
	# "Inquiry User" is an internal umbrella role (auto-synced onto any user who
	# holds Inquiry Manager / Inquiry Officer / Marketer, see utils.py) used only
	# to satisfy the Inquiry Workflow's mandatory single-role "allow_edit" slot
	# for the active states — it carries no DocType permissions of its own.
	#
	# Commercial Manager / Commercial Officer are a separate, downstream team:
	# they only ever see Inquiries once submitted (see Inquiry's permissions
	# and utils.sync_commercial_officer_user_permission), so they're
	# deliberately NOT part of the Inquiry-role set above.
	for role in (
		"Inquiry Manager",
		"Inquiry Officer",
		"Marketer",
		"Inquiry User",
		"Commercial Manager",
		"Commercial Officer",
	):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


# ---------------------------------------------------------------------------
# Access to Customer / Item / Employee for whoever creates Inquiries
# ---------------------------------------------------------------------------


def grant_master_data_access():
	"""None of Inquiry Officer / Marketer / Inquiry Manager have any
	permission on the core doctypes Inquiry links to out of the box, which
	makes those Link fields unusable (Frappe blocks Link search/select
	without at least `select` on the target doctype, and some client-side
	lookups need full `read`). Audited against every Link field on Inquiry:
	inquiry_source (Customer), items.item (Item), marketer (Employee),
	inquiry_officer (User), company (Company), currency (Currency),
	referred_party_country (Country), plus contact_person/customer_address
	(Contact/Address, Permission Level 1 — Inquiry Manager only, matching
	who can even see those fields on the form).

	Grants are least-privilege per role, with one deliberate exception:
	  - Customer: select+read+create so a Customer can be found or quick-
	    created right from the Inquiry form (Inquiry Manager also gets write,
	    for corrections).
	  - Item: select+read+create for all three — Inquiry is frequently about
	    a brand-new product (see the NPD category), so frontline staff need
	    to be able to add a new Item inline, not just select existing ones.
	  - Employee: select+read+create+write for all three, matching the
	    standard "+ Create a New Employee" quick-create in the Marketer link
	    field's own dropdown, the same experience every other Link field in
	    this app has. This does expose standard Employee fields (not
	    Employee-sensitive payroll/salary data, which lives in separate
	    doctypes this app is never granted), which is a wider surface than
	    the original select-only design — accepted deliberately so the
	    create-a-Marketer flow matches core ERPNext's own UX instead of a
	    bespoke dialog. Whenever an Employee gets a `user_id` linked by
	    someone holding an Inquiry role, `auto_assign_marketer_role` (Employee
	    on_update, in utils.py) automatically grants that user the Marketer
	    role, since linking a user from this app's context only makes sense
	    if they're meant to become a Marketer.
	  - Company / Currency / Country / User: select+read for everyone who
	    can create an Inquiry — these are plain reference data, no
	    create/write needed.
	  - Contact / Address: select+read for Inquiry Manager only, matching
	    the Permission Level 1 restriction that already hides those fields
	    from Inquiry Officer/Marketer on the form itself.
	"""
	for role in ("Inquiry Officer", "Marketer", "Inquiry Manager"):
		_grant_custom_docperm("Employee", role, select=1, read=1, create=1, write=1)
		_grant_custom_docperm("Company", role, select=1, read=1)
		_grant_custom_docperm("Currency", role, select=1, read=1)
		_grant_custom_docperm("Country", role, select=1, read=1)
		_grant_custom_docperm("User", role, select=1, read=1)

	for role in ("Inquiry Officer", "Marketer"):
		_grant_custom_docperm("Customer", role, select=1, read=1, create=1)
		_grant_custom_docperm("Item", role, select=1, read=1, create=1)

	_grant_custom_docperm("Customer", "Inquiry Manager", select=1, read=1, write=1, create=1)
	_grant_custom_docperm("Item", "Inquiry Manager", select=1, read=1, create=1)
	_grant_custom_docperm("Contact", "Inquiry Manager", select=1, read=1)
	_grant_custom_docperm("Address", "Inquiry Manager", select=1, read=1)


# ---------------------------------------------------------------------------
# Commercial team (Commercial Manager / Commercial Officer): they take a
# submitted Inquiry, generate a Quotation from it, then a Request for
# Quotation to the suppliers of its items -- or, in parallel, a Sales Order
# and Sales Invoice straight to the customer, followed by an Indent (see
# setup_sales_pipeline_integration below). None of the core doctypes either
# flow touches (Quotation, Request for Quotation, Sales Order, Sales
# Invoice, Supplier, Supplier Quotation, plus Item/Company/Currency/
# Customer/Contact which they all need) are granted to any role in this app
# by default.
# ---------------------------------------------------------------------------


def grant_commercial_access():
	reference_data = (
		"Item",
		"Company",
		"Currency",
		"Customer",
		"Contact",
		"Purchase Order",
		"UOM",
		"Sales Taxes and Charges Template",
		"Purchase Taxes and Charges Template",
		"Terms and Conditions",
		"Address",
		"User",  # Commercial Manager needs this to search for a Commercial Officer to assign
	)
	for role in ("Commercial Officer", "Commercial Manager"):
		for doctype in reference_data:
			_grant_custom_docperm(doctype, role, select=1, read=1)

		_grant_custom_docperm("Supplier", role, select=1, read=1)

		# Multi-price management (see ensure_default_price_list /
		# sync_item_prices_from_* in utils.py): the automatic sync itself
		# runs with ignore_permissions=True, but the Commercial team still
		# needs to browse/adjust the auto-maintained Price Lists and Item
		# Prices directly from the desk.
		for doctype in ("Price List", "Item Price"):
			_grant_custom_docperm(
				doctype, role, select=1, read=1, write=1, create=1, report=1, export=1,
			)

		# Commercial Officer generates these; Commercial Manager gets the
		# same access for oversight (reassigning, reviewing, following up).
		# Sales Order / Sales Invoice are the parallel direct-sale pipeline
		# (Inquiry -> Sales Order -> Sales Invoice -> Indent) this same team
		# runs alongside the buying side.
		for doctype in ("Quotation", "Request for Quotation", "Sales Order", "Sales Invoice"):
			_grant_custom_docperm(
				doctype, role, select=1, read=1, write=1, create=1, submit=1, print=1, email=1,
				report=1, export=1,
			)

		# Supplier replies are usually submitted via the RFQ portal, but a
		# Commercial Officer can also log a phone/email reply manually.
		_grant_custom_docperm(
			"Supplier Quotation", role, select=1, read=1, write=1, create=1, print=1, email=1,
			report=1, export=1,
		)

	_grant_core_report_access()


def _grant_core_report_access():
	"""Item-wise Purchase History and Supplier Quotation Comparison are core
	ERPNext reports ("see the last buying — supplier, when, at what rate"
	and "a comparative statement when replies are received against an RFQ")
	-- both already exist, so just extend their own `roles` restriction
	list rather than rebuilding either report from scratch."""
	for report_name in ("Item-wise Purchase History", "Supplier Quotation Comparison"):
		if not frappe.db.exists("Report", report_name):
			continue
		report = frappe.get_doc("Report", report_name)
		existing_roles = {r.role for r in report.get("roles")}
		changed = False
		for role in ("Commercial Officer", "Commercial Manager"):
			if role not in existing_roles:
				report.append("roles", {"role": role})
				changed = True
		if changed:
			report.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Retired artifacts: estimated_value/currency were removed from Inquiry, so
# the chart/card built on them are cleaned up too. Safe to run every
# migrate — becomes a no-op once cleaned up on a given site.
# ---------------------------------------------------------------------------


def cleanup_retired_artifacts():
	retired_chart = "Estimated Value Trend"
	retired_card = "Open Pipeline Value"

	if frappe.db.exists("Dashboard", "Inquiry Dashboard"):
		dashboard = frappe.get_doc("Dashboard", "Inquiry Dashboard")
		changed = False

		charts = [c for c in dashboard.get("charts") if c.chart != retired_chart]
		if len(charts) != len(dashboard.get("charts")):
			dashboard.set("charts", charts)
			changed = True

		cards = [c for c in dashboard.get("cards") if c.card != retired_card]
		if len(cards) != len(dashboard.get("cards")):
			dashboard.set("cards", cards)
			changed = True

		if changed:
			dashboard.save(ignore_permissions=True)

	if frappe.db.exists("Workspace", "Smart App"):
		workspace = frappe.get_doc("Workspace", "Smart App")
		changed = False

		charts = [c for c in workspace.get("charts") if c.chart_name != retired_chart]
		if len(charts) != len(workspace.get("charts")):
			workspace.set("charts", charts)
			changed = True

		cards = [c for c in workspace.get("number_cards") if c.number_card_name != retired_card]
		if len(cards) != len(workspace.get("number_cards")):
			workspace.set("number_cards", cards)
			changed = True

		content = json.loads(workspace.content or "[]")
		new_content = [
			b
			for b in content
			if not (b.get("type") == "chart" and b.get("data", {}).get("chart_name") == retired_chart)
			and not (
				b.get("type") == "number_card" and b.get("data", {}).get("number_card_name") == retired_card
			)
		]
		if len(new_content) != len(content):
			workspace.content = json.dumps(new_content)
			changed = True

		if changed:
			workspace.save(ignore_permissions=True)

	if frappe.db.exists("Dashboard Chart", retired_chart):
		frappe.delete_doc("Dashboard Chart", retired_chart, ignore_permissions=True, force=True)
	if frappe.db.exists("Number Card", retired_card):
		frappe.delete_doc("Number Card", retired_card, ignore_permissions=True, force=True)


# ---------------------------------------------------------------------------
# Master data (all editable by Inquiry Manager from their respective lists)
# ---------------------------------------------------------------------------


def seed_master_data():
	_seed("Inquiry Shipment Mode", "mode_name", ["By Air", "By Sea"])
	_seed(
		"Inquiry Payment Mode",
		"mode_name",
		[
			"LC",
			"TT",
			"BC",
			"DA - 15 Days",
			"DA - 30 Days",
			"DA - 45 Days",
			"DA - 60 Days",
			"DA - 90 Days",
			"DA - Above 90 Days",
			# Also used by Indent's own "Payment Terms" field (see
			# setup_indent_masters) -- Indent's sample template quotes
			# "DP AT SIGHT", which this list didn't otherwise carry.
			"DP AT SIGHT",
			"LC AT SIGHT",
		],
	)
	_seed("Inquiry Category", "category_name", ["NPD - New Product Development", "Commercial"])

	incoterms = {
		"EXW": "Ex Works",
		"FOB": "Free On Board",
		"CIF": "Cost, Insurance and Freight",
		"CFR": "Cost and Freight",
		"CNF": "Cost and Freight (C&F)",
		"DDP": "Delivered Duty Paid",
		# Also used by Indent's own "Incoterm" field (see
		# setup_indent_masters) -- Indent's sample template quotes "CPT".
		"CPT": "Carriage Paid To",
	}
	for code, description in incoterms.items():
		if not frappe.db.exists("Inquiry Incoterm", code):
			frappe.get_doc(
				{"doctype": "Inquiry Incoterm", "incoterm_code": code, "description": description}
			).insert(ignore_permissions=True)


def _seed(doctype, fieldname, values):
	for value in values:
		if not frappe.db.exists(doctype, value):
			frappe.get_doc({"doctype": doctype, fieldname: value}).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Indent Trade Term: one manager-editable master list backing five of
# Indent's own "Terms & Conditions" grid fields (Port of Loading,
# Destination, Origin, Packing, Lead Time -- each just scoped to its own
# term_type via a Link query, see indent.js), the same way Inquiry Shipment
# Mode / Payment Mode / Incoterm / Category already back Inquiry's own
# dropdowns. Payment Terms and Incoterm reuse those existing master lists
# directly instead (see the "DP AT SIGHT" / "CPT" additions in
# seed_master_data) rather than duplicating them here.
# ---------------------------------------------------------------------------

INDENT_TRADE_TERM_SEED = {
	"Port of Loading": ["Any Chinese Airport", "Any Chinese Seaport"],
	"Destination": ["Lahore Airport, Pakistan", "Karachi Port, Pakistan"],
	"Origin": ["China", "India", "Pakistan"],
	"Packing": ["Export Standard"],
	"Lead Time": ["1-2 Weeks", "3-4 Weeks", "5-6 Weeks", "7-8 Weeks"],
}


def setup_indent_masters():
	if not frappe.db.exists("DocType", "Indent Trade Term"):
		return
	for term_type, values in INDENT_TRADE_TERM_SEED.items():
		for value in values:
			if not frappe.db.exists("Indent Trade Term", {"term_type": term_type, "value": value}):
				frappe.get_doc(
					{"doctype": "Indent Trade Term", "term_type": term_type, "value": value}
				).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


def setup_workflow():
	"""Reconciles states/transitions on every run (not just create-once), so
	a correction here (like the allow_edit unification below) self-heals on
	an already-created Workflow instead of being stuck with whatever was set
	the first time this ran."""
	_ensure_workflow_masters()

	all_roles = ["Inquiry Officer", "Marketer", "Inquiry Manager"]
	manager_only = ["Inquiry Manager"]

	# Every state uses the same "Inquiry User" umbrella role (auto-synced
	# onto anyone holding Inquiry Officer/Marketer/Inquiry Manager, and onto
	# Commercial Manager too -- see sync_inquiry_user_role in utils.py).
	# States used to lock down Converted/Lost/Closed to Inquiry Manager only,
	# but allow_edit applies to the WHOLE document, not just inquiry_status --
	# that blocked Commercial Manager from ever setting commercial_officer
	# once an Inquiry reached one of those statuses, which matters more than
	# the extra strictness was worth. DocPerm-level and Permission Level 1
	# restrictions still apply regardless of workflow state.
	edit_role_by_state = {state: "Inquiry User" for state in STATUSES}

	transitions = [
		("Open", "Send for Quotation", "Quotation", all_roles),
		("Open", "Mark as Replied", "Replied", all_roles),
		("Quotation", "Mark as Replied", "Replied", all_roles),
		("Open", "Mark as Lost", "Lost", all_roles),
		("Quotation", "Mark as Lost", "Lost", all_roles),
		("Replied", "Mark as Lost", "Lost", all_roles),
		("Replied", "Convert", "Converted", ["Marketer", "Inquiry Manager"]),
		("Converted", "Close", "Closed", manager_only),
		("Lost", "Close", "Closed", manager_only),
		("Closed", "Reopen", "Open", manager_only),
	]

	if frappe.db.exists("Workflow", "Inquiry Workflow"):
		workflow = frappe.get_doc("Workflow", "Inquiry Workflow")
	else:
		workflow = frappe.new_doc("Workflow")
		workflow.workflow_name = "Inquiry Workflow"
		workflow.document_type = "Inquiry"
		workflow.workflow_state_field = "inquiry_status"
		workflow.is_active = 1
		workflow.send_email_alert = 0

	changed = workflow.is_new()

	states_by_name = {s.state: s for s in workflow.get("states")}
	for state in STATUSES:
		if state in states_by_name:
			row = states_by_name[state]
			if row.allow_edit != edit_role_by_state[state] or row.doc_status != "0":
				row.allow_edit = edit_role_by_state[state]
				row.doc_status = "0"
				changed = True
		else:
			workflow.append("states", {"state": state, "doc_status": "0", "allow_edit": edit_role_by_state[state]})
			changed = True

	existing_transitions = {
		(t.state, t.action, t.next_state, t.allowed) for t in workflow.get("transitions")
	}
	for from_state, action, next_state, roles in transitions:
		for role in roles:
			key = (from_state, action, next_state, role)
			if key not in existing_transitions:
				workflow.append(
					"transitions",
					{
						"state": from_state,
						"action": action,
						"next_state": next_state,
						"allowed": role,
						"allow_self_approval": 1,
					},
				)
				changed = True

	if workflow.is_new():
		workflow.insert(ignore_permissions=True)
	elif changed:
		workflow.save(ignore_permissions=True)


def _ensure_workflow_masters():
	"""Workflow Document State.state / Workflow Transition.action(+state+next_state)
	are Links to Workflow State / Workflow Action Master respectively, and must
	exist before the Workflow document referencing them can be saved."""
	for state in STATUSES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": state}).insert(
				ignore_permissions=True
			)
	for action in WORKFLOW_ACTIONS:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{"doctype": "Workflow Action Master", "workflow_action_name": action}
			).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Kanban Board
# ---------------------------------------------------------------------------


def setup_kanban_board():
	if frappe.db.exists("Kanban Board", "Inquiry Status Board"):
		return

	board = frappe.new_doc("Kanban Board")
	board.kanban_board_name = "Inquiry Status Board"
	board.reference_doctype = "Inquiry"
	board.field_name = "inquiry_status"
	for status in STATUSES:
		board.append("columns", {"column_name": status})
	board.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Dashboard Charts
# ---------------------------------------------------------------------------


def setup_dashboard_charts():
	charts = [
		{
			"chart_name": "Inquiries by Status",
			"chart_type": "Group By",
			"group_by_type": "Count",
			"group_by_based_on": "inquiry_status",
			"type": "Donut",
		},
		{
			"chart_name": "Inquiries by Marketer",
			"chart_type": "Group By",
			"group_by_type": "Count",
			"group_by_based_on": "marketer",
			"type": "Bar",
		},
		{
			"chart_name": "Inquiries by Category",
			"chart_type": "Group By",
			"group_by_type": "Count",
			"group_by_based_on": "category",
			"type": "Pie",
		},
	]
	for c in charts:
		if frappe.db.exists("Dashboard Chart", c["chart_name"]):
			continue
		chart = frappe.new_doc("Dashboard Chart")
		chart.chart_name = c["chart_name"]
		chart.chart_type = c["chart_type"]
		chart.document_type = "Inquiry"
		chart.based_on = "inquiry_date"
		chart.value_based_on = c.get("value_based_on")
		chart.group_by_type = c.get("group_by_type")
		chart.group_by_based_on = c.get("group_by_based_on")
		chart.type = c["type"]
		chart.timeseries = c.get("timeseries", 0)
		chart.time_interval = c.get("time_interval", "Yearly")
		chart.timespan = c.get("timespan", "Last Year")
		chart.filters_json = "[]"
		chart.is_public = 1
		chart.module = MODULE
		chart.insert(ignore_permissions=True)


def setup_commercial_charts():
	"""Commercial-side charts -- currently just a breakdown of the supplier
	master (see smart_app.supplier_import) by country. Kept separate from
	setup_dashboard_charts because these are not Inquiry-based (no
	`based_on` date field), so they'd need special-casing in that loop."""
	if not frappe.db.exists("DocType", "Supplier"):
		return
	if frappe.db.exists("Dashboard Chart", "Suppliers by Country"):
		return
	chart = frappe.new_doc("Dashboard Chart")
	chart.chart_name = "Suppliers by Country"
	chart.chart_type = "Group By"
	chart.document_type = "Supplier"
	chart.group_by_type = "Count"
	chart.group_by_based_on = "country"
	chart.type = "Donut"
	chart.filters_json = json.dumps([["Supplier", "disabled", "=", 0]])
	chart.is_public = 1
	chart.module = MODULE
	chart.insert(ignore_permissions=True)

	if frappe.db.exists("DocType", "Indent") and not frappe.db.exists("Dashboard Chart", "Indents by Status"):
		indent_chart = frappe.new_doc("Dashboard Chart")
		indent_chart.chart_name = "Indents by Status"
		indent_chart.chart_type = "Group By"
		indent_chart.document_type = "Indent"
		indent_chart.group_by_type = "Count"
		indent_chart.group_by_based_on = "indent_status"
		indent_chart.type = "Donut"
		indent_chart.filters_json = json.dumps([["Indent", "docstatus", "!=", 2]])
		indent_chart.is_public = 1
		indent_chart.module = MODULE
		indent_chart.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Number Cards (KPIs)
# ---------------------------------------------------------------------------


def setup_number_cards():
	cards = [
		{
			"label": "Open Inquiries",
			"function": "Count",
			"filters_json": [["Inquiry", "inquiry_status", "=", "Open"]],
		},
		{
			"label": "Converted Inquiries",
			"function": "Count",
			"filters_json": [["Inquiry", "inquiry_status", "=", "Converted"]],
		},
		{
			"label": "Lost Inquiries",
			"function": "Count",
			"filters_json": [["Inquiry", "inquiry_status", "=", "Lost"]],
		},
	]
	for c in cards:
		_create_number_card(c["label"], c["function"], c["filters_json"])


def _create_number_card(label, function, filters, aggregate_function_based_on=None, document_type="Inquiry"):
	if frappe.db.exists("Number Card", label):
		return
	card = frappe.new_doc("Number Card")
	card.label = label
	card.document_type = document_type
	card.type = "Document Type"
	card.function = function
	card.aggregate_function_based_on = aggregate_function_based_on
	card.filters_json = json.dumps(filters)
	card.is_public = 1
	card.show_percentage_stats = 1
	card.stats_time_interval = "Monthly"
	card.module = MODULE
	card.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Commercial overview: how a Commercial Manager sees total/assigned/
# unassigned submitted Inquiries, and tracks each one through the Quotation
# / RFQ pipeline.
# ---------------------------------------------------------------------------


def setup_commercial_overview():
	_create_number_card(
		"Submitted Inquiries", "Count", [["Inquiry", "docstatus", "=", 1]]
	)
	_create_number_card(
		"Unassigned Inquiries",
		"Count",
		[["Inquiry", "docstatus", "=", 1], ["Inquiry", "commercial_officer", "is", "not set"]],
	)
	_create_number_card(
		"Assigned Inquiries",
		"Count",
		[["Inquiry", "docstatus", "=", 1], ["Inquiry", "commercial_officer", "is", "set"]],
	)
	# The supplier master the Commercial team sends RFQs to (see
	# smart_app.supplier_import) -- surfaced here so its size is visible
	# alongside the pipeline it feeds.
	if frappe.db.exists("DocType", "Supplier"):
		_create_number_card(
			"Total Suppliers", "Count", [["Supplier", "disabled", "=", 0]], document_type="Supplier"
		)
	# Submitted Indents not yet Closed -- the Commercial team's own
	# "still waiting on payment" queue.
	if frappe.db.exists("DocType", "Indent"):
		_create_number_card(
			"Open Indents",
			"Count",
			[["Indent", "docstatus", "=", 1], ["Indent", "indent_status", "!=", "Closed"]],
			document_type="Indent",
		)

	# Only submitted Inquiries belong on this board -- otherwise every draft
	# (still "Unassigned" by default before it's even handed to Commercial)
	# would clutter it too.
	commercial_pipeline_filters = json.dumps([["Inquiry", "docstatus", "=", 1]])
	if frappe.db.exists("Kanban Board", "Commercial Pipeline"):
		board = frappe.get_doc("Kanban Board", "Commercial Pipeline")
		if board.filters != commercial_pipeline_filters:
			board.filters = commercial_pipeline_filters
			board.save(ignore_permissions=True)
	else:
		board = frappe.new_doc("Kanban Board")
		board.kanban_board_name = "Commercial Pipeline"
		board.reference_doctype = "Inquiry"
		board.field_name = "commercial_status"
		board.filters = commercial_pipeline_filters
		for status in COMMERCIAL_STATUSES:
			board.append("columns", {"column_name": status})
		board.insert(ignore_permissions=True)

	_create_query_report(
		"Commercial Assignment Overview",
		"""
		select
			i.name as "Inquiry:Link/Inquiry:130",
			i.customer_name as "Customer:Data:180",
			i.category as "Category:Link/Inquiry Category:150",
			ifnull(i.commercial_officer, '') as "Commercial Officer:Link/User:200",
			i.commercial_status as "Commercial Status:Data:150",
			i.inquiry_date as "Inquiry Date:Date:110"
		from `tabInquiry` i
		where i.docstatus = 1
		order by i.commercial_officer is null desc, i.inquiry_date desc
		""".strip(),
		roles=("Commercial Manager", "Commercial Officer", "System Manager"),
	)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------


def setup_dashboard():
	if frappe.db.exists("Dashboard", "Inquiry Dashboard"):
		return

	dashboard = frappe.new_doc("Dashboard")
	dashboard.dashboard_name = "Inquiry Dashboard"
	dashboard.module = MODULE
	dashboard.is_default = 0
	for chart in CHART_NAMES:
		dashboard.append("charts", {"chart": chart})
	for card in CARD_NAMES:
		dashboard.append("cards", {"card": card})
	dashboard.insert(ignore_permissions=True)


def setup_commercial_dashboard():
	"""A Commercial-team counterpart to the Inquiry Dashboard: the three
	submitted/assigned/unassigned KPIs, the supplier-master count, and the
	Suppliers-by-Country chart, on one page linked from the workspace's
	Commercial Team section."""
	if frappe.db.exists("Dashboard", "Commercial Dashboard"):
		return

	dashboard = frappe.new_doc("Dashboard")
	dashboard.dashboard_name = "Commercial Dashboard"
	dashboard.module = MODULE
	dashboard.is_default = 0
	for chart in COMMERCIAL_CHART_NAMES:
		if frappe.db.exists("Dashboard Chart", chart):
			dashboard.append("charts", {"chart": chart})
	for card in COMMERCIAL_CARD_NAMES:
		if frappe.db.exists("Number Card", card):
			dashboard.append("cards", {"card": card})
	dashboard.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Reports
# ---------------------------------------------------------------------------


def setup_reports():
	_create_query_report(
		"Marketer Performance",
		"""
		select
			e.employee_name as "Marketer:Data:220",
			count(i.name) as "Total Inquiries:Int:130",
			sum(case when i.inquiry_status = 'Converted' then 1 else 0 end) as "Converted:Int:110",
			sum(case when i.inquiry_status = 'Lost' then 1 else 0 end) as "Lost:Int:100",
			sum(case when i.inquiry_status not in ('Converted', 'Lost', 'Closed') then 1 else 0 end) as "In Progress:Int:120"
		from `tabInquiry` i
		left join `tabEmployee` e on e.name = i.marketer
		group by i.marketer
		order by count(i.name) desc
		""".strip(),
	)

	_create_query_report(
		"Inquiry Status Summary",
		"""
		select
			i.inquiry_status as "Status:Data:130",
			ic.category_name as "Category:Data:220",
			count(i.name) as "Total Inquiries:Int:130"
		from `tabInquiry` i
		left join `tabInquiry Category` ic on ic.name = i.category
		group by i.inquiry_status, i.category
		order by field(i.inquiry_status, 'Open', 'Quotation', 'Replied', 'Converted', 'Lost', 'Closed')
		""".strip(),
	)

	_create_query_report(
		"Indent Register",
		"""
		select
			ind.name as "Indent No:Link/Indent:130",
			ind.indent_date as "Date:Date:100",
			ind.customer_name as "Buyer:Data:200",
			ind.supplier_name as "Seller:Data:200",
			ind.currency as "Currency:Link/Currency:90",
			ind.total_amount as "Total Value:Currency/currency:130",
			ind.indent_status as "Status:Data:110"
		from `tabIndent` ind
		where ind.docstatus != 2
		order by ind.indent_date desc
		""".strip(),
		roles=("Commercial Manager", "Commercial Officer", "System Manager"),
		ref_doctype="Indent",
	)


def _create_query_report(
	name,
	query,
	roles=("Inquiry Manager", "Inquiry Officer", "Marketer", "System Manager"),
	ref_doctype="Inquiry",
):
	"""Reconciles the query/roles on every run, not just on first create, so
	an updated SQL definition (e.g. dropping a removed field) self-heals on
	the next migrate instead of leaving the stale version in place."""
	if frappe.db.exists("Report", name):
		report = frappe.get_doc("Report", name)
	else:
		report = frappe.new_doc("Report")
		report.report_name = name
		report.ref_doctype = ref_doctype
		report.report_type = "Query Report"
		report.is_standard = "No"
		report.module = MODULE

	changed = report.is_new() or report.query != query
	report.query = query

	existing_roles = {r.role for r in report.get("roles")}
	for role in roles:
		if role not in existing_roles:
			report.append("roles", {"role": role})
			changed = True

	if report.is_new():
		report.insert(ignore_permissions=True)
	elif changed:
		report.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Commercial pipeline integration on core doctypes: Quotation's own
# "Get Items From" > Inquiry (only Inquiries assigned to the current
# Commercial Officer are offered), a "Create Request for Quotation" button
# that aggregates every supplier of every item in the Quotation (Item's own
# "Supplier Items" table — an Item commonly has several, trader and
# manufacturer alike, and all of them are pulled in), plus traceability
# fields back to the source Inquiry. Both Quotation and Request for
# Quotation are core ERPNext doctypes, so this is done non-invasively via
# Custom Fields and a Client Script rather than editing ERPNext's own files.
# ---------------------------------------------------------------------------

QUOTATION_CLIENT_SCRIPT_JS = """
frappe.ui.form.on("Quotation", {
	refresh: function (frm) {
		if (frm.doc.docstatus === 0 && frappe.model.can_read("Inquiry")) {
			frm.add_custom_button(
				__("Inquiry"),
				function () {
					erpnext.utils.map_current_doc({
						method: "smart_app.smart_app.doctype.inquiry.inquiry.make_quotation",
						source_doctype: "Inquiry",
						target: frm,
						setters: [
							{
								label: "Customer",
								fieldname: "inquiry_source",
								fieldtype: "Link",
								options: "Customer",
								default: frm.doc.party_name || undefined,
							},
						],
						get_query_filters: {
							commercial_officer: frappe.session.user,
							docstatus: 1,
						},
					});
				},
				__("Get Items From"),
				"btn-default"
			);
		}

		if (!frm.is_new() && frm.doc.items && frm.doc.items.length && frappe.model.can_create("Request for Quotation")) {
			frm.add_custom_button(__("Request for Quotation"), function () {
				frappe.call({
					method: "smart_app.smart_app.doctype.inquiry.inquiry.create_request_for_quotation",
					args: { quotation_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Preparing Request for Quotation..."),
					callback: function (r) {
						if (r.message) {
							frappe.set_route("Form", "Request for Quotation", r.message);
						}
					},
				});
			});
		}
	},
});
""".strip()

# The draft RFQ that create_request_for_quotation (inquiry.py) builds already
# carries every item and every supplier of every item, plus the corporate
# email_template wired in via set_data_for_supplier -- all a Commercial
# Officer needs to do is delete any supplier rows they don't want (plain
# grid-row delete, already available on any draft with write access) and
# send it. Submitting an RFQ already triggers ERPNext's own
# send_to_supplier() from its on_submit -- so "Submit & Send to Suppliers"
# is one action, not submit-then-hunt-for-the-separate-native-button.
RFQ_CLIENT_SCRIPT_JS = """
frappe.ui.form.on("Request for Quotation", {
	refresh: function (frm) {
		// The reverse direction of the "Request for Quotation" button on
		// Quotation (see QUOTATION_CLIENT_SCRIPT_JS) -- that one goes
		// Quotation -> new RFQ; this one lets someone start from a blank
		// RFQ and pull items/suppliers from an existing Quotation instead,
		// so the two doctypes are connected both ways. Deliberately a plain
		// Link prompt (filtered server-side to Quotations owned by the
		// current user, unless they're a Commercial Manager/System
		// Manager) + explicit frm.set_value/clear_table/add_child, not
		// erpnext.utils.map_current_doc -- that mechanism's
		// MultiSelectDialog + generic mapper pipeline is built around
		// picking one-or-more *rows* to pull into an existing table, not
		// cloning one whole source document's data onto a blank one, and
		// didn't suit this direction well.
		if (frm.is_new() && frappe.model.can_read("Quotation")) {
			frm.add_custom_button(
				__("Quotation"),
				function () {
					frappe.prompt(
						[
							{
								fieldname: "quotation",
								label: __("Quotation"),
								fieldtype: "Link",
								options: "Quotation",
								reqd: 1,
								get_query: function () {
									return {
										query: "smart_app.smart_app.doctype.inquiry.inquiry.get_quotations_for_rfq",
									};
								},
							},
						],
						function (values) {
							frappe.call({
								method: "smart_app.smart_app.doctype.inquiry.inquiry.get_request_for_quotation_data",
								args: { quotation_name: values.quotation },
								freeze: true,
								freeze_message: __("Fetching items and suppliers..."),
								callback: function (r) {
									if (!r.message) return;
									const data = r.message;

									frm.set_value("company", data.company);
									frm.set_value("transaction_date", data.transaction_date);
									frm.set_value("quotation", data.quotation);
									frm.set_value("inquiry", data.inquiry);
									frm.set_value("email_template", data.email_template);
									frm.set_value("message_for_supplier", data.message_for_supplier);
									frm.set_value("mfs_html", data.mfs_html);
									frm.set_value("use_html", data.use_html);
									frm.set_value("subject", data.subject);

									frm.clear_table("items");
									(data.items || []).forEach(function (row) {
										frm.add_child("items", row);
									});

									frm.clear_table("suppliers");
									(data.suppliers || []).forEach(function (row) {
										frm.add_child("suppliers", row);
									});

									frm.refresh_fields();
									frm.dirty();
								},
							});
						},
						__("Get Items From Quotation"),
						__("Fetch")
					);
				},
				__("Get Items From"),
				"btn-default"
			);
		}

		if (!frm.is_new() && frm.doc.docstatus === 0 && frm.doc.suppliers && frm.doc.suppliers.length) {
			frm.add_custom_button(__("Submit & Send to Suppliers"), function () {
				frappe.confirm(
					__("This will submit the RFQ and email every supplier listed below. Continue?"),
					function () {
						frm.savesubmit();
					}
				);
			}).addClass("btn-primary");
		}
	},
});
""".strip()


def setup_quotation_integration():
	if frappe.db.exists("DocType", "Quotation"):
		_add_custom_field("Quotation", "inquiry", "Inquiry", "Inquiry", insert_after="party_name")
		_upsert_client_script(
			"Inquiry - Commercial Pipeline (Quotation)", "Quotation", QUOTATION_CLIENT_SCRIPT_JS
		)

	if frappe.db.exists("DocType", "Request for Quotation"):
		_add_custom_field(
			"Request for Quotation", "inquiry", "Inquiry", "Inquiry", insert_after="company"
		)
		# Traces this RFQ back to the specific Quotation it was generated
		# from -- distinct from `inquiry` above, which traces the whole
		# chain back further to the originating Inquiry (if any). An RFQ
		# built from a Quotation that didn't itself come from an Inquiry
		# (e.g. started directly via the reverse "Get Items From Quotation"
		# button below) will have `quotation` set but `inquiry` blank.
		_add_custom_field(
			"Request for Quotation", "quotation", "Quotation", "Quotation", insert_after="inquiry"
		)
		# Neither field should be hand-edited directly -- the only supported
		# way to set them is the "Get Items From > Quotation" button (see
		# RFQ_CLIENT_SCRIPT_JS), which is also the only place `quotation`
		# ever gets a value worth showing. `inquiry` stays fully hidden --
		# it's internal chain-tracing (RFQ -> Quotation -> Inquiry), not
		# something a Commercial Officer needs to see on this form; `quotation`
		# stays visible but read-only, so it's there as confirmation once set.
		_set_property_setter("Request for Quotation", "quotation", "read_only", "1", "Check")
		_set_property_setter("Request for Quotation", "inquiry", "hidden", "1", "Check")
		_upsert_client_script(
			"Inquiry - Commercial Pipeline (Request for Quotation)",
			"Request for Quotation",
			RFQ_CLIENT_SCRIPT_JS,
		)


# ---------------------------------------------------------------------------
# The parallel direct-sale pipeline: Inquiry -> Quotation -> Sales Order ->
# Sales Invoice -> Indent, run by the same Commercial team alongside the
# Quotation -> RFQ -> Supplier Quotation buying pipeline above (both start
# from the same Quotation -- this isn't a fork of the Inquiry, it's a fork
# of what happens *after* a Quotation exists).
#
# Sales Order is deliberately built from Quotation, not Inquiry directly --
# core ERPNext already provides this completely natively, both directions
# (Quotation's own "Create > Sales Order" button, and the reverse "Get Items
# From > Quotation" on a blank Sales Order, both calling erpnext.selling.
# doctype.quotation.quotation.make_sales_order) -- so there's nothing to
# customise here at all, only the permission grant (grant_commercial_access)
# for a Commercial Officer/Manager to use either one. Sales Order -> Sales
# Invoice is equally native. Only the "Create > Indent" button once a Sales
# Invoice is submitted is this app's own.
# ---------------------------------------------------------------------------

# create_indent_from_sales_invoice (indent.py) builds a draft Indent with
# every item carried over -- a Commercial Officer still has to pick which
# Supplier is actually fulfilling the shipment (which fetches its bank
# details, see setup_supplier_bank_fields) and fill in the trade-terms grid,
# so this deliberately doesn't try to do more than hand off the item list.
SALES_INVOICE_CLIENT_SCRIPT_JS = """
frappe.ui.form.on("Sales Invoice", {
	refresh: function (frm) {
		if (
			frm.doc.docstatus === 1 &&
			frm.doc.items &&
			frm.doc.items.length &&
			frappe.model.can_create("Indent")
		) {
			frm.add_custom_button(__("Indent"), function () {
				frappe.call({
					method: "smart_app.smart_app.doctype.indent.indent.create_indent_from_sales_invoice",
					args: { sales_invoice_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Preparing Indent..."),
					callback: function (r) {
						if (r.message) {
							frappe.set_route("Form", "Indent", r.message);
						}
					},
				});
			}, __("Create"));
		}
	},
});
""".strip()


def setup_sales_pipeline_integration():
	if frappe.db.exists("DocType", "Sales Order"):
		# Hidden -- internal chain-tracing (Sales Order -> Quotation ->
		# Inquiry), same treatment as Request for Quotation's own `inquiry`
		# field. Best-effort filled in by
		# smart_app.smart_app.utils.set_inquiry_from_quotation (Sales Order
		# validate) from whichever Quotation this Sales Order was created
		# from (core ERPNext's native mapper, either direction -- see the
		# module docstring above), since that mapper has no idea about a
		# Custom Field we added after the fact.
		_add_custom_field("Sales Order", "inquiry", "Inquiry", "Inquiry", insert_after="customer")
		_set_property_setter("Sales Order", "inquiry", "hidden", "1", "Check")
		# Self-healing cleanup: an earlier version of this app built Sales
		# Order directly from Inquiry (its own Client Script + a
		# make_sales_order mapper) instead of via Quotation. Remove that
		# script from any site that already migrated with it, so a stale
		# "Get Items From > Inquiry" button doesn't linger on Sales Order.
		if frappe.db.exists("Client Script", "Inquiry - Commercial Pipeline (Sales Order)"):
			frappe.delete_doc(
				"Client Script", "Inquiry - Commercial Pipeline (Sales Order)", ignore_permissions=True
			)

	if frappe.db.exists("DocType", "Sales Invoice"):
		# Hidden -- internal chain-tracing (Sales Invoice -> Sales Order ->
		# Quotation -> Inquiry), same treatment as above. Best-effort filled
		# in by smart_app.smart_app.utils.set_inquiry_from_sales_order (Sales
		# Invoice validate), since core ERPNext's own Sales Order -> Sales
		# Invoice mapper has a fixed field_map that won't carry a Custom
		# Field over on its own.
		_add_custom_field("Sales Invoice", "inquiry", "Inquiry", "Inquiry", insert_after="customer")
		_set_property_setter("Sales Invoice", "inquiry", "hidden", "1", "Check")
		_upsert_client_script(
			"Inquiry - Commercial Pipeline (Sales Invoice)", "Sales Invoice", SALES_INVOICE_CLIENT_SCRIPT_JS
		)


def _add_custom_field(dt, fieldname, label, options, insert_after, fieldtype="Link"):
	name = f"{dt}-{fieldname}"
	if frappe.db.exists("Custom Field", name):
		return
	frappe.get_doc(
		{
			"doctype": "Custom Field",
			"dt": dt,
			"fieldname": fieldname,
			"label": label,
			"fieldtype": fieldtype,
			"options": options,
			"insert_after": insert_after,
			"allow_on_submit": 1,
		}
	).insert(ignore_permissions=True)


def _upsert_client_script(name, dt, script_body, view="Form"):
	if frappe.db.exists("Client Script", name):
		script = frappe.get_doc("Client Script", name)
	else:
		script = frappe.new_doc("Client Script")
		script.name = name
		script.dt = dt
		script.view = view

	changed = script.is_new() or script.script != script_body or not script.enabled
	script.script = script_body
	script.enabled = 1

	if script.is_new():
		script.insert(ignore_permissions=True)
	elif changed:
		script.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Item master columns on every item table in the trading pipeline: UOM
# (exists everywhere already, just hidden from the grid by default) and
# this site's own custom_pharmacopeia / custom_item_grade fields on Item
# (which don't exist on any of these core child tables at all).
# ---------------------------------------------------------------------------

# child doctype -> its own Link-to-Item fieldname (Inquiry Item uses "item";
# every core ERPNext item table uses "item_code")
ITEM_MASTER_COLUMN_DOCTYPES = {
	"Quotation Item": "item_code",
	"Request for Quotation Item": "item_code",
	"Supplier Quotation Item": "item_code",
}

# Only these two actually carry a rate/amount at all -- Request for Quotation
# Item has neither field: an RFQ is the request sent out *before* any
# supplier has quoted a price, so there's nothing to show yet.
RATE_VALUE_COLUMN_DOCTYPES = ("Quotation Item", "Supplier Quotation Item")


def setup_item_master_columns():
	for dt, item_fieldname in ITEM_MASTER_COLUMN_DOCTYPES.items():
		if not frappe.db.exists("DocType", dt):
			continue

		_set_property_setter(dt, "uom", "in_list_view", "1", "Check")

		# Every one of these doctypes' native in_list_view fields (item_code,
		# qty, and -- for the two below -- rate/amount) already summed close
		# to a full-width grid row on their own; inserting uom/pharmacopeia/
		# grade as additional in_list_view columns without shrinking anything
		# pushed rate/amount (later in field_order) out of the visible grid
		# entirely, which is exactly what looked like "rate and value aren't
		# shown". Tightening these three to single-width columns is what
		# frees enough room for rate/amount to stay on-screen.
		_set_property_setter(dt, "item_code", "columns", "2", "Int")
		_set_property_setter(dt, "qty", "columns", "1", "Int")
		_set_property_setter(dt, "uom", "columns", "1", "Int")

		for fieldname, label, insert_after in (
			("custom_pharmacopeia", "Pharmacopeia", item_fieldname),
			("custom_item_grade", "Item Grade", "custom_pharmacopeia"),
		):
			name = f"{dt}-{fieldname}"
			if frappe.db.exists("Custom Field", name):
				cf = frappe.get_doc("Custom Field", name)
				if not cf.in_list_view or cf.columns != 1:
					cf.in_list_view = 1
					cf.columns = 1
					cf.save(ignore_permissions=True)
				continue
			frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": dt,
					"fieldname": fieldname,
					"label": label,
					"fieldtype": "Data",
					"fetch_from": f"{item_fieldname}.{fieldname}",
					"insert_after": insert_after,
					"in_list_view": 1,
					"columns": 1,
					"read_only": 1,
					"allow_on_submit": 1,
				}
			).insert(ignore_permissions=True)

	for dt in RATE_VALUE_COLUMN_DOCTYPES:
		if not frappe.db.exists("DocType", dt):
			continue
		_set_property_setter(dt, "rate", "in_list_view", "1", "Check")
		_set_property_setter(dt, "rate", "columns", "2", "Int")
		_set_property_setter(dt, "amount", "in_list_view", "1", "Check")
		_set_property_setter(dt, "amount", "columns", "2", "Int")


def _set_property_setter(doctype, fieldname, property_name, value, property_type):
	"""Property Setter's own autoname is "{doc_type}-{field_name}-{property}"
	(confirmed against its controller), and its own validate() deletes any
	pre-existing conflicting one before inserting -- so this just needs a
	cheap guard against re-writing an already-correct value on every run."""
	name = f"{doctype}-{fieldname}-{property_name}"
	if frappe.db.get_value("Property Setter", name, "value") == value:
		return
	frappe.get_doc(
		{
			"doctype": "Property Setter",
			"doctype_or_field": "DocField",
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property_name,
			"value": value,
			"property_type": property_type,
		}
	).insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Multi-supplier management on Item: the native "Supplier Items" table
# (Item Supplier child doctype) only ever carried `supplier` +
# `supplier_part_no` -- enough to *list* several suppliers per Item, but no
# way to tell a trader apart from a manufacturer, or mark which one is the
# preferred source when several are on file. Both matter in practice once
# create_request_for_quotation (inquiry.py) aggregates every supplier on an
# Item's row for an RFQ blast to all of them at once.
# ---------------------------------------------------------------------------

# fieldname, label, fieldtype, grid column width, extra DocField kwargs
ITEM_SUPPLIER_CUSTOM_FIELDS = (
	(
		"supplier_type",
		"Supplier Type",
		"Select",
		2,
		{"options": "Manufacturer\nTrader\nDistributor\nOther"},
	),
	(
		"is_preferred_supplier",
		"Preferred",
		"Check",
		1,
		{},
	),
)


def setup_item_supplier_customization():
	if not frappe.db.exists("DocType", "Item Supplier"):
		return

	insert_after = "supplier_part_no"
	for fieldname, label, fieldtype, columns, extra in ITEM_SUPPLIER_CUSTOM_FIELDS:
		name = f"Item Supplier-{fieldname}"
		field_dict = {
			"doctype": "Custom Field",
			"dt": "Item Supplier",
			"fieldname": fieldname,
			"label": label,
			"fieldtype": fieldtype,
			"insert_after": insert_after,
			"in_list_view": 1,
			"columns": columns,
			**extra,
		}

		if frappe.db.exists("Custom Field", name):
			cf = frappe.get_doc("Custom Field", name)
			changed = False
			for key, value in field_dict.items():
				if key == "doctype":
					continue
				if cf.get(key) != value:
					cf.set(key, value)
					changed = True
			if changed:
				cf.save(ignore_permissions=True)
		else:
			frappe.get_doc(field_dict).insert(ignore_permissions=True)

		insert_after = fieldname


# ---------------------------------------------------------------------------
# Structured bank details + seller address on Supplier, for Indent -- "SELLER"
# and "BANK DETAILS" fetch straight from whichever Supplier is picked as an
# Indent's own seller (see indent.json). smart_app.supplier_import already
# writes a pipe-delimited "Key: Value | Key: Value" summary into the native
# `supplier_details` field for all 345 imported suppliers; these are the
# structured fields Indent actually reads, backfilled once from that same
# text (see backfill_supplier_bank_details) and self-healing from then on
# (see ensure_supplier_bank_details, utils.py, Supplier.validate) for anyone
# who keeps typing new suppliers' details the same way. They're always
# plain editable fields too -- filling them in directly for a brand-new
# Supplier is the more robust path going forward, not a requirement to keep
# writing that exact text shape.
# ---------------------------------------------------------------------------

SUPPLIER_BANK_FIELDS = (
	# fieldname, label, fieldtype, insert_after
	("indent_bank_details_section", "Bank Details (for Indent)", "Section Break", "supplier_details"),
	("bank_beneficiary_name", "Beneficiary Name", "Data", "indent_bank_details_section"),
	("bank_name", "Bank Name", "Data", "bank_beneficiary_name"),
	("column_break_indent_bank", None, "Column Break", "bank_name"),
	("bank_account_no", "Account No", "Data", "column_break_indent_bank"),
	("swift_code", "SWIFT Code", "Data", "bank_account_no"),
	("bank_address", "Bank Address", "Small Text", "swift_code"),
	("seller_address_display", "Address (for Indent)", "Small Text", "bank_address"),
)


def setup_supplier_bank_fields():
	if not frappe.db.exists("DocType", "Supplier"):
		return
	for fieldname, label, fieldtype, insert_after in SUPPLIER_BANK_FIELDS:
		_add_custom_field("Supplier", fieldname, label, None, insert_after, fieldtype=fieldtype)


# ---------------------------------------------------------------------------
# Print Format
# ---------------------------------------------------------------------------


def setup_print_format():
	html = """
<div class="print-format">
	<h2>{{ doc.name }}</h2>
	<table class="table table-bordered" style="width: 100%">
		<tr>
			<td style="width: 25%"><b>Date</b></td><td style="width: 25%">{{ frappe.utils.formatdate(doc.inquiry_date) }}</td>
			<td style="width: 25%"><b>Status</b></td><td style="width: 25%">{{ doc.inquiry_status }}</td>
		</tr>
		<tr>
			<td><b>Customer</b></td><td>{{ doc.customer_name or "" }}</td>
			<td><b>Category</b></td><td>{{ doc.category or "" }}</td>
		</tr>
		<tr>
			<td><b>Mode of Shipment</b></td><td>{{ doc.shipment_mode or "" }}</td>
			<td><b>Mode of Payment</b></td><td>{{ doc.payment_mode or "" }}</td>
		</tr>
		<tr>
			<td><b>Incoterm</b></td><td>{{ doc.incoterm or "" }}</td>
			<td><b>Commercial Officer</b></td><td>{{ doc.commercial_officer or "" }}</td>
		</tr>
		<tr>
			<td><b>Commercial Status</b></td><td>{{ doc.commercial_status or "" }}</td>
			<td></td><td></td>
		</tr>
	</table>
	<h4>Items</h4>
	<table class="table table-bordered" style="width: 100%">
		<thead>
			<tr><th style="width: 10%">#</th><th>Item</th><th style="width: 20%">Quantity</th></tr>
		</thead>
		<tbody>
			{% for row in doc.items %}
			<tr>
				<td>{{ row.idx }}</td>
				<td>{{ row.item_name or row.item }}</td>
				<td>{{ row.qty }}</td>
			</tr>
			{% endfor %}
		</tbody>
	</table>
	{% if doc.notes %}
	<h4>Notes</h4>
	<p>{{ doc.notes }}</p>
	{% endif %}
</div>
""".strip()

	if frappe.db.exists("Print Format", "Inquiry Standard"):
		pf = frappe.get_doc("Print Format", "Inquiry Standard")
	else:
		pf = frappe.new_doc("Print Format")
		pf.name = "Inquiry Standard"
		pf.doc_type = "Inquiry"
		pf.module = MODULE
		pf.print_format_type = "Jinja"
		pf.standard = "No"
		pf.disabled = 0

	# custom_format=1 is what actually tells Frappe to render `html` as a
	# Jinja template at all -- without it, print_format_type="Jinja" alone
	# is ignored and Frappe falls back to auto-generating the print layout
	# from format_data (which this print format never sets), silently
	# discarding everything written into `html` below. Included in the
	# `changed` check so a site that already migrated before this was
	# caught gets self-healed on the next one.
	changed = pf.is_new() or pf.html != html or not pf.custom_format
	pf.html = html
	pf.custom_format = 1

	if pf.is_new():
		pf.insert(ignore_permissions=True)
	elif changed:
		pf.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Indent Print Format -- the same content and section structure as the
# firm's own indent_template.pdf (seller/buyer, item table, trade-terms
# grid, bank details, the three clause blocks, shipping marks, signatures),
# restyled as a proper corporate document: one type scale, one border/
# color system (a single accent colour used for section bars and the
# totals rule), sentence case on the clause paragraphs instead of a wall of
# capitals -- with the handful of terms the template itself bolds (30 days,
# 85% shelf-life, "OUR") kept bold -- and comma-formatted currency values.
# The letterhead/logo/NTN header at the top of that PDF is left to the
# site's own Letter Head, not baked in here.
#
# The FOR BANKER / FOR BUYER / FOR SHIPPER clauses and the Shipping Marks
# wording are still hardcoded, not doc fields -- the whole point (see the
# task this was built for) is that they read identically on every single
# Indent; only {{ doc.customer_name }} varies in the Shipping Marks block,
# exactly as in the source template. Set as Indent's `default_print_format`
# (indent.json) so it's what opens automatically on Print/PDF.
# ---------------------------------------------------------------------------


def setup_indent_print_format():
	html = r"""
<div class="indent-print">
<style>
	.indent-print {
		font-family: "Helvetica Neue", Helvetica, Arial, sans-serif;
		font-size: 10.5px;
		line-height: 1.55;
		color: #1e293b;
	}
	.indent-print b, .indent-print strong { color: #0f172a; }

	.indent-print .doc-title {
		text-align: center;
		font-size: 21px;
		font-weight: 700;
		letter-spacing: 4px;
		color: #0f172a;
		margin: 0 0 16px;
		padding-bottom: 10px;
		border-bottom: 2.5px solid #0f6e51;
	}

	.indent-print table {
		border-collapse: collapse;
		width: 100%;
		margin-bottom: 12px;
	}
	.indent-print th, .indent-print td {
		border: 1px solid #d4dae2;
		padding: 6px 9px;
		vertical-align: top;
	}

	/* Section header bar -- one per block (Seller/Buyer, Items, Terms, etc). */
	.indent-print .section-head {
		background: #0f6e51;
		color: #ffffff;
		font-size: 9.5px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 1px;
		padding: 5px 9px;
		border: 1px solid #0f6e51;
	}

	.indent-print .label-cell {
		font-weight: 600;
		width: 22%;
		background: #f8fafb;
		color: #55606e;
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}
	.indent-print .party-name { font-size: 11.5px; font-weight: 700; }
	.indent-print .party-address { color: #475569; }

	.indent-print .items-table th {
		background: #f8fafb;
		color: #55606e;
		font-size: 9px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		text-align: left;
	}
	.indent-print .items-table td.num, .indent-print .items-table th.num { text-align: right; }
	.indent-print .items-table .item-desc { color: #64748b; font-size: 9.7px; font-style: italic; }
	.indent-print .total-row td {
		border-top: 1.5px solid #0f6e51;
		background: #f4faf7;
		font-weight: 700;
		font-size: 11px;
	}

	.indent-print .clause-label {
		text-align: center;
		font-weight: 700;
		font-size: 9.5px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: #0f6e51;
		background: #f4faf7;
		width: 13%;
	}
	.indent-print .clause-text { font-size: 9.8px; line-height: 1.65; }
	.indent-print .clause-text + .clause-text { margin-top: 6px; }
	.indent-print .shipping-marks { text-align: center; }

	.indent-print .signature-row td {
		border: none;
		padding-top: 34px;
	}
	.indent-print .signature-row .signature-line {
		border-top: 1px solid #0f172a;
		padding-top: 6px;
		font-weight: 600;
		font-size: 9px;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: #334155;
	}

	.indent-print .terms-note { font-size: 9.8px; color: #334155; }
	.indent-print .terms-note .heading {
		display: block;
		font-size: 9.5px;
		font-weight: 700;
		text-transform: uppercase;
		letter-spacing: 0.5px;
		color: #0f6e51;
		margin-bottom: 3px;
	}
</style>

<div class="doc-title">Indent</div>

<table>
	<tr>
		<td class="label-cell" style="width: 16%;">Indent No</td>
		<td><b>{{ doc.name }}</b></td>
		<td class="label-cell" style="width: 12%;">Date</td>
		<td>{{ frappe.utils.formatdate(doc.indent_date) }}</td>
	</tr>
</table>

<table>
	<tr>
		<td class="section-head" style="width: 50%;">Seller</td>
		<td class="section-head">Buyer</td>
	</tr>
	<tr>
		<td>
			<div class="party-name">{{ doc.supplier_name or "" }}</div>
			<div class="party-address">{{ (doc.seller_address_display or "").replace("\n", "<br>") | safe }}</div>
		</td>
		<td>
			<div class="party-name">{{ doc.customer_name or "" }}</div>
			<div class="party-address">{{ (doc.customer_address_display or "").replace("\n", "<br>") | safe }}</div>
		</td>
	</tr>
</table>

<table class="items-table">
	<tr>
		<td class="section-head" colspan="5">Items</td>
	</tr>
	<tr>
		<th>Product Description</th>
		<th style="width: 11%">HS Code</th>
		<th class="num" style="width: 13%">Quantity</th>
		<th class="num" style="width: 15%">Unit Price ({{ doc.currency }})</th>
		<th class="num" style="width: 16%">Total Value ({{ doc.currency }})</th>
	</tr>
	{% for row in doc.items %}
	<tr>
		<td>
			{{ row.item_name or row.item_code }}
			{% if row.description %}<div class="item-desc">{{ row.description }}</div>{% endif %}
		</td>
		<td>{{ row.hs_code or "" }}</td>
		<td class="num">{{ row.qty }} {{ row.uom or "" }}</td>
		<td class="num">{{ "{:,.2f}".format(row.rate or 0) }}</td>
		<td class="num">{{ "{:,.2f}".format(row.amount or 0) }}</td>
	</tr>
	{% endfor %}
	<tr class="total-row">
		<td colspan="4" style="text-align: right;">Total Value Net to Supplier ({{ doc.currency }})</td>
		<td class="num">{{ "{:,.2f}".format(doc.total_amount or 0) }}</td>
	</tr>
</table>

<table>
	<tr><td class="section-head" colspan="6">Terms &amp; Conditions</td></tr>
	<tr>
		<td class="label-cell">Payment Terms</td><td>{{ doc.payment_terms or "" }}</td>
		<td class="label-cell">Incoterm</td><td>{{ doc.incoterm or "" }}</td>
		<td class="label-cell">Lead Time</td><td>{{ doc.lead_time or "" }}</td>
	</tr>
	<tr>
		<td class="label-cell">Port of Loading</td><td>{{ doc.port_of_loading or "" }}</td>
		<td class="label-cell">Trans-Shipment</td><td>{{ doc.trans_shipment or "" }}</td>
		<td class="label-cell">GMP</td><td>{{ doc.gmp_availability or "" }}</td>
	</tr>
	<tr>
		<td class="label-cell">Destination</td><td>{{ doc.destination or "" }}</td>
		<td class="label-cell">Partial Shipment</td><td>{{ doc.partial_shipment or "" }}</td>
		<td class="label-cell">FTA</td><td>{{ doc.fta_availability or "" }}</td>
	</tr>
	<tr>
		<td class="label-cell">Origin</td><td>{{ doc.origin or "" }}</td>
		<td class="label-cell">Packing</td><td>{{ doc.packing or "" }}</td>
		<td class="label-cell">WS</td><td>{{ doc.ws_availability or "" }}</td>
	</tr>
</table>

<table>
	<tr><td class="section-head" colspan="2">Bank Details</td></tr>
	<tr><td class="label-cell">Beneficiary Name</td><td>{{ doc.bank_beneficiary_name or "" }}</td></tr>
	<tr><td class="label-cell">Bank Name</td><td>{{ doc.bank_name or "" }}</td></tr>
	<tr><td class="label-cell">Bank Address</td><td>{{ doc.bank_address or "" }}</td></tr>
	<tr><td class="label-cell">Account No</td><td>{{ doc.bank_account_no or "" }}</td></tr>
	<tr><td class="label-cell">SWIFT Code</td><td>{{ doc.swift_code or "" }}</td></tr>
</table>

<table>
	<tr>
		<td class="clause-label">For<br>Banker</td>
		<td class="clause-text">
			<b>Validity:</b> This indent is valid for 30 days from the date of issue for establishing the bank
			instrument. This bank instrument must remain valid for 90 days and an additional 15 days for negotiation.
			<div class="clause-text"><b>Payment clause (71A):</b> Clause 71A must indicate &ldquo;OUR&rdquo; at the
			time of payment remittance to ensure that the net amount is received by the beneficiary/supplier without
			any deductions.</div>
		</td>
	</tr>
	<tr>
		<td class="clause-label">For<br>Buyer</td>
		<td class="clause-text">
			Any discrepancy regarding the quality or quantity of the material must be communicated within
			<b>30 days</b> of the material's arrival.
			<div class="clause-text">Any quality-related discrepancy must be supported by a test report based on a
			mutually agreed method of testing.</div>
		</td>
	</tr>
	<tr>
		<td class="clause-label">For<br>Shipper</td>
		<td class="clause-text">
			The material must have a minimum of <b>85% shelf-life</b> remaining at the time of arrival at the
			destination port to ensure compliance with the import policy of Pakistan.
			<div class="clause-text">Non-negotiable documents including invoice, packing list, COA, GMP, Form 3,
			Form 7, FTA &amp; AWB must be emailed to the agent for approval prior to shipment.</div>
			<div class="clause-text">The buyer's NTN number must be clearly mentioned on the Airway Bill (AWB) or
			Bill of Lading.</div>
			<div class="clause-text">The original invoice and packing list must be affixed to each drum, carton,
			tin, or box to avoid any penalty charges.</div>
		</td>
	</tr>
	<tr>
		<td class="clause-label">Shipping<br>Marks</td>
		<td class="clause-text shipping-marks">
			<b>Beneficiary Name &amp; Origin</b><br>
			{{ doc.customer_name or "" }} / {{ doc.company }} / Lahore<br><br>
			<b>Material Name</b> &mdash; Net &amp; Gross Weight, Quantity, Batch No, Mfg Date &amp; Expiry Date
		</td>
	</tr>
</table>

{% if doc.terms %}
<div class="terms-note">
	<span class="heading">General Terms and Conditions</span>
	{{ doc.terms }}
</div>
{% endif %}

<table>
	<tr class="signature-row">
		<td style="width: 50%;"><div class="signature-line">Indentor Seal &amp; Signature</div></td>
		<td><div class="signature-line">Buyer's Seal &amp; Signature</div></td>
	</tr>
</table>
</div>
""".strip()

	if frappe.db.exists("Print Format", "Indent Standard"):
		pf = frappe.get_doc("Print Format", "Indent Standard")
	else:
		pf = frappe.new_doc("Print Format")
		pf.name = "Indent Standard"
		pf.doc_type = "Indent"
		pf.module = MODULE
		pf.print_format_type = "Jinja"
		pf.standard = "No"
		pf.disabled = 0

	# custom_format=1 is what actually tells Frappe to render `html` as a
	# Jinja template -- see the matching comment in setup_print_format.
	# Without it, Frappe silently ignores the HTML below and auto-builds
	# the layout instead, which is why the very first version of this print
	# format didn't look like a custom design at all.
	changed = pf.is_new() or pf.html != html or not pf.custom_format
	pf.html = html
	pf.custom_format = 1

	if pf.is_new():
		pf.insert(ignore_permissions=True)
	elif changed:
		pf.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Workspace (independent module, shortcuts, sidebar item, charts, KPIs)
# ---------------------------------------------------------------------------


LINK_CARDS = [
	{
		"label": "Inquiry",
		"icon": "small-file",
		"links": [
			{"label": "Inquiry", "link_type": "DocType", "link_to": "Inquiry"},
		],
	},
	{
		"label": "Masters",
		"icon": "list",
		"links": [
			{"label": "Inquiry Shipment Mode", "link_type": "DocType", "link_to": "Inquiry Shipment Mode"},
			{"label": "Inquiry Payment Mode", "link_type": "DocType", "link_to": "Inquiry Payment Mode"},
			{"label": "Inquiry Incoterm", "link_type": "DocType", "link_to": "Inquiry Incoterm"},
			{"label": "Inquiry Category", "link_type": "DocType", "link_to": "Inquiry Category"},
			{"label": "Indent Trade Term", "link_type": "DocType", "link_to": "Indent Trade Term"},
		],
	},
	{
		"label": "Commercial",
		"icon": "list",
		"links": [
			{"label": "Supplier", "link_type": "DocType", "link_to": "Supplier"},
			{"label": "Quotation", "link_type": "DocType", "link_to": "Quotation"},
			{"label": "Request for Quotation", "link_type": "DocType", "link_to": "Request for Quotation"},
			{"label": "Supplier Quotation", "link_type": "DocType", "link_to": "Supplier Quotation"},
			{"label": "Sales Order", "link_type": "DocType", "link_to": "Sales Order"},
			{"label": "Sales Invoice", "link_type": "DocType", "link_to": "Sales Invoice"},
			{"label": "Indent", "link_type": "DocType", "link_to": "Indent"},
		],
	},
	{
		"label": "Reports",
		"icon": "report",
		"links": [
			{
				"label": "Marketer Performance",
				"link_type": "Report",
				"link_to": "Marketer Performance",
				"is_query_report": 1,
			},
			{
				"label": "Inquiry Status Summary",
				"link_type": "Report",
				"link_to": "Inquiry Status Summary",
				"is_query_report": 1,
			},
		],
	},
]


def setup_workspace():
	if frappe.db.exists("Workspace", "Smart App"):
		workspace = frappe.get_doc("Workspace", "Smart App")
	else:
		workspace = _build_base_workspace()

	_add_workspace_visuals(workspace)
	_add_workspace_links(workspace)
	_add_commercial_section(workspace)


def _build_base_workspace():
	content = [
		{
			"id": frappe.generate_hash(length=10),
			"type": "header",
			"data": {"text": '<span class="h4"><b>Smart App</b></span>', "col": 12},
		},
		{
			"id": frappe.generate_hash(length=10),
			"type": "paragraph",
			"data": {
				"text": "Inquiry management, marketer performance and trading workflow automation.",
				"col": 12,
			},
		},
		{
			"id": frappe.generate_hash(length=10),
			"type": "header",
			"data": {"text": '<span class="h5">Shortcuts</span>', "col": 12},
		},
	]

	workspace = frappe.new_doc("Workspace")
	workspace.name = "Smart App"
	workspace.title = "Smart App"
	workspace.label = "Smart App"
	workspace.module = MODULE
	workspace.icon = "crm"
	workspace.public = 1
	workspace.is_hidden = 0
	workspace.sequence_id = 10.0

	for s in SHORTCUTS:
		workspace.append("shortcuts", s)
		content.append(
			{
				"id": frappe.generate_hash(length=10),
				"type": "shortcut",
				"data": {"shortcut_name": s["label"], "col": 3},
			}
		)

	workspace.content = json.dumps(content)
	workspace.insert(ignore_permissions=True)
	return workspace


def _has_content_block(content, block_type, **data_match):
	"""Whether `content` already has a block of this type whose data matches
	every key/value given -- used to guard every content.append() so
	re-running setup_workspace() on each migrate doesn't pile up duplicate
	headers/shortcuts/charts/cards every single time."""
	for block in content:
		if block.get("type") != block_type:
			continue
		data = block.get("data", {})
		if all(data.get(k) == v for k, v in data_match.items()):
			return True
	return False


def _dedupe_content_blocks(content):
	"""One-time (but safe to re-run) cleanup for content arrays that already
	accumulated duplicates from before content.append() calls were guarded --
	keeps only the first occurrence of each (type, identifying-field) block."""
	key_field_by_type = {
		"header": "text",
		"paragraph": "text",
		"shortcut": "shortcut_name",
		"chart": "chart_name",
		"number_card": "number_card_name",
		"card": "card_name",
	}
	seen = set()
	deduped = []
	for block in content:
		btype = block.get("type")
		data = block.get("data", {})
		key_field = key_field_by_type.get(btype)
		key = (btype, data.get(key_field)) if key_field else (btype, json.dumps(data, sort_keys=True))
		if key in seen:
			continue
		seen.add(key)
		deduped.append(block)
	return deduped


def _add_workspace_visuals(workspace):
	workspace.reload()
	content = _dedupe_content_blocks(json.loads(workspace.content or "[]"))

	existing_cards = {row.number_card_name for row in workspace.get("number_cards")}
	existing_charts = {row.chart_name for row in workspace.get("charts")}

	key_numbers_header = '<span class="h5">Key Numbers</span>'
	if not _has_content_block(content, "header", text=key_numbers_header):
		content.append(
			{"id": frappe.generate_hash(length=10), "type": "header", "data": {"text": key_numbers_header, "col": 12}}
		)
	for card in CARD_NAMES + COMMERCIAL_CARD_NAMES:
		if card not in existing_cards:
			workspace.append("number_cards", {"number_card_name": card, "label": card})
		if not _has_content_block(content, "number_card", number_card_name=card):
			content.append(
				{
					"id": frappe.generate_hash(length=10),
					"type": "number_card",
					"data": {"number_card_name": card, "col": 3},
				}
			)

	charts_header = '<span class="h5">Charts</span>'
	if not _has_content_block(content, "header", text=charts_header):
		content.append(
			{"id": frappe.generate_hash(length=10), "type": "header", "data": {"text": charts_header, "col": 12}}
		)
	for chart in CHART_NAMES + COMMERCIAL_CHART_NAMES:
		if chart not in existing_charts:
			workspace.append("charts", {"chart_name": chart, "label": chart})
		if not _has_content_block(content, "chart", chart_name=chart):
			content.append(
				{
					"id": frappe.generate_hash(length=10),
					"type": "chart",
					"data": {"chart_name": chart, "col": 6},
				}
			)

	workspace.content = json.dumps(content)
	workspace.save(ignore_permissions=True)


def _add_workspace_links(workspace):
	"""Classic ERPNext-style grouped Links section: a card per group (Inquiry,
	Masters, Reports) each listing every doctype/report in the app. Only adds
	cards that don't already exist, same as shortcuts/charts/number_cards, so
	it never clobbers anything an Inquiry Manager customised by hand via the
	workspace editor."""
	workspace.reload()
	content = _dedupe_content_blocks(json.loads(workspace.content or "[]"))
	existing_cards = {row.label for row in workspace.get("links") if row.type == "Card Break"}

	links_header = '<span class="h5">Links</span>'
	if not _has_content_block(content, "header", text=links_header):
		content.append(
			{"id": frappe.generate_hash(length=10), "type": "header", "data": {"text": links_header, "col": 12}}
		)

	for card in LINK_CARDS:
		if card["label"] not in existing_cards:
			workspace.append(
				"links",
				{
					"type": "Card Break",
					"label": card["label"],
					"icon": card.get("icon"),
					"link_count": len(card["links"]),
				},
			)
			for link in card["links"]:
				workspace.append(
					"links",
					{
						"type": "Link",
						"label": link["label"],
						"link_type": link["link_type"],
						"link_to": link["link_to"],
						"is_query_report": link.get("is_query_report", 0),
					},
				)
		if _has_content_block(content, "card", card_name=card["label"]):
			continue
		content.append(
			{
				"id": frappe.generate_hash(length=10),
				"type": "card",
				"data": {"card_name": card["label"], "col": 4},
			}
		)

	workspace.content = json.dumps(content)
	workspace.save(ignore_permissions=True)


def _add_commercial_section(workspace):
	"""Shortcuts for the Commercial team's pipeline: assignment overview,
	Quotation/RFQ/Supplier Quotation lists, and the two core ERPNext reports
	for purchase history and RFQ-reply comparison. Same idempotent
	"add if missing" pattern as the rest of the workspace."""
	workspace.reload()
	content = _dedupe_content_blocks(json.loads(workspace.content or "[]"))
	existing_shortcuts = {row.label for row in workspace.get("shortcuts")}

	if not any(b.get("type") == "header" and "Commercial Team" in b.get("data", {}).get("text", "") for b in content):
		content.append(
			{
				"id": frappe.generate_hash(length=10),
				"type": "header",
				"data": {"text": '<span class="h5">Commercial Team</span>', "col": 12},
			}
		)

	for s in COMMERCIAL_SHORTCUTS:
		if s["label"] not in existing_shortcuts:
			workspace.append("shortcuts", s)
			content.append(
				{
					"id": frappe.generate_hash(length=10),
					"type": "shortcut",
					"data": {"shortcut_name": s["label"], "col": 3},
				}
			)

	workspace.content = json.dumps(content)
	workspace.save(ignore_permissions=True)


def add_home_workspace_shortcut():
	"""Best-effort: add a Smart App shortcut card onto the standard Home
	workspace so it's reachable from the very first screen a user sees."""
	if not frappe.db.exists("Workspace", "Home"):
		return

	home = frappe.get_doc("Workspace", "Home")
	already_linked = any(row.label == "Smart App" for row in home.get("shortcuts"))
	if already_linked:
		return

	home.append(
		"shortcuts",
		{"label": "Smart App", "type": "URL", "url": "/app/smart-app", "color": "#3B82F6"},
	)

	content = json.loads(home.content or "[]")
	content.append(
		{
			"id": frappe.generate_hash(length=10),
			"type": "shortcut",
			"data": {"shortcut_name": "Smart App", "col": 3},
		}
	)
	home.content = json.dumps(content)
	home.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Let Inquiry Manager self-serve on the Inquiry Workflow definition
# ---------------------------------------------------------------------------


def grant_inquiry_manager_workflow_access():
	for doctype in ("Workflow", "Workflow State", "Workflow Action Master"):
		_grant_custom_docperm(doctype, "Inquiry Manager", read=1, write=1, select=1)


def _grant_custom_docperm(doctype, role, **perms):
	"""Reconciles the grant on every run (not just create-once), so widening
	or narrowing a permission set in this file self-heals on the next
	migrate instead of being stuck with whatever was granted the first time
	a given (doctype, role) pair was seen."""
	existing_name = frappe.db.get_value(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}, "name"
	)
	if existing_name:
		doc = frappe.get_doc("Custom DocPerm", existing_name)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Custom DocPerm",
				"parent": doctype,
				"parenttype": "DocType",
				"parentfield": "permissions",
				"role": role,
				"permlevel": 0,
			}
		)

	changed = False
	for key, value in perms.items():
		if doc.get(key) != value:
			doc.set(key, value)
			changed = True

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	elif changed:
		doc.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Restricted sidebar: users whose ONLY roles are Inquiry-related see just the
# Smart App workspace (see smart_app.smart_app.utils.sync_module_profile for
# the per-user auto-assignment, which deliberately leaves mixed-role users —
# e.g. someone who is also a Sales User — untouched).
# ---------------------------------------------------------------------------


def setup_module_profile():
	"""Rebuilds the block list every run (not just on first create) so a
	correction to BUSINESS_MODULES_TO_HIDE self-heals on the next migrate,
	rather than being stuck with whatever list existed when the profile was
	first created."""
	existing_modules = set(frappe.get_all("Module Def", pluck="name"))
	modules_to_block = sorted(m for m in BUSINESS_MODULES_TO_HIDE if m in existing_modules)

	if frappe.db.exists("Module Profile", MODULE_PROFILE_NAME):
		profile = frappe.get_doc("Module Profile", MODULE_PROFILE_NAME)
	else:
		profile = frappe.new_doc("Module Profile")
		profile.module_profile_name = MODULE_PROFILE_NAME

	profile.set("block_modules", [])
	for module in modules_to_block:
		profile.append("block_modules", {"module": module})

	if profile.is_new():
		profile.insert(ignore_permissions=True)
	else:
		profile.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Test users: one login per role, so permissions can be verified end-to-end.
# TEST CREDENTIALS ONLY — the password is only ever set on first creation
# (never reset on a later migrate, so changing it afterwards sticks), and
# these should be disabled, removed, or given a real password before any
# real deployment.
# ---------------------------------------------------------------------------

TEST_USERS = [
	{
		"email": "commercialmanager@smartchem.com",
		"full_name": "Commercial Manager (Test)",
		"role": "Commercial Manager",
	},
	{
		"email": "commercialofficer@smartchem.com",
		"full_name": "Commercial Officer (Test)",
		"role": "Commercial Officer",
	},
	{
		"email": "inquiryofficer@smartchem.com",
		"full_name": "Inquiry Officer (Test)",
		"role": "Inquiry Officer",
	},
	{
		"email": "inquirymanager@smartchem.com",
		"full_name": "Inquiry Manager (Test)",
		"role": "Inquiry Manager",
	},
]

# Longer/mixed-character than a bare "test123" specifically so this doesn't
# get rejected by a site with System Settings > Security > "Enforce Password
# Policy" turned on (Frappe scores password strength via zxcvbn and requires
# a minimum score) -- also explicitly bypassed via ignore_password_policy
# below, so this creates successfully regardless of that setting either way.
TEST_USER_PASSWORD = "Test@12345"


def setup_test_users():
	for u in TEST_USERS:
		if frappe.db.exists("User", u["email"]):
			continue
		user = frappe.new_doc("User")
		user.email = u["email"]
		user.first_name = u["full_name"]
		user.send_welcome_email = 0
		user.user_type = "System User"
		user.new_password = TEST_USER_PASSWORD
		user.flags.ignore_password_policy = True
		user.append("roles", {"role": u["role"]})
		user.insert(ignore_permissions=True)


def backfill_commercial_manager_inquiry_user_role():
	"""sync_inquiry_user_role (utils.py) only fixes up a User's roles on that
	User's own next save -- so a Commercial Manager created before Commercial
	Manager was added to INQUIRY_USER_ROLE_TRIGGERS (or simply never edited
	since) needs a one-time nudge. Re-saving triggers the same validate hook,
	so this reuses that logic rather than duplicating it."""
	if not frappe.db.exists("Role", "Inquiry User"):
		return

	commercial_managers = frappe.get_all(
		"Has Role", filters={"role": "Commercial Manager", "parenttype": "User"}, pluck="parent"
	)
	for user_name in commercial_managers:
		user = frappe.get_doc("User", user_name)
		if "Inquiry User" not in [r.role for r in user.roles]:
			user.save(ignore_permissions=True)


def backfill_commercial_status():
	"""Any Inquiry that existed before commercial_status was added to the
	doctype has NULL there, not the literal string "Unassigned" (Frappe
	doesn't retroactively backfill a new field's default onto existing
	rows) -- normalise those directly so the Commercial Pipeline Kanban
	doesn't show a separate blank column, and so Inquiry.sync_commercial_
	status's own defensive handling of this (see inquiry.py) always has a
	clean starting point going forward."""
	frappe.db.sql(
		"""
		update `tabInquiry`
		set commercial_status = 'Unassigned'
		where commercial_status is null or commercial_status = ''
		"""
	)

	# Separately, any Inquiry assigned via the Assign button before the
	# before_update_after_submit fix (see inquiry.py) has a real
	# commercial_officer on it but got stuck on commercial_status =
	# "Unassigned", because validate()/sync_commercial_status() was never
	# invoked for that save (Frappe only runs validate() for a "save" or
	# "submit" action, not "update_after_submit" -- see the docstring on
	# Inquiry.before_update_after_submit). This is real assignment data,
	# not a display default, so it needs its own targeted correction --
	# only rows genuinely stuck (officer set, status still Unassigned),
	# never touching one already further along the pipeline.
	frappe.db.sql(
		"""
		update `tabInquiry`
		set commercial_status = 'Assigned'
		where commercial_officer is not null
			and commercial_officer != ''
			and commercial_status = 'Unassigned'
		"""
	)


def backfill_party_price_lists():
	"""ensure_default_price_list (utils.py) only runs automatically for a
	*new* Customer/Supplier via their after_insert hook -- this applies the
	same thing to every party that already existed before that feature was
	added, so multi-price management isn't limited to records created from
	here on."""
	from smart_app.smart_app.utils import ensure_default_price_list

	for customer in frappe.get_all("Customer", fields=["name", "customer_name", "default_price_list"]):
		if not customer.default_price_list:
			ensure_default_price_list("Customer", customer.name, customer.customer_name or customer.name)

	for supplier in frappe.get_all("Supplier", fields=["name", "supplier_name", "default_price_list"]):
		if not supplier.default_price_list:
			ensure_default_price_list("Supplier", supplier.name, supplier.supplier_name or supplier.name)


def backfill_item_default_warehouse():
	"""ensure_item_default_warehouse (utils.py, Item.validate) only fixes up a
	stock Item's Item Defaults on that Item's own next save -- so any stock
	Item created before this fix shipped (or simply never re-saved since)
	still has none, and will trip ERPNext's own "Warehouse is mandatory for
	stock Item" validation the next time it's used with a qty on a Request
	for Quotation, Supplier Quotation, or Purchase Order. Same gap, applied
	directly to every existing stock Item that's missing a default for the
	site's global default Company."""
	from smart_app.smart_app.utils import get_default_warehouse_for_company

	company = frappe.defaults.get_global_default("company")
	if not company:
		return

	warehouse = get_default_warehouse_for_company(company)
	if not warehouse:
		return

	stock_items = frappe.get_all("Item", filters={"is_stock_item": 1, "disabled": 0}, pluck="name")
	for item_code in stock_items:
		if frappe.db.exists("Item Default", {"parent": item_code, "company": company}):
			continue
		item = frappe.get_doc("Item", item_code)
		item.append("item_defaults", {"company": company, "default_warehouse": warehouse})
		item.save(ignore_permissions=True)


def backfill_supplier_bank_details():
	"""ensure_supplier_bank_details (utils.py, Supplier.validate) only fixes
	up a Supplier's structured bank_*/seller_address_display fields on that
	Supplier's own next save -- applies the same parse directly to every
	Supplier that already existed before those fields were added, so all
	345 imported by smart_app.supplier_import get their Indent-ready bank
	details without needing to be individually re-saved first. Only ever
	fills a field that's currently blank."""
	from smart_app.smart_app.utils import parse_supplier_details_text

	bank_fields = ["bank_beneficiary_name", "bank_name", "bank_address", "bank_account_no", "swift_code"]
	fields = ["name", "supplier_details", "seller_address_display", *bank_fields]

	for supplier in frappe.get_all("Supplier", fields=fields):
		parsed = parse_supplier_details_text(supplier.get("supplier_details"))
		for fieldname, value in parsed.items():
			if not supplier.get(fieldname):
				frappe.db.set_value("Supplier", supplier.name, fieldname, value, update_modified=False)


def backfill_rfq_quotation_links():
	"""The `quotation` traceability field on Request for Quotation (see
	setup_quotation_integration) is new -- any RFQ created before it existed
	only ever got `inquiry` set. Where that Inquiry has exactly one
	Quotation against it, that's unambiguously this RFQ's source -- fill it
	in directly; left blank wherever it's ambiguous (more than one
	Quotation against the same Inquiry) rather than guessing."""
	if not frappe.db.exists("DocType", "Request for Quotation"):
		return
	if not frappe.get_meta("Request for Quotation").has_field("quotation"):
		return

	rfqs = frappe.get_all(
		"Request for Quotation",
		filters={"inquiry": ["is", "set"]},
		fields=["name", "inquiry", "quotation"],
	)
	for rfq in rfqs:
		if rfq.quotation:
			continue
		quotations = frappe.get_all("Quotation", filters={"inquiry": rfq.inquiry}, pluck="name")
		if len(quotations) == 1:
			frappe.db.set_value("Request for Quotation", rfq.name, "quotation", quotations[0])


# ---------------------------------------------------------------------------
# Email branding: replace Frappe/ERPNext's generic footer on outgoing
# emails (used by RFQ supplier emails, among everything else) with a
# placeholder that's obviously meant to be edited — this app has no way to
# know your company's real name/address, so it deliberately does not
# fabricate one. Left alone if you've already customised
# email_footer_address yourself.
# ---------------------------------------------------------------------------


def setup_email_branding():
	settings = frappe.get_single("System Settings")
	changed = False

	if not settings.email_footer_address:
		settings.email_footer_address = (
			"Your Company Name — update this in System Settings > Email > "
			"Email Footer Address"
		)
		changed = True

	if not settings.disable_standard_email_footer:
		settings.disable_standard_email_footer = 1
		changed = True

	if changed:
		settings.save(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Email Template: a reusable, editable format for the RFQ supplier message
# (Request for Quotation's own message_for_supplier field), rather than
# every Commercial Officer writing that email from scratch each time.
# Edit its wording any time from Settings > Email > Email Template.
# ---------------------------------------------------------------------------

RFQ_EMAIL_TEMPLATE_NAME = "Request for Quotation - Supplier Message"

RFQ_EMAIL_TEMPLATE_SUBJECT = "Request for Quotation - {{ name }}"

# Variables available here come from RequestforQuotation.supplier_rfq_mail in
# ERPNext core (erpnext/buying/doctype/request_for_quotation/
# request_for_quotation.py) -- it renders this against a FLAT dict
# (self.as_dict(), i.e. every RFQ field directly: name, company, items, ...,
# plus supplier/supplier_name/portal_link/update_password_link/user_fullname
# merged in on top) -- there is no "doc" wrapper, so `{{ doc.name }}` would
# silently render blank. portal_link is the supplier's actual way to respond
# (a "Submit your Quotation" button to the RFQ portal) -- the original
# version of this template omitted it entirely, so a supplier receiving that
# email had no way to act on it at all.
RFQ_EMAIL_TEMPLATE_BODY = """
<div style="font-family: Arial, Helvetica, sans-serif; color: #1f2937; max-width: 640px;">
<p>Dear {{ supplier_name or supplier }},</p>
<p>{{ company }} would like to request your best quotation for the item(s) listed below.
Please share your price, lead time, and payment terms at your earliest convenience.</p>
<table style="border-collapse: collapse; width: 100%; margin: 16px 0;">
<thead>
<tr style="background: #0f172a; color: #ffffff;">
<th style="padding: 8px; text-align: left; border: 1px solid #0f172a;">Item</th>
<th style="padding: 8px; text-align: left; border: 1px solid #0f172a;">Qty</th>
<th style="padding: 8px; text-align: left; border: 1px solid #0f172a;">UOM</th>
<th style="padding: 8px; text-align: left; border: 1px solid #0f172a;">Required By</th>
</tr>
</thead>
<tbody>
{% for item in items %}
<tr>
<td style="padding: 8px; border: 1px solid #cbd5e1;">{{ item.item_name or item.item_code }}</td>
<td style="padding: 8px; border: 1px solid #cbd5e1;">{{ item.qty }}</td>
<td style="padding: 8px; border: 1px solid #cbd5e1;">{{ item.uom }}</td>
<td style="padding: 8px; border: 1px solid #cbd5e1;">{{ item.schedule_date }}</td>
</tr>
{% endfor %}
</tbody>
</table>
<p>{{ portal_link }}{% if update_password_link %} {{ update_password_link }}{% endif %}</p>
<p>Thank you,<br>{{ user_fullname }}<br>{{ company }}</p>
</div>
""".strip()


def setup_email_templates():
	"""Self-healing, but only over content this installer generated itself --
	if a Commercial Manager has since edited the wording from Settings >
	Email > Email Template, that customisation is left alone rather than
	silently overwritten on the next migrate."""
	previously_generated_bodies = (
		RFQ_EMAIL_TEMPLATE_BODY,
		# the original template this replaced -- referenced `doc.company`
		# against a flat context (silently rendered blank) and never
		# included a portal_link, so a supplier had no way to actually
		# respond to the RFQ.
		"""<p>Dear Sir/Madam,</p>
<p>We would like to request your best quotation for the items listed below.
Please share your price, lead time, and payment terms at your earliest
convenience.</p>
<p>Thank you,<br>{{ doc.company }}</p>""",
	)

	if frappe.db.exists("Email Template", RFQ_EMAIL_TEMPLATE_NAME):
		template = frappe.get_doc("Email Template", RFQ_EMAIL_TEMPLATE_NAME)
		if template.response.strip() in previously_generated_bodies:
			template.subject = RFQ_EMAIL_TEMPLATE_SUBJECT
			template.response = RFQ_EMAIL_TEMPLATE_BODY
			template.save(ignore_permissions=True)
		return

	frappe.get_doc(
		{
			"doctype": "Email Template",
			"name": RFQ_EMAIL_TEMPLATE_NAME,
			"subject": RFQ_EMAIL_TEMPLATE_SUBJECT,
			"response": RFQ_EMAIL_TEMPLATE_BODY,
		}
	).insert(ignore_permissions=True)
