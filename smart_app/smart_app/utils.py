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
	"""User.validate: keep the internal "Inquiry User" umbrella role (used only
	to satisfy the Inquiry Workflow's single-role `allow_edit` slot) in sync
	with whether this user holds any of the three real Inquiry roles. Runs in
	`validate` (not `on_update`) so the role list is fixed up as part of the
	same save instead of triggering a second, recursive save."""
	if not frappe.db.exists("Role", UMBRELLA_ROLE):
		return

	current_roles = {r.role for r in doc.get("roles")}
	has_inquiry_role = bool(current_roles & INQUIRY_ROLES)
	has_umbrella_role = UMBRELLA_ROLE in current_roles

	if has_inquiry_role and not has_umbrella_role:
		doc.append("roles", {"role": UMBRELLA_ROLE})
	elif has_umbrella_role and not has_inquiry_role:
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
