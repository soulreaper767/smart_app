# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
One-shot (but safe to re-run) grant of full access to every document in
this app, at every level, for one named user -- typically a demo account.

    bench --site <site> execute smart_app.grant_full_access.grant_full_access --kwargs "{'user_email': 'demo@demo.com'}"
    # preview only, writes nothing:
    bench --site <site> execute smart_app.grant_full_access.grant_full_access --kwargs "{'user_email': 'demo@demo.com', 'dry_run': True}"

**Not wired into install.py/patches** -- unlike the roles this app's own
setup() grants to TEST_USERS (its own throwaway accounts, created by this
app), elevating a specific *real* user's access is a deliberate one-off
action for whoever is running this, never something that should happen
silently to every site that installs/migrates this app.

"Full access to every document at every level" means three different
things in Frappe, and this grants all three:

1. The **System Manager** role -- Frappe's own conventional "can see and do
   anything" role. Every doctype's own permissions in this app (and
   virtually every ERPNext core doctype) already grants System Manager a
   full create/read/write/delete/submit/cancel/amend row; this app's own
   custom permission hooks (Inquiry's get_permission_query_conditions /
   has_permission, see inquiry.py) also explicitly exempt System Manager
   from every restriction they apply to other roles.

2. Every role this app itself defines (Commercial Manager, Commercial
   Officer, Inquiry Manager, Inquiry Officer, Marketer, Logistic Manager,
   Logistic Officer) -- System Manager alone covers document *permissions*,
   but several of this app's own Client Scripts gate a button's
   *visibility* on one specific named role directly (e.g. Inquiry's own
   "Assign" button checks `frappe.user_roles.includes("Commercial
   Manager")`, not System Manager, and Shipment's own "Assign" button is
   the same shape for Logistic Manager) rather than on the underlying
   doctype permission. Holding every role too is what makes every one of
   those buttons actually show up, not just the data be technically
   reachable through search/report views. The three Manager-tier roles
   (Inquiry/Commercial/Logistic Manager) already give this user the
   highest Permission Level every doctype in this app defines (e.g.
   Inquiry's own Permission-Level-1 contact fields and Permission-Level-2
   `inquiry_status`, both Inquiry-Manager-only) -- there's no separate
   "all permission levels" step beyond holding these roles.

3. **No standing User Permission left scoping them to anything.** This is
   the one easy to miss, and the one that actually bites: granting the
   Commercial Officer role (step 2 above) makes Frappe's own `User.
   on_update` hook (`sync_commercial_officer_user_permission`, utils.py)
   *immediately create* a User Permission restricting this exact user to
   only Inquiries linked to themselves -- the normal, correct behaviour
   for a real Commercial Officer, who should only ever see their own
   deals, but the exact opposite of what a full-access account needs. The
   same thing happens for the Marketer role if this user is ever linked as
   a Marketer record's own `user`. A User Permission applies regardless of
   role -- System Manager does **not** bypass it -- so this is cleaned up
   explicitly, every run, rather than assumed to not exist. This is what
   produces errors like "You are not allowed to access this Inquiry ...
   because it is linked to User 'x' in row N, field Y" or "demo@demo.com
   does not have access to this document" even though every role above is
   already held.
"""

import frappe

ALL_APP_ROLES = (
	"System Manager",
	"Inquiry Manager",
	"Inquiry Officer",
	"Marketer",
	"Commercial Manager",
	"Commercial Officer",
	"Logistic Manager",
	"Logistic Officer",
)


def grant_full_access(user_email, dry_run=False):
	if not frappe.db.exists("User", user_email):
		frappe.throw(f"No User {user_email} on this site -- create the User first, then re-run this.")

	user = frappe.get_doc("User", user_email)
	existing_roles = {r.role for r in user.get("roles")}
	missing_roles = [r for r in ALL_APP_ROLES if r not in existing_roles]

	existing_user_permissions = frappe.get_all(
		"User Permission", filters={"user": user_email}, fields=["name", "allow", "for_value"]
	)

	result = {
		"user": user_email,
		"added_roles": missing_roles,
		"user_type_changed": user.user_type != "System User",
		"enabled_changed": not user.enabled,
		"removed_user_permissions": [
			f"{p.allow}: {p.for_value}" for p in existing_user_permissions
		],
	}

	if dry_run:
		print(f"[smart_app] (dry run) would change for {user_email}: {result}")
		return result

	for role in missing_roles:
		user.append("roles", {"role": role})

	if result["user_type_changed"]:
		# Desk access is required for any of the roles above to mean
		# anything -- a Website User never reaches the Desk UI those
		# permissions/buttons live in, regardless of what's in its roles
		# table.
		user.user_type = "System User"
	if result["enabled_changed"]:
		user.enabled = 1

	user.flags.ignore_password_policy = True
	user.save(ignore_permissions=True)

	# Granting Commercial Officer above (and saving the User doc) is
	# exactly what makes sync_commercial_officer_user_permission create a
	# fresh self-scoping User Permission -- so this has to run *after* the
	# save, not before, or it would just get immediately recreated.
	for perm in frappe.get_all("User Permission", filters={"user": user_email}, pluck="name"):
		frappe.delete_doc("User Permission", perm, ignore_permissions=True)

	frappe.db.commit()

	print(f"[smart_app] granted full access to {user_email}: {result}")
	return result
