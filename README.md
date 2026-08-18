# Smart App

A custom Frappe/ERPNext v15 app that adds an independent **Inquiry Management**
workspace on top of ERPNext — built the same way ERPNext builds Lead /
Opportunity, with naming series, versioning, workflow-driven status, roles,
dashboards, KPIs, kanban and reports.

## Phase 1 scope

- **Inquiry** doctype (naming series `INQ-.YYYY.-`, `track_changes` versioning,
  a `Workflow` for its status field, submittable-free draft-style editing)
- **Inquiry Item** child table (Item + Quantity only — no rates/values)
- Four manager-editable master lists: **Inquiry Shipment Mode**,
  **Inquiry Payment Mode**, **Inquiry Incoterm**, **Inquiry Category**
- Four roles: **Inquiry Manager**, **Inquiry Officer**, **Marketer**, and an
  internal **Inquiry User** umbrella role (see Roles & permissions below)
- A "referred party" scenario with an automated **Create Customer** action
- A dedicated **Smart App** Workspace (shortcuts to every form/report/master
  list, KPIs, charts) plus a shortcut card added to the default **Home**
  workspace, and every other workspace hidden for users whose roles are
  entirely Inquiry-related (see below)
- A **Kanban Board**, a **Dashboard**, 4 **Dashboard Charts**, 4 **Number
  Cards (KPIs)**, 2 **Query Reports**, and 1 **Print Format**
- Everything above is created automatically on `bench install-app` (and kept
  in sync on every `bench migrate`) — no manual setup screens required.

Commission automation is intentionally **out of scope for Phase 1** and will
be layered on in a later phase, once the base Inquiry flow is confirmed.

## Doctype: Inquiry

| Field | Notes |
|---|---|
| `naming_series` | `INQ-.YYYY.-####` |
| `inquiry_date` | defaults to today |
| `inquiry_status` | Open / Quotation / Replied / Converted / Lost / Closed — driven by the **Inquiry Workflow**. Active states (Open/Quotation/Replied) are editable by Inquiry Officer, Marketer or Inquiry Manager; terminal states (Converted/Lost/Closed) are editable by Inquiry Manager only |
| `category` | Link → Inquiry Category (NPD / Commercial, manager-editable) |
| `company` | for multi-company setups |
| `inquiry_source` | Link → Customer — quick-create a new Customer inline, just like any other Link |
| `customer_name` | auto-fetched, read-only |
| `contact_person` / `contact_display` / `contact_email` / `contact_mobile` / `customer_address` / `address_display` | auto-fetched from the Customer's default Contact/Address, **Permission Level 1** — hidden from **Inquiry Officer** and **Marketer**, visible to **Inquiry Manager** / **System Manager** only |
| `is_for_referred_party` + referred party fields | when checked, capture a new party's details; a **Create Customer** button appears to turn them into a real Customer |
| `marketer` | Link → Employee, restricted by query to employees whose linked User has the **Marketer** role; auto-set when a Marketer creates a new Inquiry |
| `inquiry_officer` | Link → User, defaults to the current user |
| `items` | Table → Inquiry Item (Item + Quantity) — used later to request Supplier Quotations |
| `shipment_mode` / `payment_mode` / `incoterm` | Links to the three manager-editable master lists |
| `estimated_value` + `currency` | for pipeline-value KPIs/reports |
| `notes` | free text |

## Roles & permissions

- **System Manager** — full access (standard).
- **Inquiry Manager** — full CRUD on Inquiry incl. Permission Level 1 (contact
  details), plus create/write/delete on all four master lists, plus
  read/write access to the `Workflow`, `Workflow State` and
  `Workflow Action Master` doctypes so the status flow / lists can be
  amended without needing System Manager. Also the only role that can create
  a brand-new Marketer (see below), and can edit an Inquiry in any status
  (see Workflow, below).
- **Inquiry Officer** — can create/read/write Inquiries, but never sees the
  customer's contact details (only the customer's name) because those
  fields sit at Permission Level 1, which this role is not granted.
