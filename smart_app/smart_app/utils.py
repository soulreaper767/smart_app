# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe

APPLICABLE_FOR = "Inquiry"


def sync_marketer_user_permission(doc, method=None):
	"""Employee.on_update: keep the Marketer -> Employee User Permission in sync."""
	sync_marketer_permission_for_employee(doc.name)


def sync_marketer_user_permission_for_user(doc, method=None):
	"""User.on_update: role changes may add/remove the Marketer role."""
	for employee in frappe.get_all("Employee", filters={"user_id": doc.name}, pluck="name"):
		sync_marketer_permission_for_employee(employee)


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
