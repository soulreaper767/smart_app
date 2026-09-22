# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
One-time (but safe to re-run) import of the firm's Marketer assignments per
Customer, from data/Customer_Marketer_2026.csv (extracted from the firm's
own "Client Data - 22-07-2026.xlsx" -- see its MARKETER column; the sheet's
own RATING column was confirmed identical to MARKETER for every row, so
only MARKETER was kept).

    bench --site <site> execute smart_app.marketer_import.import_marketers

Runs once automatically via smart_app/patches/import_marketers_2026.py on
the first `bench migrate` after this app is pulled.

Creates every distinct Marketer name in the sheet (already deduplicated --
one casing variant, "Hamza Ali khan", was folded into "Hamza Ali Khan"
while extracting the CSV; "Unassigned"/"Direct" mean *no* Marketer, not a
real name, and were dropped the same way), then sets Customer.marketer for
every Customer whose name matches a row. Only ever links *existing*
Customers -- a name that doesn't match one is reported, not silently
skipped, and never used to create a new Customer.
"""

import csv
import os

import frappe

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "Customer_Marketer_2026.csv")


def _read_rows():
	with open(DATA_FILE, encoding="utf-8-sig", newline="") as f:
		return list(csv.DictReader(f))


def import_marketers():
	rows = _read_rows()

	marketer_names = sorted({(row.get("Marketer") or "").strip() for row in rows if row.get("Marketer")})
	created_marketers = []
	for name in marketer_names:
		if not frappe.db.exists("Marketer", name):
			frappe.get_doc({"doctype": "Marketer", "marketer_name": name}).insert(ignore_permissions=True)
			created_marketers.append(name)

	linked, already_set, unmatched = [], [], []
	for row in rows:
		customer_name = (row.get("Customer Name") or "").strip()
		marketer = (row.get("Marketer") or "").strip()
		if not customer_name or not marketer:
			continue

		customer = frappe.db.get_value("Customer", {"customer_name": customer_name}, "name")
		if not customer:
			unmatched.append(customer_name)
			continue

		if frappe.db.get_value("Customer", customer, "marketer"):
			already_set.append(customer_name)
			continue

		frappe.db.set_value("Customer", customer, "marketer", marketer, update_modified=False)
		linked.append(customer_name)

	frappe.db.commit()
	frappe.clear_cache()

	print(
		f"[smart_app] marketer import: {len(created_marketers)} Marketer(s) created, "
		f"{len(linked)} Customer(s) linked, {len(already_set)} already had a Marketer, "
		f"{len(unmatched)} Customer name(s) not found in this site"
	)
	if unmatched:
		print(f"[smart_app]   not found (review/link manually): {', '.join(unmatched)}")

	return {
		"created_marketers": created_marketers,
		"linked": linked,
		"already_set": already_set,
		"unmatched": unmatched,
	}
