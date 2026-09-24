# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
One-shot (but safe to re-run) correction of every Item's Unit of Measure to
Kg, whatever it's currently set to.

    bench --site <site> execute smart_app.item_uom_migration.set_all_items_to_kg --kwargs "{'dry_run': True}"
    bench --site <site> execute smart_app.item_uom_migration.set_all_items_to_kg
    # force through items with existing stock transactions too:
    bench --site <site> execute smart_app.item_uom_migration.set_all_items_to_kg --kwargs "{'force': True}"

Always run with `dry_run: True` first (works with or without `force`) and
read the printed summary before running for real -- this only prints a
preview and writes nothing.

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

**`force=False` (default): items with existing Stock Ledger Entries are
skipped, not changed.** This mirrors core ERPNext's own guard --
`Item.validate_uom()` -> `check_stock_uom_with_bin()` (erpnext/stock/
doctype/item/item.py) throws "cannot be changed directly" the moment a
Stock Ledger Entry or a Bin with reserved/ordered/indented/planned qty
already exists for that Item in a different unit, precisely because every
past transaction's quantity was recorded against the *old* unit. Safe
items go through the normal `doc.save()`, so Frappe's own UOM-conversion
recompute and every other Item validation still runs. Skipped items are
listed by name in the summary.

**`force=True`: changed anyway, deliberately bypassing that guard** -- the
explicit ask this was built for was "future entries have updated UOM"
regardless of what already exists. `stock_uom`/`purchase_uom`/`sales_uom`
are written directly via `frappe.db.set_value` (the only way to get past
`check_stock_uom_with_bin`, the same "raw update, not doc.save()" pattern
currency_migration.py uses for its own must-bypass-validation case),
followed by a raw insert of a `conversion_factor = 1` row for the new
`stock_uom` into the Item's own UOM Conversion Detail child table if one
doesn't already exist (what `add_default_uom_in_conversion_factor_table`
would otherwise do inside the normal save path) -- so every future
Purchase Order/Sales Order/Quotation/Indent line defaulting off this
Item's `stock_uom` gets Kg correctly. **What this does NOT do**: touch any
existing Stock Ledger Entry, Bin balance, or line on an already-created
document -- those keep whatever unit they were actually recorded in; this
only changes the Item master's own default, which is what every *future*
transaction reads. Existing stock reports/balances are not retroactively
reinterpreted, and Bin.actual_qty is left exactly as it was (its number
doesn't change, only what unit newly-created records default to).
"""

import frappe

TARGET_UOM = "Kg"


def _ensure_uom_exists(uom):
	if not frappe.db.exists("UOM", uom):
		frappe.get_doc({"doctype": "UOM", "uom_name": uom}).insert(ignore_permissions=True)


def _has_stock_ledger_entries(item_code):
	return bool(frappe.db.exists("Stock Ledger Entry", {"item_code": item_code}))


def _ensure_uom_conversion_row(item_code, uom):
	"""Direct child-row insert, not a full Item.save() -- add_default_uom_
	in_conversion_factor_table (core) does the equivalent inside the normal
	save path, which force=True deliberately bypasses."""
	if frappe.db.exists("UOM Conversion Detail", {"parent": item_code, "uom": uom}):
		return
	frappe.get_doc(
		{
			"doctype": "UOM Conversion Detail",
			"parent": item_code,
			"parenttype": "Item",
			"parentfield": "uoms",
			"uom": uom,
			"conversion_factor": 1,
		}
	).insert(ignore_permissions=True)


def set_all_items_to_kg(target_uom=TARGET_UOM, dry_run=False, force=False):
	if not dry_run:
		_ensure_uom_exists(target_uom)

	summary = {
		"already_correct": 0,
		"changed": 0,
		"forced": [],
		"blocked_stock_transactions": [],
		"failed": [],
	}

	items = frappe.get_all("Item", fields=["name", "stock_uom", "purchase_uom", "sales_uom"])

	for item in items:
		needs_change = (
			item.stock_uom != target_uom
			or (item.purchase_uom and item.purchase_uom != target_uom)
			or (item.sales_uom and item.sales_uom != target_uom)
		)
		if not needs_change:
			summary["already_correct"] += 1
			continue

		has_stock_txn = item.stock_uom != target_uom and _has_stock_ledger_entries(item.name)

		if has_stock_txn and not force:
			summary["blocked_stock_transactions"].append(item.name)
			continue

		if dry_run:
			summary["changed"] += 1
			if has_stock_txn:
				summary["forced"].append(item.name)
			continue

		if has_stock_txn:
			# Bypasses Item.validate_uom()'s check_stock_uom_with_bin guard on
			# purpose -- see module docstring's force=True section.
			values = {"stock_uom": target_uom}
			if item.purchase_uom and item.purchase_uom != target_uom:
				values["purchase_uom"] = target_uom
			if item.sales_uom and item.sales_uom != target_uom:
				values["sales_uom"] = target_uom
			try:
				frappe.db.set_value("Item", item.name, values, update_modified=False)
				_ensure_uom_conversion_row(item.name, target_uom)
				summary["changed"] += 1
				summary["forced"].append(item.name)
			except Exception as e:
				frappe.db.rollback()
				summary["failed"].append({"item": item.name, "error": str(e)})
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
		f"[smart_app] Item UOM -> {target_uom}{' (dry run)' if dry_run else ''}"
		f"{' (force)' if force else ''}: "
		f"{summary['changed']} changed, {summary['already_correct']} already correct, "
		f"{len(summary['forced'])} forced past existing stock transactions, "
		f"{len(summary['blocked_stock_transactions'])} blocked (existing stock transactions), "
		f"{len(summary['failed'])} failed"
	)
	if summary["forced"]:
		print("[smart_app] Forced (had Stock Ledger Entries): " + ", ".join(summary["forced"]))
	if summary["blocked_stock_transactions"]:
		print(
			"[smart_app] Blocked (has Stock Ledger Entries, re-run with force=True to override): "
			+ ", ".join(summary["blocked_stock_transactions"])
		)
	if summary["failed"]:
		print("[smart_app] Failed:", summary["failed"])

	return summary