- **Marketer** — can create Inquiries (auto-assigned as the Marketer) and can
  only read/write Inquiries where they are the assigned Marketer. This is
  enforced two ways: a standard Frappe **User Permission** (Employee →
  current user, scoped to the Inquiry doctype only via `applicable_for`, so
  it never restricts their access to HR/Employee records elsewhere) is kept
  in sync automatically whenever an Employee or User record is saved
  (`smart_app.smart_app.utils`), plus a server-side `validate()` guard in
  `inquiry.py`.
- **Inquiry User** — an internal, non-user-facing umbrella role. It carries no
  DocType permissions of its own; it exists only because the Inquiry
  Workflow's per-state "who can edit while in this state" setting accepts a
  single role, and Inquiry Officer/Marketer/Inquiry Manager are three
  different roles. It's auto-granted to (and revoked from) any User who holds
  one of those three roles, via a `validate` hook on User — you never assign
  it by hand.

### Access to every doctype Inquiry links to

None of the three roles have any permission on the core doctypes Inquiry
links to by default — Customer, Item, Employee, Company, Currency, Country,
User, Contact, Address — which would otherwise make those Link fields
unusable (Frappe requires at least `select` on a doctype to search/pick it
in a Link field, and some client-side lookups need full `read`).
`grant_master_data_access` in `install.py` grants exactly what's needed,
least-privilege:

