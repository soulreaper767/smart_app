# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""One-time load of the firm's supplier database (data/Supplier_Import_2026.csv).

Runs once, automatically, on the first `bench migrate` after this app is
pulled. The importer itself is idempotent (upsert by Supplier name, missing
Country/Supplier Group created first), so re-running it by hand later --
`bench execute smart_app.supplier_import.import_suppliers` -- is always safe.
"""

import frappe

from smart_app.supplier_import import import_suppliers


def execute():
	if not frappe.db.table_exists("Supplier"):
		# ERPNext not installed on this site -- nothing to import into.
		return
	import_suppliers()
