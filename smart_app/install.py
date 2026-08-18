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
	"Estimated Value Trend",
]

CARD_NAMES = [
	"Open Inquiries",
	"Converted Inquiries",
	"Lost Inquiries",
	"Open Pipeline Value",
]

REPORT_NAMES = ["Marketer Performance", "Inquiry Status Summary"]

SHORTCUTS = [
	{"label": "New Inquiry", "type": "DocType", "link_to": "Inquiry", "doc_view": "New", "color": "Blue"},
	{"label": "Inquiry List", "type": "DocType", "link_to": "Inquiry", "doc_view": "List", "color": "Blue"},
	{
		"label": "Inquiry Kanban",
		"type": "DocType",
		"link_to": "Inquiry",
		"doc_view": "Kanban",
		"color": "Green",
	},
	{"label": "Inquiry Report", "type": "DocType", "link_to": "Inquiry", "doc_view": "Report", "color": "Green"},
	{"label": "Marketer Performance", "type": "Report", "link_to": "Marketer Performance", "color": "Orange"},
	{"label": "Inquiry Status Summary", "type": "Report", "link_to": "Inquiry Status Summary", "color": "Orange"},
	{
		"label": "Mode of Shipment",
		"type": "DocType",
		"link_to": "Inquiry Shipment Mode",
		"doc_view": "List",
		"color": "Grey",
	},
	{
		"label": "Mode of Payment",
		"type": "DocType",
		"link_to": "Inquiry Payment Mode",
		"doc_view": "List",
		"color": "Grey",
	},
	{
		"label": "Incoterms",
		"type": "DocType",
		"link_to": "Inquiry Incoterm",
		"doc_view": "List",
		"color": "Grey",
	},
	{
		"label": "Inquiry Category",
		"type": "DocType",
		"link_to": "Inquiry Category",
		"doc_view": "List",
		"color": "Grey",
	},
]


def after_install():
	setup()


def after_migrate():
	setup()


