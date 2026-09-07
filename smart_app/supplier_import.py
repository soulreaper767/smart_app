# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
One-shot (but safe to re-run) importer for the firm's supplier database
(``data/Supplier_Import_2026.csv``).

Runs automatically once via ``smart_app/patches/import_suppliers_2026.py`` on
the next ``bench migrate`` after this app is pulled, and can also be re-run by
hand at any time:

    bench --site <site> execute smart_app.supplier_import.import_suppliers
    bench --site <site> execute smart_app.supplier_import.import_suppliers --kwargs "{'dry_run': True}"

Design goals (see the task this was built for):
  * **No import errors.** Every record the CSV *links to* -- Country, Supplier
    Group -- is created properly first if the site doesn't already have it,
    rather than letting a Link validation fail mid-import.
  * **Upsert, not insert-only.** A Supplier that already exists (matched by
    name) is *updated* in place with the CSV's data; one that doesn't is
    created. Re-running never duplicates and always converges the site to the
    full, current dataset.
  * **Row isolation.** Each supplier is written inside its own savepoint, so
    one bad row is logged to Error Log and skipped without aborting the rest.
"""

import csv
import os

import frappe

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "Supplier_Import_2026.csv")

# The CSV's "Supplier Group" column is empty for every row, so every supplier
# gets this group. ERPNext ships "All Supplier Groups" as the root group; if a
# different default is configured in Buying Settings we honour that instead.
FALLBACK_SUPPLIER_GROUP = "All Supplier Groups"

# Country-name variants in the source data that mean an existing, canonical
# ERPNext Country. Mapped to the canonical record (when the site has it) so a
# supplier links to a complete Country row rather than a bare duplicate. If the
# canonical record is also missing, KNOWN_COUNTRY_DATA below is used to create
# the name as written, properly (ISO code + timezone).
COUNTRY_ALIASES = {
	"Sultanate of Oman": "Oman",
}

# ISO 3166-1 alpha-2 codes + primary IANA timezone for every country this
# dataset references, so any that a trimmed-down site is missing gets created
# with the same shape ERPNext's own country seed would give it -- not just a
# lone country_name.
KNOWN_COUNTRY_DATA = {
	"Brazil": {"code": "br", "time_zones": "America/Sao_Paulo"},
	"China": {"code": "cn", "time_zones": "Asia/Shanghai"},
	"France": {"code": "fr", "time_zones": "Europe/Paris"},
	"Germany": {"code": "de", "time_zones": "Europe/Berlin"},
	"Hong Kong": {"code": "hk", "time_zones": "Asia/Hong_Kong"},
	"India": {"code": "in", "time_zones": "Asia/Kolkata"},
	"Mongolia": {"code": "mn", "time_zones": "Asia/Ulaanbaatar"},
	"Oman": {"code": "om", "time_zones": "Asia/Muscat"},
	"Sultanate of Oman": {"code": "om", "time_zones": "Asia/Muscat"},
	"Spain": {"code": "es", "time_zones": "Europe/Madrid"},
	"United Arab Emirates": {"code": "ae", "time_zones": "Asia/Dubai"},
	"United Kingdom": {"code": "gb", "time_zones": "Europe/London"},
}

# Two rows have a blank Country cell but an unambiguous India address in their
# "Supplier Details" (Tamil Nadu / Hyderabad). Filled in explicitly here rather
# than guessed by parsing free text.
COUNTRY_BY_SUPPLIER = {
	"RR LIFE SCIENCES": "India",
	"SEUTIC LABS PVT LTD.": "India",
}


def _norm(value):
	"""Collapse internal whitespace/newlines and trim -- some Supplier Name
	cells in the export contain a literal newline."""
	return " ".join((value or "").split()).strip()


def _read_rows():
	with open(DATA_FILE, encoding="utf-8-sig", newline="") as f:
		return list(csv.DictReader(f))


# ---------------------------------------------------------------------------
# Linked master records: create anything the CSV references that's missing
# ---------------------------------------------------------------------------


def ensure_supplier_group():
	"""Return a usable Supplier Group name, creating the fallback root group if
	the site somehow has none."""
	configured = frappe.db.get_single_value("Buying Settings", "supplier_group")
	if configured and frappe.db.exists("Supplier Group", configured):
		return configured

	if not frappe.db.exists("Supplier Group", FALLBACK_SUPPLIER_GROUP):
		group = frappe.new_doc("Supplier Group")
		group.supplier_group_name = FALLBACK_SUPPLIER_GROUP
		group.is_group = 1
		group.insert(ignore_permissions=True)

	if not configured:
		frappe.db.set_single_value("Buying Settings", "supplier_group", FALLBACK_SUPPLIER_GROUP)

	return FALLBACK_SUPPLIER_GROUP


def ensure_country(raw_name):
	"""Resolve a CSV Country value to an existing Country record name, creating
	it properly if neither the name nor a known canonical alias exists."""
	name = _norm(raw_name)
	if not name:
		return None

	if frappe.db.exists("Country", name):
		return name

	canonical = COUNTRY_ALIASES.get(name)
	if canonical and frappe.db.exists("Country", canonical):
		return canonical

	target = canonical or name
	if frappe.db.exists("Country", target):
		return target

	data = KNOWN_COUNTRY_DATA.get(name) or KNOWN_COUNTRY_DATA.get(target, {})
	country = frappe.new_doc("Country")
	country.country_name = target
	if data.get("code"):
		country.code = data["code"]
	if data.get("time_zones"):
		country.time_zones = data["time_zones"]
	country.insert(ignore_permissions=True)
	print(f"[smart_app] created missing Country: {target}")
	return country.name


def ensure_linked_records(rows):
	"""Create every Country / Supplier Group the import will need up front, so
	no per-row save fails on a missing Link target."""
	group = ensure_supplier_group()

	wanted_countries = set()
	for row in rows:
		name = _norm(row.get("Supplier Name"))
		country = _norm(row.get("Country")) or COUNTRY_BY_SUPPLIER.get(name, "")
		if country:
			wanted_countries.add(country)

	resolved = {}
	for country in sorted(wanted_countries):
		resolved[country] = ensure_country(country)

	frappe.db.commit()
	return group, resolved


# ---------------------------------------------------------------------------
# Suppliers: upsert every row
# ---------------------------------------------------------------------------


def _apply_row(doc, row, is_new, default_group, country):
	name = _norm(row.get("Supplier Name"))
	supplier_type = _norm(row.get("Supplier Type")) or "Company"
	details = (row.get("Supplier Details") or "").strip()
	email = _norm(row.get("Email Id"))
	mobile = _norm(row.get("Mobile No"))

	if is_new:
		doc.supplier_name = name
		doc.supplier_type = supplier_type
		doc.supplier_group = default_group
	else:
		if not doc.supplier_group:
			doc.supplier_group = default_group
		if supplier_type and doc.supplier_type != supplier_type:
			doc.supplier_type = supplier_type

	if country:
		doc.country = country
	if details:
		doc.supplier_details = details
	# email_id / mobile_no drive primary-contact creation on save -- only set
	# them when the supplier has none yet, so re-runs don't churn contacts.
	if email and "@" in email and not doc.get("email_id"):
		doc.email_id = email
	if mobile and not doc.get("mobile_no"):
		doc.mobile_no = mobile


def import_suppliers(dry_run=False):
	"""Create/update every Supplier in the bundled CSV. Idempotent."""
	rows = _read_rows()
	default_group, country_map = ensure_linked_records(rows)

	existing = {
		s.supplier_name: s.name
		for s in frappe.get_all("Supplier", fields=["name", "supplier_name"])
	}

	created, updated, duplicates, errors = [], [], [], []
	seen = set()

	for row in rows:
		name = _norm(row.get("Supplier Name"))
		if not name:
			continue

		key = name.casefold()
		if key in seen:
			duplicates.append(name)
			continue
		seen.add(key)

		country = country_map.get(
			_norm(row.get("Country")) or COUNTRY_BY_SUPPLIER.get(name, ""), None
		)

		is_new = name not in existing
		if dry_run:
			(created if is_new else updated).append(name)
			continue

		savepoint = "smart_app_supplier_import"
		frappe.db.savepoint(savepoint)
		try:
			doc = frappe.new_doc("Supplier") if is_new else frappe.get_doc("Supplier", existing[name])
			_apply_row(doc, row, is_new, default_group, country)
			doc.flags.ignore_mandatory = True
			doc.save(ignore_permissions=True)
			(created if is_new else updated).append(name)
		except Exception:
			frappe.db.rollback(save_point=savepoint)
			errors.append(name)
			frappe.log_error(
				message=frappe.get_traceback(),
				title=f"Smart App supplier import failed: {name[:100]}",
			)

	if not dry_run:
		frappe.db.commit()

	summary = (
		f"[smart_app] supplier import{' (dry run)' if dry_run else ''}: "
		f"{len(created)} created, {len(updated)} updated, "
		f"{len(duplicates)} duplicate rows skipped, {len(errors)} errors"
	)
	print(summary)
	if errors:
		print(f"[smart_app]   errors on: {', '.join(errors)} (see Error Log)")

	return {
		"created": created,
		"updated": updated,
		"duplicates": duplicates,
		"errors": errors,
	}
