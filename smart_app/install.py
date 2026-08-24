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
	run_step(setup_workflow, "workflow")
	run_step(setup_kanban_board, "kanban board")
	run_step(setup_dashboard_charts, "dashboard charts")
	run_step(setup_number_cards, "number cards")
	run_step(setup_commercial_overview, "commercial overview (cards + kanban + report)")
	run_step(setup_dashboard, "dashboard")
	run_step(setup_reports, "reports")
	run_step(setup_print_format, "print format")
	run_step(setup_workspace, "workspace")
	run_step(add_home_workspace_shortcut, "home workspace shortcut")
	run_step(grant_inquiry_manager_workflow_access, "inquiry manager workflow access")
	run_step(setup_module_profile, "restricted module profile")
	run_step(setup_quotation_integration, "quotation get-items-from + create-rfq integration")
	run_step(setup_item_master_columns, "item master columns (UOM/pharmacopeia/grade)")
	run_step(setup_item_supplier_customization, "multi-supplier management on Item (type/preferred)")
	run_step(setup_test_users, "test users")
	run_step(backfill_commercial_manager_inquiry_user_role, "backfill Inquiry User role for Commercial Manager")
	run_step(backfill_commercial_status, "backfill blank/stuck commercial_status on existing Inquiries")
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
# Quotation to the suppliers of its items. None of the core doctypes that
# flow touches (Quotation, Request for Quotation, Supplier, Supplier
# Quotation, plus Item/Company/Currency/Customer/Contact which Quotation and
# RFQ themselves need) are granted to any role in this app by default.
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

		# Commercial Officer generates these; Commercial Manager gets the
		# same access for oversight (reassigning, reviewing, following up).
		for doctype in ("Quotation", "Request for Quotation"):
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


def _create_number_card(label, function, filters, aggregate_function_based_on=None):
	if frappe.db.exists("Number Card", label):
		return
	card = frappe.new_doc("Number Card")
	card.label = label
	card.document_type = "Inquiry"
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


def _create_query_report(name, query, roles=("Inquiry Manager", "Inquiry Officer", "Marketer", "System Manager")):
	"""Reconciles the query/roles on every run, not just on first create, so
	an updated SQL definition (e.g. dropping a removed field) self-heals on
	the next migrate instead of leaving the stale version in place."""
	if frappe.db.exists("Report", name):
		report = frappe.get_doc("Report", name)
	else:
		report = frappe.new_doc("Report")
		report.report_name = name
		report.ref_doctype = "Inquiry"
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

	changed = pf.is_new() or pf.html != html
	pf.html = html

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
	for chart in CHART_NAMES:
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

RFQ_EMAIL_TEMPLATE_SUBJECT = "Request for Quotation - {{ doc.name }}"

RFQ_EMAIL_TEMPLATE_BODY = """
<p>Dear Sir/Madam,</p>
<p>We would like to request your best quotation for the items listed below.
Please share your price, lead time, and payment terms at your earliest
convenience.</p>
<p>Thank you,<br>{{ doc.company }}</p>
""".strip()


def setup_email_templates():
	if frappe.db.exists("Email Template", RFQ_EMAIL_TEMPLATE_NAME):
		return
	frappe.get_doc(
		{
			"doctype": "Email Template",
			"name": RFQ_EMAIL_TEMPLATE_NAME,
			"subject": RFQ_EMAIL_TEMPLATE_SUBJECT,
			"response": RFQ_EMAIL_TEMPLATE_BODY,
		}
	).insert(ignore_permissions=True)
