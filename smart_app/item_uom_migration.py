# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
One-shot (but safe to re-run) correction of every Item's Unit of Measure to
Kg, whatever it's currently set to.

    bench --site <site> execute smart_app.item_uom_migration.set_all_items_to_kg --kwargs "{'dry_run': True}"
    bench --site <site> execute smart_app.item_uom_migration.set_all_items_to_kg

Always run with `dry_run: True` first and read the printed summary before
running for real -- this only prints a preview and writes nothing.

**Not wired into install.py/patches** -- unlike currency_migration.py, this
doesn't run automatically on migrate. Changing what unit an Item is
actually tracked/transacted in is a real, deliberate data decision, not
something that should happen silently the next time someone pulls this app
and migrates; run it by hand when you're ready.

Scope: `stock_uom` (Item's actual "Default Unit of Measure") on every Item,
plus `purchase_uom`/`sales_uom` (the optional per-Item overrides used
instead of `stock_uom` on Purchase/Sales documents specifically) wherever
either is set to something other than Kg -- changing stock_uom alone and
leaving a "Nos" purchase_uom override in place would mean Purchase Orders
kept transacting in the old unit regardless. Both are cleared/set the same
way: to Kg if populated and different, left alone if already blank (blank
already means "use stock_uom", nothing to fix there).

**Items with existing Stock Ledger Entries are deliberately skipped, not
forced.** This mirrors core ERPNext's own guard (Item.validate() normally
refuses to change `stock_uom` once a Stock Ledger Entry exists for that
Item, precisely because every past transaction's quantity was recorded
against the *old* unit -- relabelling the Item now would make historical
stock reports silently misreport quantities in Kg that were never actually
Kg, with no unit conversion applied). Those Items are reported separately
in the summary so they can be reviewed and corrected by hand (a fresh Item
+ a Stock Reconciliation, generally -- not something this script should
decide on its own). Every other Item goes through the normal
`doc.save()` path (not a raw SQL/`db.set_value` bypass), so Frappe's own
UOM-conversion-factor recompute and any other Item validation still runs.
"""

import frappe

TARGET_UOM = "Kg"


def _ensure_uom_exists(uom):
	if not frappe.db.exists("UOM", uom):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)


def _has_stock_ledger_entries(item_code):
	return bool(frappe.db.exists("Stock Ledger Entry", {"item_code": item_code}))


def set_all_items_to_kg(target_uom=TARGET_UOM, dry_run=False):
	if not dry_run:
		_ensure_uom_exists(target_uom)

	summary = {
		"already_correct": 0,
		"changed": 0,
		"blocked_stock_transactions": [],
		"failed": [],
	}

	items = frappe.get_all(
		"Item", fields=["name", "stock_uom", "purchase_uom", "sales_uom"]
	)

	for item in items:
		needs_change = (
			item.stock_uom != target_uom
			or (item.purchase_uom and item.purchase_uom != target_uom)
			or (item.sales_uom and item.sales_uom != target_uom)
		)
		if not needs_change:
			summary["already_correct"] += 1
			continue

		if item.stock_uom != target_uom and _has_stock_ledger_entries(item.name):
			summary["blocked_stock_transactions"].append(item.name)
			continue

		if dry_run:
			summary["changed"] += 1
			continue

		try:
			doc = frappe.get_doc("Item", item.name)
			doc.stock_uom = target_uom
			if doc.get("purchase_uom") and doc.purchase_uom != target_uom:
				doc.purchase_uom = target_uom
			if doc.get("sales_uom") and doc.sales_uom != target_uom:
				doc.sales_uom = target_uom
			doc.save(ignore_permissions=True)
			summary["changed"] += 1
		except Exception as e:
			frappe.db.rollback()
			summary["failed"].append({"item": item.name, "error": str(e)})

	if not dry_run:
		frappe.db.commit()
		frappe.clear_cache()

	print(
		f"[smart_app] Item UOM -> {target_uom}{' (dry run)' if dry_run else ''}: "
		f"{summary['changed']} changed, {summary['already_correct']} already correct, "
		f"{len(summary['blocked_stock_transactions'])} blocked (existing stock transactions), "
		f"{len(summary['failed'])} failed"
	)
	if summary["blocked_stock_transactions"]:
		print(
			"[smart_app] Blocked (has Stock Ledger Entries, review by hand): "
			+ ", ".join(summary["blocked_stock_transactions"])
		)
	if summary["failed"]:
		print("[smart_app] Failed:", summary["failed"])

	return summary
