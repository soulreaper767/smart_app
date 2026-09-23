# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""One-time load of the firm's Customer -> Marketer assignments (see
smart_app.marketer_import for exactly what this does). Idempotent, so
re-running by hand later is always safe:

    bench --site <site> execute smart_app.marketer_import.import_marketers
"""

import frappe

from smart_app.install import setup_customer_marketer_field
from smart_app.marketer_import import import_marketers


def execute():
	if not frappe.db.table_exists("Customer") or not frappe.db.exists("DocType", "Marketer"):
		return

	# Patches run during migrate's schema-update phase, *before* the
	# after_migrate hook that normally creates Customer.marketer (install.
	# setup() -> setup_customer_marketer_field). Without this, import_
	# marketers() throws "Unknown column 'marketer'" the moment it tries to
	# read a field that doesn't exist on this site yet -- ensure it here
	# directly rather than relying on hook ordering.
	setup_customer_marketer_field()
	frappe.db.commit()

	import_marketers()
