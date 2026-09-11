# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""One-time switch of the site's default currency to USD -- see
smart_app.currency_migration for exactly what this touches and why
(relabel only, including already-submitted Quotation/Supplier Quotation
records). Idempotent, so re-running by hand later is always safe:

    bench --site <site> execute smart_app.currency_migration.switch_default_currency
"""

import frappe

from smart_app.currency_migration import switch_default_currency


def execute():
	if not frappe.db.table_exists("Company"):
		return
	switch_default_currency()