def setup():
	run_step(ensure_roles, "roles")
	run_step(seed_master_data, "master data")
	run_step(setup_workflow, "workflow")
	run_step(setup_kanban_board, "kanban board")
	run_step(setup_dashboard_charts, "dashboard charts")
	run_step(setup_number_cards, "number cards")
	run_step(setup_dashboard, "dashboard")
	run_step(setup_reports, "reports")
	run_step(setup_print_format, "print format")
	run_step(setup_workspace, "workspace")
	run_step(add_home_workspace_shortcut, "home workspace shortcut")
	run_step(grant_inquiry_manager_workflow_access, "inquiry manager workflow access")

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
	for role in ("Inquiry Manager", "Inquiry Officer", "Marketer"):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


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
	if frappe.db.exists("Workflow", "Inquiry Workflow"):
		return

	all_roles = ["Inquiry Officer", "Marketer", "Inquiry Manager"]
	manager_only = ["Inquiry Manager"]

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

	workflow = frappe.new_doc("Workflow")
	workflow.workflow_name = "Inquiry Workflow"
	workflow.document_type = "Inquiry"
	workflow.workflow_state_field = "inquiry_status"
	workflow.is_active = 1
	workflow.send_email_alert = 0

	for state in STATUSES:
		workflow.append("states", {"state": state, "doc_status": "0"})

	for from_state, action, next_state, roles in transitions:
		for role in roles:
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

	workflow.insert(ignore_permissions=True)


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
		{
			"chart_name": "Estimated Value Trend",
			"chart_type": "Sum",
			"value_based_on": "estimated_value",
			"type": "Line",
			"timeseries": 1,
			"time_interval": "Monthly",
			"timespan": "Last Year",
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
		{
			"label": "Open Pipeline Value",
			"function": "Sum",
			"aggregate_function_based_on": "estimated_value",
			"filters_json": [["Inquiry", "inquiry_status", "not in", ["Lost", "Closed"]]],
		},
	]
	for c in cards:
		if frappe.db.exists("Number Card", c["label"]):
			continue
		card = frappe.new_doc("Number Card")
		card.label = c["label"]
		card.document_type = "Inquiry"
		card.type = "Document Type"
		card.function = c["function"]
		card.aggregate_function_based_on = c.get("aggregate_function_based_on")
		card.filters_json = json.dumps(c["filters_json"])
		card.is_public = 1
		card.show_percentage_stats = 1
		card.stats_time_interval = "Monthly"
		card.module = MODULE
		card.insert(ignore_permissions=True)


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
			sum(case when i.inquiry_status not in ('Converted', 'Lost', 'Closed') then 1 else 0 end) as "In Progress:Int:120",
			sum(ifnull(i.estimated_value, 0)) as "Total Estimated Value:Currency:180"
		from `tabInquiry` i
		left join `tabEmployee` e on e.name = i.marketer
		group by i.marketer
		order by sum(ifnull(i.estimated_value, 0)) desc
		""".strip(),
	)

	_create_query_report(
		"Inquiry Status Summary",
		"""
		select
			i.inquiry_status as "Status:Data:130",
			ic.category_name as "Category:Data:220",
			count(i.name) as "Total Inquiries:Int:130",
			sum(ifnull(i.estimated_value, 0)) as "Total Estimated Value:Currency:180"
		from `tabInquiry` i
		left join `tabInquiry Category` ic on ic.name = i.category
		group by i.inquiry_status, i.category
		order by field(i.inquiry_status, 'Open', 'Quotation', 'Replied', 'Converted', 'Lost', 'Closed')
		""".strip(),
	)


def _create_query_report(name, query):
	if frappe.db.exists("Report", name):
		return
	report = frappe.new_doc("Report")
	report.report_name = name
	report.ref_doctype = "Inquiry"
	report.report_type = "Query Report"
	report.is_standard = "No"
	report.module = MODULE
	report.query = query
	for role in ("Inquiry Manager", "Inquiry Officer", "Marketer", "System Manager"):
		report.append("roles", {"role": role})
	report.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Print Format
# ---------------------------------------------------------------------------


def setup_print_format():
	if frappe.db.exists("Print Format", "Inquiry Standard"):
		return

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
			<td><b>Estimated Value</b></td>
			<td>{{ frappe.utils.fmt_money(doc.estimated_value, currency=doc.currency) if doc.estimated_value else "" }}</td>
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

	pf = frappe.new_doc("Print Format")
	pf.name = "Inquiry Standard"
	pf.doc_type = "Inquiry"
	pf.module = MODULE
	pf.print_format_type = "Jinja"
	pf.standard = "No"
	pf.disabled = 0
	pf.html = html
	pf.insert(ignore_permissions=True)


# ---------------------------------------------------------------------------
# Workspace (independent module, shortcuts, sidebar item, charts, KPIs)
# ---------------------------------------------------------------------------


def setup_workspace():
	if frappe.db.exists("Workspace", "Smart App"):
		workspace = frappe.get_doc("Workspace", "Smart App")
	else:
		workspace = _build_base_workspace()

	_add_workspace_visuals(workspace)


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


def _add_workspace_visuals(workspace):
	workspace.reload()
	content = json.loads(workspace.content or "[]")

	existing_cards = {row.number_card_name for row in workspace.get("number_cards")}
	existing_charts = {row.chart_name for row in workspace.get("charts")}

	content.append(
		{
			"id": frappe.generate_hash(length=10),
			"type": "header",
			"data": {"text": '<span class="h5">Key Numbers</span>', "col": 12},
		}
	)
	for card in CARD_NAMES:
		if card not in existing_cards:
			workspace.append("number_cards", {"number_card_name": card, "label": card})
		content.append(
			{
				"id": frappe.generate_hash(length=10),
				"type": "number_card",
				"data": {"number_card_name": card, "col": 3},
			}
		)

	content.append(
		{
			"id": frappe.generate_hash(length=10),
			"type": "header",
			"data": {"text": '<span class="h5">Charts</span>', "col": 12},
		}
	)
	for chart in CHART_NAMES:
		if chart not in existing_charts:
			workspace.append("charts", {"chart_name": chart, "label": chart})
		content.append(
			{
				"id": frappe.generate_hash(length=10),
				"type": "chart",
				"data": {"chart_name": chart, "col": 6},
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
		{"label": "Smart App", "type": "URL", "url": "/app/smart-app", "color": "Blue"},
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
	if frappe.db.exists(
		"Custom DocPerm", {"parent": doctype, "role": role, "permlevel": 0}
	):
		return
	frappe.get_doc(
		{
			"doctype": "Custom DocPerm",
			"parent": doctype,
			"parenttype": "DocType",
			"parentfield": "permissions",
			"role": role,
			"permlevel": 0,
			**perms,
		}
	).insert(ignore_permissions=True)