| Doctype | Inquiry Officer / Marketer / Inquiry Manager |
|---|---|
| Customer | select, read, create (Inquiry Manager also gets write, for corrections) |
| Item | select, read, create (a "New Product Development" Inquiry is often about an item that doesn't exist yet) |
| Employee | select, read, create, write |
| Company, Currency, Country, User | select, read |
| Contact, Address | Inquiry Manager only (select, read) — matches the Permission Level 1 restriction that already hides these fields on the form for the other two roles |

**Creating a new Marketer** uses the exact same "+ Create a New Employee"
quick-create every other Link field in this app already has — click into the
Marketer field, search, and "Create a New Employee" appears at the bottom
like it does for Customer/Item, rather than a bespoke dialog. This is why
Employee gets full create+write above (a wider surface than the
select-only design this app started with, chosen deliberately to match core
ERPNext's own UX). The generic Employee quick-create form has no way to also
assign a role, though, so `auto_assign_marketer_role` (Employee `on_update`,
in `utils.py`) fills that gap: whenever an Employee gets a `user_id` linked
by someone holding an Inquiry role, that user is automatically granted the
Marketer role — since linking a user from this app's context only makes
sense if they're meant to become one. It's left alone for anyone editing
Employee without any Inquiry role (e.g. HR staff), so it never surprises an
unrelated Employee edit.

The "auto-fill my Marketer record" convenience on a *new* Inquiry (for a
user who's already a Marketer) still goes through the whitelisted
`get_my_marketer_employee` rather than a plain `frappe.db.get_list` client
call — no functional difference now that Employee has full read, but it
avoids an unnecessary round trip.

### Focused sidebar (hiding other workspaces)

A **Module Profile** named `Inquiry Team` is created on install and blocks a
curated list of ERPNext/HRMS/Webshop/Payments *business* modules
(`BUSINESS_MODULES_TO_HIDE` in `install.py`: Accounts, Buying, Selling,
Stock, CRM, Support, Projects, Assets, Manufacturing, HR, Payroll, etc). It
is deliberately a **blocklist, not "everything except Smart App"** — an
earlier version tried the latter and it hid the **Home** workspace too. So
does simply blocklisting every module that "sounds like" a business module:
on ERPNext v15 the **Home** workspace's own module is `Setup` (confirmed
against a live site), so `Setup` must never appear in
`BUSINESS_MODULES_TO_HIDE` even though it's also home to the more
sensitive **ERP Settings**/**ERPNext Settings** workspaces — Frappe blocks
by module, not by individual workspace, so those two stay visible in the
sidebar as a cosmetic (not access) tradeoff; the underlying settings
doctypes' permissions are untouched. Any module this list doesn't
recognise — including ones from apps it's never heard of — defaults to
staying **visible**, not hidden. If your site has other business modules
that should also be hidden, add them to `BUSINESS_MODULES_TO_HIDE` and
re-run migrate (the block list is rebuilt from that constant on every run,
so edits self-heal).

The profile is auto-assigned to a User (via the same `validate` hook on
User, in `smart_app.smart_app.utils.sync_module_profile`) **only if every
role that User holds is Inquiry-related** (Inquiry Manager / Inquiry Officer
/ Marketer / Inquiry User, plus the harmless baseline roles every user has
like `All`/`Desk User`). A user who *also* holds an unrelated role — e.g.
someone who is both a Marketer and a Sales User — is left completely
untouched, so their access to Selling/other workspaces is never affected.
System Manager is always excluded. If you need a mixed-role user to get the
focused sidebar too, either broaden the module list, or clear their
`module_profile` field yourself — the sync logic never overwrites a Module
Profile it didn't set itself.

## Workspace shortcuts & links

The **Smart App** workspace ships with:
- **Shortcuts** (the row of buttons at the top): New Inquiry, Inquiry List,
  Inquiry Kanban, Inquiry Report view, Inquiry Dashboard, both Query Reports
  (Marketer Performance, Inquiry Status Summary), Customers, the Inquiry
  Workflow, and all four master lists.
- **Links** (the classic ERPNext grouped-card section further down the
  page, `LINK_CARDS` in `install.py`): every doctype and report the app
  ships with, organised into **Inquiry** (the Inquiry doctype itself),
  **Masters** (all four master lists), and **Reports** (both Query
  Reports) cards.

## Quotation integration

Once an Inquiry's status is **Quotation**, it becomes selectable from the
core **Quotation** form's own "Get Items From" dropdown — click **Get Items
From → Inquiry**, and only Inquiries currently in the Quotation status are
offered (via `get_query_filters`), matching how ERPNext already does this
for Opportunity → Quotation.

This is done without touching any ERPNext source file: `setup_quotation_
integration` in `install.py` adds a **Client Script** on the Quotation
doctype (the button + `erpnext.utils.map_current_doc` call, mirroring
ERPNext's own Opportunity button exactly) and a **Custom Field**
`inquiry` (Link → Inquiry) on Quotation for traceability back to the
source. The server-side mapping — `make_quotation` in `inquiry.py` — pulls
the Customer, Company, Currency and every Inquiry Item (by Item and Qty)
into the new Quotation, mirroring
`erpnext.crm.doctype.opportunity.opportunity.make_quotation`.

## Installation

This repository is the **app source**, not a bench. On your ERPNext v15
server/bench:

```bash
bench get-app smart_app https://github.com/soulreaper767/smart_app.git
bench --site <your-site> install-app smart_app
bench --site <your-site> migrate
bench build
bench restart
```

After install, assign the **Inquiry Manager**, **Inquiry Officer** and
**Marketer** roles to the relevant Users (Marketers should also have an
Employee record linked via `user_id`). Open **Smart App** from the sidebar
(or the shortcut card added to the Home workspace) to start using it.

### If a setup step logs a warning

`install.py` runs every setup step (roles, master data, workflow, kanban
board, charts, KPIs, dashboard, reports, print format, workspace) in its own
try/except and commits independently, so one failing step never blocks the
rest. Check **Error Log** (`bench --site <your-site> console` →
`frappe.get_all("Error Log", limit=5, order_by="creation desc")`, or the Error
Log list in the desk) for the exact step. After pulling an updated version of
this app (`bench get-app smart_app --branch main --overwrite` or `git pull`
inside `apps/smart_app`, then `bench build`), re-run:

```bash
bench --site <your-site> migrate
```

`setup()` is fully idempotent — every step only creates what's missing and
leaves existing records alone, so it's always safe to re-run, including via
`bench --site <your-site> execute smart_app.install.setup` directly if you
want to force it outside of a migrate.

## Roadmap

- Phase 2: commission automation for Marketers based on converted Inquiries.
- Phase 2: Supplier Quotation request automation from the Inquiry `items`
  table (per-item RFQ to suppliers of that item).
