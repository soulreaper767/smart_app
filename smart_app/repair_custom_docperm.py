# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
One-shot (but safe to re-run) repair for a real permission regression this
app's own grant_* functions caused on every core ERPNext doctype they ever
touched. **Run this immediately on any site that has already run a
migrate with the old (pre-fix) install.py.**

    bench --site <site> execute smart_app.repair_custom_docperm.repair_custom_docperm
    # preview only, writes nothing:
    bench --site <site> execute smart_app.repair_custom_docperm.repair_custom_docperm --kwargs "{'dry_run': True}"

**What happened.** Frappe's own `Meta.set_custom_permissions()`
(`frappe/model/meta.py`) -- docstring literally "Reset `permissions` with
Custom DocPerm if exists" -- means the moment *any* Custom DocPerm row
exists for a doctype, every role's effective permission on it comes
*only* from Custom DocPerm, completely replacing (not merging with) that
doctype's own native permissions from its DocType JSON. `install.py`'s own
`_grant_custom_docperm` helper (used by `grant_master_data_access`/
`grant_commercial_access`/`grant_logistics_access`/
`grant_inquiry_manager_workflow_access`) never accounted for this: the
very first grant on a given core doctype -- e.g. Commercial Officer's own
row on Address -- silently revoked every *other* role's native access to
it too, System Manager included. This is exactly what produced "does not
have doctype access via role permission for document Address" for a
System Manager login on a live site that had already migrated.

`install.py`'s `_grant_custom_docperm` is fixed going forward (it now
seeds Custom DocPerm with a full copy of the native permissions the first
time it ever touches a doctype) -- but that fix only protects a doctype
this app hasn't granted anything on *yet*. Every doctype already poisoned
by the old code on an already-migrated site needs this one-time repair
instead: restores exactly the roles (and permlevels) that went missing,
by diffing each affected doctype's *native* DocType.json permissions
(untouched the whole time -- Custom DocPerm is a separate table, nothing
was ever destroyed, only shadowed) against its current Custom DocPerm
rows, and inserting a verbatim copy of any native `(role, permlevel,
if_owner)` combination with zero Custom DocPerm presence. Never touches a
role/permlevel that already has a Custom DocPerm row, even a restrictive
one -- that's either this app's own grant or a legitimate prior
customisation, and either way it's left exactly as is.

**Deliberately scoped to only the doctypes this app's own code has ever
called `_grant_custom_docperm` on** -- not a site-wide sweep. A live site
can easily have its own, unrelated Custom DocPerm customisation on
doctypes like Account/Attendance/Branch (real client configuration via
the Desk's own Role Permissions Manager) -- this script never touches
those, or anything else outside the list below.
"""

import frappe

# Mirrors every _grant_custom_docperm call site in install.py exactly --
# keep this in sync if a future grant_* function touches a new doctype.
AFFECTED_DOCTYPES = (
	"Employee", "Company", "Currency", "Country", "User", "Customer", "Item",
	"Contact", "Address", "Supplier", "Price List", "Item Price", "Quotation",
	"Request for Quotation", "Sales Order", "Sales Invoice", "Payment Entry",
	"Purchase Order", "Supplier Quotation", "Supplier Comparative Statement",
	"Warehouse", "Cost Center", "Mode of Payment", "Payment Terms Template",
	"Shipping Rule", "Workflow", "Workflow State", "Workflow Action Master",
	"UOM", "Sales Taxes and Charges Template", "Purchase Taxes and Charges Template",
	"Terms and Conditions",
)

DOCPERM_COLUMNS = (
	"role", "permlevel", "if_owner", "read", "write", "create", "delete",
	"submit", "cancel", "amend", "report", "export", "import", "share",
	"print", "email", "select",
)


def repair_custom_docperm(dry_run=False):
	result = {}

	for doctype in AFFECTED_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": doctype}):
			# Never had a Custom DocPerm row at all for this doctype -- its
			# native permissions are still fully in effect, nothing lost.
			continue

		existing_keys = {
			(row.role, row.permlevel, row.if_owner)
			for row in frappe.get_all(
				"Custom DocPerm",
				filters={"parent": doctype},
				fields=["role", "permlevel", "if_owner"],
			)
		}

		doctype_doc = frappe.get_cached_doc("DocType", doctype)
		missing = [
			perm
			for perm in (doctype_doc.get("permissions") or [])
			if (perm.role, perm.permlevel or 0, perm.if_owner or 0) not in existing_keys
		]
		if not missing:
			continue

		result[doctype] = [
			f"{p.role} (permlevel {p.permlevel or 0})" for p in missing
		]
		if dry_run:
			continue

		for perm in missing:
			row = {col: perm.get(col) for col in DOCPERM_COLUMNS}
			frappe.get_doc(
				{
					"doctype": "Custom DocPerm",
					"parent": doctype,
					"parenttype": "DocType",
					"parentfield": "permissions",
					**row,
				}
			).insert(ignore_permissions=True)

	if not dry_run:
		frappe.db.commit()
		frappe.clear_cache()

	print(
		f"[smart_app] repair_custom_docperm{' (dry run)' if dry_run else ''}: "
		f"{result or 'nothing to repair'}"
	)
	return result
