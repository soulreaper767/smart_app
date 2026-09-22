# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""One-time load of the firm's Customer -> Marketer assignments (see
smart_app.marketer_import for exactly what this does). Idempotent, so
re-running by hand later is always safe:

    bench --site <site> execute smart_app.marketer_import.import_marketers
"""

import frappe

from smart_app.marketer_import import import_marketers


def execute():
	if not frappe.db.table_exists("Customer") or not frappe.db.exists("DocType", "Marketer"):
		return
	import_marketers()
