# Smart App

A custom Frappe/ERPNext v15 app that adds an independent **Inquiry Management**
workspace on top of ERPNext — built the same way ERPNext builds Lead /
Opportunity, with naming series, versioning, workflow-driven status, roles,
dashboards, KPIs, kanban and reports.

## Phase 1 scope

- **Inquiry** doctype (naming series `INQ-.YYYY.-`, `track_changes` versioning,
  a `Workflow` for its status field, now **submittable** — see Phase 2)
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
- A **Kanban Board**, a **Dashboard**, 3 **Dashboard Charts**, 3 **Number
  Cards (KPIs)**, 2 **Query Reports**, and 1 **Print Format**
- Everything above is created automatically on `bench install-app` (and kept
  in sync on every `bench migrate`) — no manual setup screens required.

Commission automation for Marketers is intentionally still **out of scope**
and will be layered on in a later phase, once Phase 2's Commercial pipeline
is confirmed. `estimated_value`/`currency` were removed from Inquiry (were
in Phase 1, not needed) — `cleanup_retired_artifacts` in `install.py`
removes the chart/card that were built on them too, on any site that
already had them.

## Phase 2 scope: the Commercial team pipeline

Once an Inquiry is **submitted**, it hands off from the Marketer/Inquiry
Officer side to a separate Commercial team:

1. A **Commercial Manager** sees every submitted Inquiry (assigned and
   unassigned) and assigns a **Commercial Officer** to each one.
2. That Commercial Officer generates a **Quotation** from it (core
   ERPNext's own "Get Items From" mechanism, extended to Inquiry).
3. From the Quotation, they generate a **Request for Quotation** draft —
   auto-populated with every supplier of every item involved (an item
   commonly has several, trader and manufacturer alike) — for review,
   submission, and sending to suppliers (both native RFQ actions).
4. Supplier replies come back as **Supplier Quotation** documents (via the
   RFQ portal, or logged manually), comparable side-by-side with ERPNext's
   own **Supplier Quotation Comparison** report, alongside **Item-wise
   Purchase History** for last-buying context (supplier, date, rate) — both
   core ERPNext reports, just given access, not rebuilt.

New in this phase: **Commercial Manager** / **Commercial Officer** roles, a
test login for each, `commercial_officer` + `commercial_status` fields on
Inquiry, a Commercial overview (KPIs + Kanban + report), and email-footer
branding. All covered in detail further down.

## Doctype: Inquiry

| Field | Notes |
|---|---|
| `naming_series` | `INQ-.YYYY.-####` |
| `inquiry_date` | defaults to today |
| `inquiry_status` | Open / Quotation / Replied / Converted / Lost / Closed — driven by the **Inquiry Workflow**. Every state uses the same `allow_edit` role (the internal Inquiry User umbrella role — see below), so Inquiry Officer/Marketer/Inquiry Manager/Commercial Manager can all edit an Inquiry regardless of its current status; every *transition*, however, is **Inquiry Manager only** (see Status changes below) |
| `status_change_reason` | Small Text, hidden until Status is actually edited, then mandatory — see Status changes below |
| `category` | Link → Inquiry Category (NPD / Commercial, manager-editable) |
| `company` | for multi-company setups |
| `inquiry_source` | Link → Customer — quick-create a new Customer inline, just like any other Link |
| `customer_name` | auto-fetched, read-only |
| `contact_person` / `contact_display` / `contact_email` / `contact_mobile` / `customer_address` / `address_display` | auto-fetched from the Customer's default Contact/Address, **Permission Level 1** — hidden from **Inquiry Officer** and **Marketer**, visible to **Inquiry Manager** / **System Manager** only |
| `is_for_referred_party` + referred party fields | when checked, capture a new party's details; a **Create Customer** button appears to turn them into a real Customer |
| `marketer` | Link → **Marketer** (this app's own doctype, not Employee — see below). Auto-filled from the Customer's own default Marketer if it has one, else from the current user's own Marketer record if they hold the Marketer role; always changeable, and every change is logged (see `marketer_history`) |
| `marketer_history` | Table → Inquiry Marketer Log, read-only — every assignment/reassignment of `marketer`, who changed it, and when |
| `inquiry_officer` | Link → User, defaults to the current user |
| `items` | Table → Inquiry Item (Item + Quantity) — feeds the Quotation/RFQ pipeline below |
| `shipment_mode` / `payment_mode` / `incoterm` | Links to the three manager-editable master lists |
| `amended_from` | standard field for a submittable doctype |
| `commercial_officer` | Link → User, `allow_on_submit` — set by Commercial Manager once submitted; restricted by query to Commercial Officer role holders |
| `commercial_status` | Unassigned / Assigned / Quotation Created / RFQ Created / RFQ Sent — read-only, advanced automatically as the Commercial pipeline progresses, never manually edited. Independent of `inquiry_status` (Open/Quotation/Replied/...) by design: `inquiry_status` tracks the customer-facing conversation (owned by Marketer/Inquiry Officer's Workflow), `commercial_status` tracks the internal Commercial-team pipeline once submitted — they're two separate dimensions, not different labels for the same thing, so `inquiry_status` intentionally never shows "Assigned" |
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
  single role, and Inquiry Officer/Marketer/Inquiry Manager/Commercial
  Manager are four different roles. It's auto-granted to (and revoked from)
  any User who holds one of those four roles, via a `validate` hook on User
  — you never assign it by hand. (Commercial Manager needs it too, since
  they must be able to set `commercial_officer` regardless of what
  `inquiry_status` the Inquiry happens to be in — this is intentionally a
  *separate* trigger set from the one driving the restricted-sidebar Module
  Profile below, so Commercial Manager never gets caught by that.)

### Submitting an Inquiry

Because the Inquiry Workflow is active, Frappe's own client-side workflow
logic **hides the native Submit button** the moment any workflow transition
is available for the current user — which is effectively always, since
every non-terminal state has one. So there's a custom **Submit** button
(`inquiry.js`) that calls the exact same `frm.savesubmit()` the native
button itself would have called — it lives outside the toolbar slot the
workflow JS hides, so it's unaffected. It only shows for a saved, unsaved-
draft Inquiry, and only if the current role actually has `submit`
permission (Inquiry Officer, Marketer, Inquiry Manager, System Manager).

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

**Creating a new Employee who becomes a Marketer** still uses the exact same
"+ Create a New Employee" quick-create every other Link field in this app
already has (from the Employee link field on the Marketer doctype itself,
or from HR). This is why Employee gets full create+write above (a wider
surface than the select-only design this app started with, chosen
deliberately to match core ERPNext's own UX). The generic Employee
quick-create form has no way to also assign a role, though, so
`auto_assign_marketer_role` (Employee `on_update`, in `utils.py`) fills that
gap: whenever an Employee gets a `user_id` linked by someone holding an
Inquiry role, that user is automatically granted the Marketer role — since
linking a user from this app's context only makes sense if they're meant to
become one — and `ensure_marketer_record_for_user` gives them their own
**Marketer** record at the same time (see below), since `Inquiry.marketer`
links to that, not to Employee/User directly. Both are left alone for
anyone editing Employee without any Inquiry role (e.g. HR staff), so this
never surprises an unrelated Employee edit.

The "auto-fill my Marketer record" convenience on a *new* Inquiry (for a
user who's already a Marketer) goes through the whitelisted `get_my_marketer`.

### Marketer doctype, Customer's own default Marketer, and assignment history

**Marketer** is this app's own lightweight master doctype (`marketer_name`,
optional `user` + `employee` cross-references, `is_disabled`) — replacing
`Inquiry.marketer`'s old direct link to Employee, and giving **Customer**
somewhere to record its own default Marketer (a new `marketer` Custom
Field, `setup_customer_marketer_field` in `install.py`) the way core
ERPNext's own Sales Team/Sales Person concept would have, without tying it
to an actual System User — most real-world marketers imported from a
spreadsheet (see below) are just names, not people who log into this site.
Core Customer's own `sales_team` table and `default_sales_partner` field
are hidden (Property Setter, not deleted — existing data and any other
part of the site relying on them is untouched) in favour of this field.

- **Auto-fill priority on a new Inquiry**
  (`set_marketer_from_customer_or_user`, `inquiry.py`): (1) leave alone if
  already set; (2) the selected Customer's own default Marketer, if it has
  one; (3) the current user's own Marketer record, if they hold the
  Marketer role. Always changeable afterwards by anyone who can edit the
  Inquiry.
- **Every assignment/reassignment is logged**, not just overwritten:
  `Inquiry.log_marketer_change` appends a row (previous Marketer, new
  Marketer, changed by, changed on) to the read-only `marketer_history`
  table every time `marketer` actually changes — including on an
  already-submitted Inquiry (also called from `before_update_after_submit`,
  same reasoning as `sync_commercial_status`).
- **Keeping the Customer in step is opt-in, per change, never silent.**
  Changing `marketer` on an Inquiry (`inquiry.js`) checks whether that
  differs from the Customer's own current default and, if so, asks
  ("Update {Customer}'s default Marketer to {Marketer} as well?") before
  calling the whitelisted `update_customer_marketer` — an explicit
  role-check-plus-`ignore_permissions` method (same proven pattern as
  `assign_commercial_officer`), since generic Customer `write` is deliberately
  Inquiry Manager only and this needs to work for Marketer/Inquiry Officer too.
- **Access control still keys off Marketer, correctly.**
  `enforce_marketer_restriction` and the standing User Permission that
  backs it up (`sync_marketer_user_permission`, now hooked to
  `Marketer.on_update` rather than Employee) both compare against the
  current user's own Marketer record (`Marketer.user`), not an Employee
  record — a plain Marketer-role user still only ever sees/edits Inquiries
  where they're the assigned Marketer.
- **Migrating existing data.** `backfill_convert_inquiry_marketer_to_marketer_doctype`
  converts every Inquiry that still names an Employee directly (the old
  shape) into a proper Marketer record (reusing one that already exists
  for that Employee's linked User) and repoints the Inquiry at it — a
  one-time field-target migration via raw SQL, deliberately not a real
  reassignment, so it doesn't log a `marketer_history` entry or prompt
  anyone about Customer. `backfill_cleanup_stale_employee_marketer_permissions`
  removes the old Employee-based User Permissions this superseded.

**Importing the firm's existing Marketer assignments.** The firm's own
`Client Data - 22-07-2026.xlsx` names a Marketer for (almost) every
Customer; `smart_app/data/Customer_Marketer_2026.csv` is the cleaned
extract (its `MARKETER` and `RATING` columns were confirmed identical for
every one of the 433 rows, so only `MARKETER` was kept; `"Hamza Ali khan"`
was folded into the canonical `"Hamza Ali Khan"`, and placeholder values
`"Unassigned"`/`"Direct"` were treated as *no* Marketer, not real names —
8 real Marketers remain). `smart_app.marketer_import.import_marketers`
creates every one of those 8 (deduplicated, never twice) and sets
`Customer.marketer` for every Customer whose name matches a row — runs
once automatically via `smart_app/patches/import_marketers_2026.py`, and
only ever links *existing* Customers; any sheet name that doesn't match
one already in the database is reported, never used to create a new
Customer or silently dropped.

### Status changes are Inquiry Manager only, and always need a reason

Every Inquiry Workflow transition — including ones Inquiry Officer/Marketer
used to be allowed to make themselves (Send for Quotation, Mark as
Replied/Lost) — is now **Inquiry Manager only** (`manager_only` in
`setup_workflow`, `install.py`; the transitions table is fully rebuilt on
every migrate, not just added to, so narrowing this self-heals a site that
already had the older, broader rows). Backed up at the field level too:
`inquiry_status` now sits at **Permission Level 2**, read-only for Inquiry
Officer/Marketer/Commercial Manager/Officer, read+write for Inquiry
Manager/System Manager only — so even if a stale client somehow still
offered a transition to a non-Manager, Frappe's own
`reset_values_if_no_permlevel_access` would silently revert the change on
save rather than actually applying it. Keeping the transitions themselves
Manager-only is what avoids that ever being visible as a confusing
click-does-nothing button in the first place.

Whenever `inquiry_status` actually changes, a reason is mandatory:
`status_change_reason` (Small Text) is hidden on the form until edited —
`inquiry.js`'s own `inquiry_status` field trigger reveals + requires it the
moment the value changes, including via a Workflow transition button
(which sets the field the same way a plain edit would, just before saving,
so the trigger still fires) — and `Inquiry.enforce_status_change_reason`
backs this up server-side (blank reason → blocked, both on a plain save and
on an already-submitted Inquiry's `before_update_after_submit` path).
Confirmed reasons are written to the document's own comment timeline
(`self.add_comment`), not a single field that the next change would just
overwrite.

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
  **Masters** (all four master lists), **Commercial** (Supplier, Quotation,
  Request for Quotation, Supplier Quotation), and **Reports** (both Query
  Reports) cards.
- A **Commercial Team** section: the Commercial Pipeline Kanban (filtered to
  submitted Inquiries only), the Commercial Assignment Overview report, the
  **Suppliers** list, Quotation/Request for Quotation/Supplier Quotation
  lists, the **Commercial Dashboard**, and the two core
  purchase-history/comparison reports (see Phase 2 below).

Every `content.append()` that builds these blocks is guarded by
`_has_content_block` — checking whether that exact header/shortcut/chart/
card is already there before adding it — and `setup_workspace` runs
`_dedupe_content_blocks` on load, since earlier versions of this file
appended some of these unconditionally on every migrate, silently piling up
duplicates each time it ran. That's now fixed and self-healing: the next
migrate cleans up any duplication a site already accumulated.

## Commercial team roles & permissions

- **Commercial Manager** — reads/writes every **submitted** Inquiry (not
  scoped to any one officer), so they can see totals and assign
  `commercial_officer`; drafts are invisible to them entirely (see below).
  Also holds Permission Level 1 read (but not write) on Inquiry — without
  it, saving an Inquiry after setting `commercial_officer` would fail on
  any Inquiry that already had contact details populated, since their
  browser never received those Permission-Level-1 field values and would
  round-trip them as blank, which Frappe treats as an attempted
  unauthorised change and rejects. Deliberately **not** part of the
  Inquiry-role set (Inquiry Manager/Officer/Marketer/Inquiry User) — they're
  a separate, downstream team, so the focused-sidebar Module Profile above
  never applies to them, and they keep normal access to Selling/Buying.

  Assignment itself happens through a dedicated **Assign**/**Reassign**
  button on the Inquiry form (`inquiry.js`, Commercial Manager only), not by
  editing the `commercial_officer` field directly and saving — the field is
  actually set read-only for this role specifically, routing them to the
  button instead. It prompts for a Commercial Officer (same
  `get_commercial_officers` query as the field itself) and calls
  `assign_commercial_officer` (`inquiry.py`) — a dedicated whitelisted
  method with its own explicit role check
  (Commercial Manager/System Manager only) plus a check that the target
  user actually holds the Commercial Officer role, then
  `doc.save(ignore_permissions=True)`. This deliberately bypasses Frappe's
  generic permission stack (`Document.check_permission` ->
  `has_permission` -> `get_doc_permissions` -> `has_user_permission` --
  several layers of evaluation that proved too hard to reason about
  precisely from outside a live site, and an earlier version routed through
  `frappe.client.set_value` straight into that stack, which kept rejecting
  a write that should have been allowed) in favour of the same
  explicit-check-plus-`ignore_permissions` pattern already proven reliable
  elsewhere in this app (`create_marketer`,
  `create_customer_from_referred_party`).

  Getting `commercial_status` to actually flip to "Assigned" took two fixes,
  not one — worth recording both since the first one looked right and
  wasn't:
  1. *(wrong fix, since corrected)* Originally assumed `sync_commercial_status()`
     just wasn't matching a blank/NULL `commercial_status` against the exact
     string `"Unassigned"` (true for any pre-existing Inquiry, since Frappe
     never backfills a newly-added field's default onto old rows) — fixed
     the string comparison, but the button still didn't work.
  2. *(the actual root cause)* `assign_commercial_officer` edits a field and
     calls `doc.save()` on an **already-submitted** Inquiry (`docstatus == 1`,
     staying `1`). Frappe treats that as a distinct `"update_after_submit"`
     action (see `check_docstatus_transition` in `frappe/model/document.py`),
     and `run_before_save_methods` only invokes the controller's `validate()`
     for a plain `"save"` or `"submit"` action — for `"update_after_submit"`
     it calls `before_update_after_submit`/`on_update_after_submit` instead,
     nothing else. So `Inquiry.validate()` — and therefore
     `sync_commercial_status()` — was silently never running at all on the
     Assign button's save, regardless of how correct its internal logic was.
     Fixed by adding `Inquiry.before_update_after_submit()`, which also calls
     `sync_commercial_status()`, so the sync now fires on this path too.

  `backfill_commercial_status` in `install.py` handles the two resulting data
  problems directly on migrate: (a) blank/NULL `commercial_status` on any
  pre-existing Inquiry, normalised to `"Unassigned"`; and (b) any Inquiry
  that was assigned via the button *before* fix #2 above and got stuck with
  a real `commercial_officer` but `commercial_status` still `"Unassigned"` —
  corrected straight to `"Assigned"` (only rows genuinely stuck in that
  combination; never touches one already further along the pipeline).
- **Commercial Officer** — reads only the Inquiries assigned to *them*.
  Enforced the same way as Marketer's restriction, but simpler: since
  `commercial_officer` links directly to **User** (not via Employee), a
  single standing **User Permission** (`allow: User, for_value: <self>,
  applicable_for: Inquiry`) is kept in sync whenever a User is saved
  (`sync_commercial_officer_user_permission` in `utils.py`) — auto-created
  when they hold the role, auto-removed when they don't. Inquiry's own
  `inquiry_officer` field has `ignore_user_permissions` set specifically so
  this restriction never also filters by *that* unrelated field.

**Submitted-only visibility**: neither Commercial role can see a non-
submitted Inquiry at all — not just via the Number Cards' own filters, but
enforced at the doctype level via `get_permission_query_conditions` and
`has_permission` in `inquiry.py` (the same pattern core Frappe uses for
ToDo's owner-only restriction), so it applies uniformly to list views,
reports, Kanban, global search, and opening one directly by URL. Inquiry
Manager/System Manager are exempt even if they also happen to hold a
Commercial role. `has_permission` is deliberately scoped to `ptype ==
"read"` only — an earlier version denied every ptype, which meant it could
also reject a legitimate *write* (Frappe's `Document.check_permission()`
calls this same hook for every permission type it evaluates, including
internally as part of a save) and broke the Assign button with a generic
"does not have doctype access" error. The read-only scoping still fully
achieves the goal, since there's nothing left to additionally restrict once
someone has legitimately reached a document via read access.
  *(Verified this doesn't extend to Marketer/Inquiry Officer's own
  Permission-Level-1 restriction on the same contact-detail fields: Frappe's
  native `reset_values_if_no_permlevel_access` silently reverts a
  restricted field to its DB value on save rather than rejecting the whole
  document — a fundamentally different, safer mechanism than the custom
  hook that broke Commercial Manager.)*
- Both roles are granted `select+read` on Item, Company, Currency, Customer,
  Contact, Address, UOM, Purchase Order, User (Commercial Manager needs this
  to search for a Commercial Officer to assign — the `commercial_officer`
  field itself is further restricted by a `get_commercial_officers` query to
  only offer actual Commercial Officer role holders), and the Sales/Purchase
  Taxes and Terms templates Quotation's own controller commonly touches, plus full
  `select+read+write+create+submit` on **Quotation**, **Request for
  Quotation**, and **Supplier Quotation** (so a phone/email supplier reply
  can be logged manually, not just accepted via the RFQ portal) — none of
  which any role in this app had before. **Item-wise Purchase History** and
  **Supplier Quotation Comparison** (see below) had their own restrictive
  role lists extended too, rather than being rebuilt.

### Test logins

One test user per role, created by `setup_test_users` — **test credentials
only**, meant for verifying each role's permissions end-to-end, not for
production use:

| Email | Password | Role |
|---|---|---|
| `commercialmanager@smartchem.com` | `Test@12345` | Commercial Manager |
| `commercialofficer@smartchem.com` | `Test@12345` | Commercial Officer |
| `inquiryofficer@smartchem.com` | `Test@12345` | Inquiry Officer |
| `inquirymanager@smartchem.com` | `Test@12345` | Inquiry Manager |

The password is only ever set on first creation — a later migrate never
resets it, so changing it afterwards sticks. Disable or reset these before
any real deployment.

### Commercial overview (`setup_commercial_overview` in `install.py`)

- **Number Cards**: Submitted Inquiries, Unassigned Inquiries, Assigned
  Inquiries (all `docstatus = 1`, the "unassigned" one filtered by
  `commercial_officer is not set`), plus **Total Suppliers** (count of
  non-disabled Supplier records — the master the RFQ blast targets, see
  the supplier import below).
- **Kanban Board** "Commercial Pipeline", grouped by `commercial_status`,
  filtered to submitted Inquiries only.
- **Query Report** "Commercial Assignment Overview" — every submitted
  Inquiry with its Commercial Officer and status.
- **Dashboard Chart** "Suppliers by Country" (`setup_commercial_charts`) —
  a Group-By donut over the Supplier master, not Inquiry-based, so it's
  built separately from the Inquiry charts.
- **Dashboard** "Commercial Dashboard" (`setup_commercial_dashboard`) — the
  four Number Cards above and the Suppliers-by-Country chart on one page,
  the Commercial-team counterpart to the Inquiry Dashboard. Linked from the
  workspace's Commercial Team section.

Clicking any of the three Number Cards (Frappe's standard behaviour, not
custom code) navigates to the Inquiry list pre-filtered to that card's exact
criteria — e.g. clicking **Assigned Inquiries** shows only those, and since
`commercial_officer`/`commercial_status` are both list-view columns already,
you see who each one is assigned to and its status right there without
opening each record.

All of these (plus shortcuts to the Suppliers, Quotation, RFQ and Supplier
Quotation lists, the Commercial Dashboard, and the two core reports below)
live under a **Commercial Team** section on the Smart App workspace.

## Quotation → Request for Quotation pipeline

Once an Inquiry is **submitted** and assigned, a Commercial Officer can
start the Quotation from *either* side, both ending up at the same
`make_quotation` mapper:
- From the **Inquiry** itself: **Create → Quotation** (mirrors ERPNext's own
  Opportunity → "Create > Quotation" button exactly, same
  `frappe.model.open_mapped_doc` call).
- From a blank **Quotation**: **Get Items From → Inquiry**, filtered to
  Inquiries assigned to the current Commercial Officer (`commercial_officer`
  = session user, `docstatus = 1`) — mirroring how ERPNext does the same
  thing for Opportunity → Quotation.

From that Quotation, a second button — **Create → Request for Quotation**
— builds a *draft* RFQ: every item carried over (Item, Qty, a 7-day
schedule date, UOM/Stock UOM from the Item master), and every supplier of
every one of those items (`Item.supplier_items` — deliberately *all* of
them, since an item commonly has multiple suppliers, trader and
manufacturer alike, and the RFQ should reach every one) added to the
Suppliers table with their default Contact's email. It's left as a draft
deliberately, so a Commercial Officer can review it before anything reaches
a supplier — most usefully, delete any supplier row they don't actually want
this RFQ to go to (plain grid-row delete, already available on any draft
Request for Quotation they have write access to, no customisation needed).

**It works the other way round too.** Request for Quotation gets its own
`quotation` Custom Field (Link → Quotation, alongside the existing `inquiry`
one) — distinct fields for a reason: `quotation` traces this RFQ to the
specific Quotation it came from, while `inquiry` traces the whole chain
further back to the originating Inquiry, which isn't always the same thing
(an RFQ started via the button below, from a Quotation that wasn't itself
generated from an Inquiry, has `quotation` set but `inquiry` blank).
`backfill_rfq_quotation_links` fills this in for RFQs that already existed
before the field did, wherever exactly one Quotation matches the RFQ's
`inquiry` unambiguously.

The RFQ client script (same file, `RFQ_CLIENT_SCRIPT_JS`) adds the reverse
entry point: a **"Get Items From → Quotation"** button on a *blank* Request
for Quotation, prompting for a Quotation (filtered server-side — see
below) and filling in the form already open in the browser: items,
suppliers, and the `quotation`/`inquiry` traceability fields all populate
together in one action, via plain `frm.set_value` /
`frm.clear_table("items")` + `frm.add_child(...)` calls in the callback —
not `erpnext.utils.map_current_doc`. That was tried first (it's the
mechanism Quotation's own "Get Items From → Inquiry" button uses), but its
`MultiSelectDialog` + `frappe.model.mapper.map_docs` pipeline is built
around picking one-or-more *rows* to pull into an existing table, not
cloning one whole source document's data onto a blank one — it didn't work
reliably for this direction, so this uses direct data-fetch instead. The
server side is `get_request_for_quotation_data` (`inquiry.py`), which
builds an in-memory (never inserted) RFQ using the exact same
`_populate_rfq_suppliers_and_template` logic as `create_request_for_quotation`
and returns it as plain data. `create_request_for_quotation` itself is
unchanged for the other direction (the "Create → Request for Quotation"
button on an already-open Quotation), where there's no blank RFQ open to
fill in place, so creating a fresh document and navigating to it is the
correct behaviour there.

Both `quotation` and `inquiry` are locked to that button as their only
entry point — `quotation` via a **Property Setter** (`read_only: 1`, so it's
still visible as confirmation of what this RFQ was generated from, but
never hand-editable), `inquiry` via a Property Setter (`hidden: 1`, since
it's internal chain-tracing that isn't useful for a Commercial Officer
looking at the form). The Quotation picker itself
(`get_quotations_for_rfq` in `inquiry.py`) only ever offers a Commercial
Officer their **own** Quotations (`owner = ` the current user — Quotation
has no `commercial_officer` field of its own the way Inquiry does, but a
Commercial Officer only ever creates one for an Inquiry already scoped to
themselves, so `owner` is an accurate stand-in); Commercial Manager/System
Manager see every submitted Quotation, for oversight.

**Sending the RFQ.** `setup_quotation_integration` adds one more Client
Script, on Request for Quotation this time: a **"Submit & Send to
Suppliers"** button (visible on any draft that has at least one supplier
row), which — after a one-line confirm — ticks a hidden `send_email_on_submit`
Custom Field and calls `frm.savesubmit()`. A Commercial Officer doesn't need
to separately find and click the native (and easy to miss) "Send Emails to
Suppliers" button afterwards — submitting via this button **is** sending.
That button still exists natively for a later re-send, e.g. if a supplier's
contact was fixed after the fact.

**The native "Submit" toolbar button, deliberately, never sends.** ERPNext's
own `on_submit` for Request for Quotation unconditionally calls
`self.send_to_supplier()` — so on a site with no outgoing Email Account
configured, even a *plain* Submit (not this app's own button at all) failed
outright trying to email suppliers nobody asked to email yet. Since that
call is inside the core controller's own `on_submit` method, no
`doc_events` hook can intercept it — only a real subclass can, so
`CustomRequestForQuotation` (`smart_app/smart_app/overrides.py`, wired via
`override_doctype_class` in `hooks.py`) replaces `on_submit` with the same
status/reset logic, but only calls `send_to_supplier()` when
`send_email_on_submit` is checked. The "Submit & Send to Suppliers" button
is the only place that ever checks it (as part of the same save+submit
request, so it lands correctly regardless of whether the form had other
unsaved edits) — the plain native Submit leaves it unchecked and just
submits, no email, no Email Account required.

Sending (via "Submit & Send to Suppliers") still requires the site's
Portal Settings to have Request for Quotation enabled (ERPNext's own
`check_portal_enabled`) — since every supplier gets a link back to submit
their reply on the buying portal, which is also the "corporate format" body:
`RFQ_EMAIL_TEMPLATE_BODY` in `install.py` renders the actual item table
(name/qty/UOM/required-by) plus that portal link and (for a first-time
supplier contact) a set-password link, in one styled HTML block — using
whatever's already on the RFQ (items, company, supplier) rather than asking
anyone to type a new email each time. This replaced an earlier, broken
version of the same template that referenced `{{ doc.company }}` /
`{{ doc.name }}` against a flat template context (ERPNext's own
`supplier_rfq_mail` renders it against `self.as_dict()` directly, not
wrapped under a `doc` key, so those silently rendered blank) and never
included the portal link at all — meaning a supplier receiving that email
literally had no way to act on it. `setup_email_templates` self-heals this
on migrate for any site that already had the old broken version, but leaves
it alone if a Commercial Manager has since edited the wording by hand from
Settings → Email → Email Template.

**Managing multiple suppliers on an Item.** The native "Supplier Items"
table on Item (Item Supplier child doctype) only ever carried `supplier` +
`supplier_part_no` — enough to *list* several suppliers, but nothing to
actually tell them apart. `setup_item_supplier_customization` in
`install.py` adds two **Custom Fields** to it:
- **Supplier Type** (`supplier_type`, Select: Manufacturer / Trader /
  Distributor / Other) — so a mixed set of sources on one Item stays
  legible at a glance.
- **Preferred** (`is_preferred_supplier`, Check) — flags which one is the
  default source when several are on file. `enforce_single_preferred_supplier`
  (`utils.py`, hooked to Item's `validate`) keeps this to at most one row at
  a time — checking a second one silently unchecks the earlier one rather
  than blocking the save with an error.

This doesn't change how RFQ generation itself works — `create_request_for_quotation`
still blasts every supplier on every item regardless of type or preference,
since "send RFQ to all of them" was the whole point; Preferred/Type are for
a human scanning the Item form, not a filter on who gets contacted.

## Supplier Comparative Statement, and the Purchase Order / Indent gate

Once a Request for Quotation is **submitted** (and sent), suppliers reply
with their own Supplier Quotations — logged either automatically via the
buying portal or manually by a Commercial Officer (see "Sending the RFQ"
above). Comparing those replies and picking a winner per item is a new
doctype, **Supplier Comparative Statement** (`SCS-.YYYY.-.MM.-.####.`,
submittable, `smart_app/smart_app/doctype/supplier_comparative_statement/`):

- **"Create → Supplier Comparative Statement"** on a submitted RFQ builds
  one, or the reverse **"Get Items From → Request for Quotation"** on a
  blank statement pulls the same data in — same shared-builder pattern
  (`_build_comparative_statement_from_rfq`) as every other "X ⇄ Y" pair in
  this app. It doesn't need every supplier to have replied yet: **"Refresh
  Rates"** re-pulls any newly-submitted Supplier Quotation rows against the
  same RFQ at any point while the statement is still a draft, adding only
  genuinely new `(item, supplier)` combinations and never touching a
  selection already made.
- The **Suppliers Sent** table lists every supplier the RFQ went to and
  whether they've quoted yet (`quoted`); the **Rates** table has one row per
  `(item, supplier)` combination that actually quoted, with an **`is_selected`**
  checkbox — tick the winning supplier's row for each item.
  `enforce_single_selection_per_item` (`validate()`) keeps this to at most
  one winner per item, same self-correcting pattern as Item's own Preferred
  Supplier flag.
- **Submitting is the lock.** `before_submit` refuses to submit until
  *every* item on the statement has exactly one selected row — the error
  names which items are still missing a winner. Once submitted, it's
  read-only (`comparative_status = "Completed"`) and becomes the single
  source of truth for that Quotation's actual sourcing.

**Back on the Quotation**, two buttons — **"Create → Purchase Order"** and
**"Create → Indent"** — are both visible as soon as the Quotation itself is
submitted (so they're discoverable), but both call
`_require_comparative_statement` first: if no submitted Supplier
Comparative Statement exists yet for this Quotation, clicking either shows
a clear error explaining what's still needed, rather than either button
being hidden with no explanation. Once a statement is submitted, both work
off `_selected_rows_by_supplier` — the exact same grouping of the exact
same winning selection, item rate/qty/Supplier included, so a Purchase
Order and an Indent for the same Quotation always source identically ("same
links to get items from," verbatim). If the winning selection spans more
than one Supplier (different items awarded to different suppliers), one
Purchase Order *and* one Indent is created **per Supplier** automatically,
and the button navigates to a filtered list instead of a single form; with
one Supplier, it navigates straight to the one document created.

The reverse **"Get Items From → Quotation"** button on a *blank* Indent
(`indent.js`) uses this same gate — it only works when the Comparative
Statement's selection is for a single Supplier; with more than one, it
throws an error pointing at the Quotation's own "Create → Indent" button
instead (which handles the per-Supplier split as above). This is
`get_indent_data_from_quotation`'s entire job now — the standalone
`create_indent_from_quotation` this replaced (which let anyone build an
Indent straight off the Quotation's own original, possibly stale, estimated
rate) is gone.

`grant_commercial_access` gives Commercial Officer/Manager full
`select+read+write+create+submit+print+email+report+export` on both
**Supplier Comparative Statement** and **Purchase Order** (the latter was
previously select+read only, needed upgrading now that the Commercial team
actually raises and submits Purchase Orders from this flow, not just
browses ones raised elsewhere).

## The direct-sale pipeline, Indent, and Commission Invoice

**This app's own revenue is the commission earned on an Indent, never the
trade's own full value** — Smart Chemicals indents/brokers a deal between a
Buyer (Customer) and a Seller (Supplier); the Buyer pays the Supplier
directly for the goods, and the Supplier in turn owes Smart Chemicals a
commission for arranging it. Two consequences run through everything
below: **Indent is sourced from Quotation**, not from a Sales Order/Sales
Invoice for the trade's own value (so it never waits on, or depends on,
whether one even exists), and a dedicated **Commission Invoice** doctype —
not the trade's own Sales Invoice — is what actually posts revenue.

A parallel, optional pipeline still exists for whatever paperwork the
Commercial team wants for the trade itself, forking off the same Quotation
the buying pipeline (Quotation → RFQ → Supplier Quotation) already uses:
**Quotation → Sales Order → Sales Invoice**. Entirely native ERPNext, both
directions at each step (Quotation's own **"Create → Sales Order"**
button and the reverse **"Get Items From → Quotation"** on a blank Sales
Order, both via `erpnext.selling.doctype.quotation.quotation.
make_sales_order`; Sales Order → Sales Invoice equally native) — nothing to
build here beyond the permission grant (`grant_commercial_access` grants
Commercial Officer/Manager full `select+read+write+create+submit+print+
email+report+export` on both) and `inquiry` traceability Custom Fields on
each (hidden, best-effort filled in via `set_inquiry_from_quotation`/
`set_inquiry_from_sales_order` in `utils.py`, reading `prevdoc_docname`/
`sales_order` since neither native mapper knows about a Custom Field added
after the fact). **This pipeline's own Sales Invoice is never treated as
revenue by this app** — nothing here submits, reports on, or ties Indent
status to it; if your process does use it for paper trail, that's between
you and whoever reconciles the books.

(An earlier version of this pipeline built Sales Order directly from
Inquiry with its own mapper/button, and Indent from a submitted Sales
Invoice; both replaced by the above once the commission-only revenue model
was clarified — `setup_sales_pipeline_integration` deletes both stale
Client Scripts from any site that already migrated with either.)

### Doctype: Indent

Smart App's own doctype (naming series `IND-.YYYY.-.MM.-.####.`, e.g.
`IND-2026-09-00001`, submittable, `track_changes`), laid out to match the
firm's own import/export indent document (`indent_template.pdf`)
field-for-field:

| Field | Notes |
|---|---|
| `quotation` | Set once via **"Get Items From > Quotation"** (`read_only`) — the only supported way to populate an Indent; the reverse **"Create > Indent"** button lives on a submitted Quotation itself, gated on a submitted Supplier Comparative Statement (see above) |
| `inquiry` | Best-effort chain-tracing back through the Quotation; hidden (internal only, like RFQ's own) |
| `customer` / `customer_name` / `customer_address_display` | The **BUYER** — fetched from the source Quotation's own `party_name`, `read_only` |
| `supplier` / `supplier_name` / `seller_address_display` | The **SELLER** — auto-filled from the Supplier Comparative Statement's own winning selection for this group of items (`build_indent_doc_for_supplier`), freely editable afterwards if it needs correcting by hand |
| `bank_beneficiary_name` / `bank_name` / `bank_address` / `bank_account_no` / `swift_code` | **Fetched automatically from the selected Supplier** the moment it's picked (`fetch_from`) — see Supplier bank details below |
| `items` (→ Indent Item) | item, product description, **HS Code** (best-effort auto-filled from the Item master's own `customs_tariff_number` if set — see `_best_effort_hs_code` — always plain-editable regardless, since classification can vary by shipment), qty, UOM, unit price, total value |
| `total_qty` / `total_amount` | Computed server-side (`Indent.calculate_totals`, `validate()`) — correct even for a row added via "Get Items From", not dependent on client JS |
| `payment_terms` (→ Inquiry Payment Mode) / `incoterm` (→ Inquiry Incoterm) | Reuse Inquiry's own existing manager-editable master lists — `seed_master_data` adds "DP AT SIGHT"/"CPT" to them, the values the sample template itself uses |
| `lead_time` / `port_of_loading` / `destination` / `origin` / `packing` | All Link → the new **Indent Trade Term** master list (below), each scoped to its own `term_type` |
| `trans_shipment` / `partial_shipment` / `gmp_availability` / `fta_availability` / `ws_availability` | Select, Allowed/Not Allowed or Available/Not Available |
| `tc_name` / `terms` | The standard ERPNext Terms-and-Conditions mechanism (Link → template, Text Editor fetched from it) — **defaults from the source Quotation's own `tc_name`/`terms`** when built via "Get Items From", freely editable afterwards |
| `indent_status` | Hidden until submitted (`depends_on`); then entirely automatic — see Status below |

Every one of the 12 "Terms & Conditions" grid fields from the template is
therefore a dropdown of one kind or another, per the brief — either an
existing master list or the new one below, never free text.

**Indent Trade Term** — one small manager-editable master list (like
Inquiry's own Shipment Mode / Payment Mode / Incoterm / Category) backing
the five Indent fields above that don't map onto an existing list: each
row is a `(term_type, value)` pair, and each Indent field's Link query is
scoped to its own `term_type` (`indent.js`) so the same list serves all
five without needing five separate doctypes. Seeded on install with a
handful of starting values (`INDENT_TRADE_TERM_SEED` in `install.py`);
extend it any time from its own list view.

**Supplier bank details, for the Indent "SELLER"/"BANK DETAILS" sections.**
`setup_supplier_bank_fields` adds `bank_beneficiary_name` / `bank_name` /
`bank_address` / `bank_account_no` / `swift_code` / `seller_address_display`
as plain Custom Fields on **Supplier** (a "Bank Details (for Indent)"
section after `supplier_details`) — Indent's own bank fields simply
`fetch_from` these the moment a Supplier is selected, exactly as asked.
`smart_app.supplier_import` already writes a pipe-delimited "Key: Value |
Key: Value" summary into every imported Supplier's native
`supplier_details` field (Beneficiary Name, Bank Name, Bank Address,
Account No, SWIFT Code, Office/Factory Address); `parse_supplier_details_text`
(`utils.py`) parses exactly that shape, `ensure_supplier_bank_details`
(`Supplier.validate`) self-heals it into the new structured fields whenever
one is still blank (never overwrites a value someone entered directly), and
`backfill_supplier_bank_details` (`install.py`) applies the same parse once
to every Supplier that already existed before these fields shipped — all
345 imported ones included. Going forward, filling these fields in directly
for a brand-new Supplier is the more robust path; the text-parsing is a
one-time convenience, not something new data needs to keep matching.

**Fixed clauses and shipping marks, exactly as asked.** The **For
Banker** / **For Buyer** / **For Shipper** clause blocks and the
**Shipping Marks** wording are hardcoded directly into the **Indent
Standard** print format (`setup_indent_print_format`), not doctype fields —
the whole point is that they read identically on *every* Indent, and a
print format genuinely can't be edited per-document the way a field could
be. The one part of Shipping Marks that does vary — the buyer's name — is
the only piece pulled from the document (`{{ doc.customer_name }}`), same
as the template. The print format covers everything below the letterhead
(seller/buyer, item table, terms grid, bank details, the three clause
blocks, shipping marks, signature line); the logo/company-header band at
the very top of `indent_template.pdf` is left to the site's own **Letter
Head**, not duplicated here. Set as Indent's `default_print_format`
(`indent.json`), so it's what Print/PDF opens with automatically — no
picking it from a list.

**`custom_format = 1` — required, not optional.** Print Format's own
`print_format_type` field is `depends_on: custom_format` in Frappe's core
schema: without `custom_format` checked, Frappe ignores `print_format_type`/
`html` entirely and renders from `format_data` (the drag-and-drop Print
Format Builder's own JSON) instead, which this print format never sets — so
the carefully-built HTML below would have silently never actually rendered.
Both `setup_print_format` (Inquiry) and `setup_indent_print_format` set it
explicitly now, and it's part of the reconcile-on-every-run `changed` check
in each, so a site that already migrated before this was caught self-heals
on the next one.

**Design.** Restyled as a proper corporate document rather than a literal
scan of the source template: one type scale, one border/colour system
throughout (soft slate-grey grid lines, a single deep-teal accent used
consistently for section bars and the totals rule — echoing Smart
Chemicals' own branding without competing with whatever Letter Head sits
above it), and sentence case on the clause paragraphs instead of a wall of
capitals — while keeping the handful of terms the source template itself
calls out in bold ("30 days", "85% shelf-life", "OUR") bold here too.
Currency values are comma-formatted (`"{:,.2f}".format(...)`, not raw
`%.2f`). Bold is reserved for what actually needs emphasis — party names,
the indent number, totals, clause category labels, signature captions —
not every label.

**Single A4 page, every main print format.** Both `setup_print_format`
(Inquiry) and `setup_indent_print_format` (Indent) set an explicit
`@page { size: A4; margin: 8mm 9mm; }` and a compact type scale (body text
around 7–8.3px, section bars ~7.5px, the title ~14px) — small enough that
even Indent's full seller/buyer/items/12-field-terms-grid/bank-details/
three-clause-blocks/shipping-marks/signatures layout fits one page without
overflowing, while keeping the same corporate design system (one accent
colour, bold reserved for what needs it) rather than looking cramped. This
was measured against the *un-letterheaded* page — see below for how the
Letter Head now added on top of every print format changes that budget.

## Corporate Letter Head, default across every print format

`setup_letter_head` turns the firm's own letterhead (source: `Latter
Head.pdf`, supplied at the root of the project) into a real, site-wide
default **Letter Head** doctype record, named `Smart Chemicals Pvt Ltd`:

- The source PDF was rendered at 300 DPI and sliced into two pieces —
  **`smart_app/public/images/letterhead_header.png`** (the top colour
  stripe, logo lockup, tagline, and rule) and **`letterhead_footer.png`**
  (the rule, phone/web/email contact icons, and Lahore/Karachi office
  addresses) — shipped as static app assets, not File-doctype attachments
  (an Attach field is just a path string; nothing in Frappe's own Letter
  Head controller requires an actual File record behind it).
- `source = "HTML"` / `footer_source = "HTML"`, each holding a single
  `<img style="width: 100%;">` tag, **not** Letter Head's built-in
  `source = "Image"` fixed-pixel-width mechanism — every print format in
  this app (and every native ERPNext one) uses a different page margin, so
  a hardcoded pixel width would overflow on some print formats and look
  undersized on others; `width: 100%` always exactly fills whatever
  margin-constrained content width that specific print format ends up
  with, on every page if the document runs long (`repeat_header_footer`).
- `is_default = 1` — the fallback Frappe uses for any document whose own
  `letter_head` field is unset (`get_letter_head`, core `printview.py`).
  `Company.default_letter_head` is also set to the same record, for the
  handful of core doctypes/regional templates that check that field first
  instead. Both **Print Settings** toggles this depends on — "Print with
  letterhead" and "Repeat Header and Footer" — default to checked on a
  fresh site already, but `setup_letter_head` reconciles them explicitly
  too, in case either was ever unchecked by hand.
- **`before_insert` gotcha:** Frappe's own Letter Head controller
  unconditionally forces `source = "Image"` the moment a brand-new record
  is inserted ("for better UX, let user set from attachment") — harmless
  to `content`/`footer` themselves, but it does mean a fresh site needs one
  immediate follow-up save to put `source` back to `"HTML"`, which
  `setup_letter_head` does right after `insert()`. Self-healing on every
  later migrate too if it's ever out of sync.
- The footer only actually renders in the generated **PDF**, not in the
  on-screen Print Preview panel — that's standard Frappe behaviour
  (`footer` HTML Editor's own field description: "Footer will display
  correctly only in PDF"), not something specific to this setup.

### Custom print formats must embed the letterhead themselves

`is_default = 1` alone is **not enough** for either of this app's own print
formats (Indent Standard, Inquiry Standard). Confirmed straight from
Frappe's own print pipeline (`frappe/www/printview.py get_rendered_template`):
for a `format_data`-driven "Standard" print format, Frappe wraps the whole
thing in its own `templates/print_formats/standard.html`, which *does*
render `{{ letter_head }}`/`{{ footer }}` automatically. But for a
**`custom_format = 1`** print format — every print format this app ships —
the template *is* `print_format.html` directly
(`jenv.from_string(print_format.html)`), rendered with
`template.render(args)` and nothing wraps it. `letter_head`/`footer`/
`no_letterhead` are still in `args`, available to reference, but **nothing
renders them unless the template itself does** — which neither of ours
did, so the letterhead silently never appeared on either, `is_default` or
not.

**The fix, and the convention every future custom print format in this app
must follow:** two constants near the top of the "Print Format" section of
`install.py` —

```python
PRINT_FORMAT_LETTERHEAD_HEADER = """
{% if letter_head and not no_letterhead %}
<div id="header-html" class="hidden-pdf">
<div class="letter-head">{{ letter_head }}</div>
</div>
{% endif %}
"""

PRINT_FORMAT_LETTERHEAD_FOOTER = """
{% if footer and not no_letterhead %}
<div id="footer-html" class="visible-pdf">
<div class="letter-head-footer">{{ footer }}</div>
</div>
{% endif %}
"""
```

— copied **verbatim** from Frappe's own `add_header` macro
(`templates/print_formats/standard_macros.html`) and `standard.html`'s own
footer block, including the exact `id="header-html"`/`id="footer-html"` +
`hidden-pdf`/`visible-pdf` + `letter-head`/`letter-head-footer` class
convention — that specific `id` is what
`frappe.utils.pdf.prepare_header_footer` looks for to extract the content
into a *repeating* wkhtmltopdf header/footer (one per page), not just an
inline block that only shows on whichever page it happens to fall on.

Every custom print format's own `html = (...)` splices these in at two
fixed points: `PRINT_FORMAT_LETTERHEAD_HEADER` right after its own
`</style>` (before its title), `PRINT_FORMAT_LETTERHEAD_FOOTER` right
before its outermost closing `</div>`. Since the surrounding markup is a
plain Python `r"""..."""` string (deliberately, so Jinja's own
`{{ doc.field }}` syntax passes through unmangled), splicing in a named
constant means restructuring that single string into a
`(r"""...""" + CONSTANT + r"""...""").strip()` concatenation rather than
one block — see `setup_print_format`/`setup_indent_print_format` for the
exact pattern to copy for the next one.

**wkhtmltopdf reads page margins from `.print-format` CSS, not `@page`.**
This was the other half of the fix, and easy to miss: `frappe.utils.pdf.
get_print_format_styles` parses page-margin/page-size/orientation
specifically off a `.print-format { ... }` rule in the print format's own
`<style>` block — **not** the standard `@page { margin: ...; }` rule (that
one is honoured by a browser/Ctrl+P print pass, never by the server-side
wkhtmltopdf render Frappe's own Print/Download PDF actually uses). Once a
print format extracts `header-html`/`footer-html` the way this one now
does, wkhtmltopdf reserves exactly `margin-top`/`margin-bottom` worth of
page height for them — too little, and the letterhead images overlap the
body content. Both print formats now carry **both** rules side by side,
kept in sync (`@page` for the browser path, `.print-format` for the real
one):

```css
@page { size: A4; margin: 46mm 9mm 38mm; }
.print-format { margin-top: 46mm; margin-bottom: 38mm; margin-left: 9mm; margin-right: 9mm; }
```

**Page-budget tradeoff, worth checking after this change.** 46mm top /
38mm bottom is a deliberately generous reservation for the header/footer
images' own natural height at full page width (~42mm/~35mm) — deliberately
generous because the *exact* width wkhtmltopdf renders `header-html`/
`footer-html` at (full page width vs. the same margin-constrained content
width as the body) isn't something confirmable without an actual
wkhtmltopdf render, which isn't available in this project's own dev
environment; erring generous avoids the images overlapping body content if
it turns out to be the wider case. Combined, that's **84mm of a 297mm A4
page** spent on the letterhead alone, on every page. Both compact
single-page formats above (Indent Standard, Inquiry Standard) were tuned to
fit exactly one A4 page *before* any letterhead was part of that budget —
**print or PDF one of each and confirm it still lands on a single page,
and that the header/footer images don't overlap the body content**; if
either needs adjusting, the fix is tightening that print format's own type
scale/row padding, or trimming the `margin-top`/`margin-bottom` reservation
if it turns out wkhtmltopdf is rendering at the narrower, margin-constrained
width — not touching the letterhead artwork itself.

### Doctype: Commission Invoice

Smart App's own doctype (naming series `COMM-.YYYY.-.MM.-.####.`,
submittable) — **this is what actually posts revenue**, not the Indent's
own trade value or the direct-sale pipeline's Sales Invoice above.

- **Source.** Built from a submitted **Indent** — "Create > Commission
  Invoice" button on Indent (`indent.js`), or the reverse "Get Items From >
  Indent" on a blank Commission Invoice — same shared-builder /
  two-whitelisted-methods shape used throughout this app
  (`_build_commission_invoice_from_indent`, `create_commission_invoice_from_indent`,
  `get_commission_invoice_data_from_indent`, all in `commission_invoice.py`).
  Fetches `indent_value` (the trade's full value, kept only as the base for
  a percentage-of-value component, never itself billed), the Supplier
  (who owes the commission) and Buyer (reference only) from the Indent.
- **Billing a Supplier through Sales Invoice.** Core ERPNext's Sales
  Invoice always bills a *Customer*. `ensure_customer_for_supplier`
  (`utils.py`) auto-creates (once, reused after via the hidden
  `represents_supplier` Custom Field on Customer) a stand-in Customer
  record for the Supplier, purely so there's somewhere for the real
  financial document to point.
- **Commission calculation — mix and match.** A `components` child table
  (**Commission Invoice Component**), each row one of **Percentage of
  Indent Value**, **Rate per UOM** (tied to a specific Indent item,
  optional), or **Fixed Amount** — add as many as needed, e.g. a base
  percentage plus a per-kilogram bonus on one item plus a flat handling
  fee, all summing to `gross_commission` (`Commission Invoice.
  calculate_commission`, server-side, not relied on from client JS).
- **Discount.** `discount_type` (Percentage or Fixed Amount) brings
  `gross_commission` down to `net_commission` — the amount actually
  invoiced.
- **Commission payment terms — the 48-hour SLA.** `payment_due_hours`
  (default 48) + `swift_copy_received_on` (when the Buyer's proof of
  payment to the Supplier was received and forwarded to them as the
  trigger for our own commission) compute `due_date`
  (`calculate_due_date`) — also set as the underlying Sales Invoice's own
  due date, so ageing/overdue reporting is accurate against the actual
  agreed term, not a generic default.
- **On submit, a real Sales Invoice is created and submitted**
  (`create_and_submit_sales_invoice`) — one line, the `Commission Income`
  service item (auto-created once, `ensure_commission_income_item`), rate
  = `net_commission`, billed to the Supplier's stand-in Customer. This is
  what actually hits the GL — native ageing, `outstanding_amount`, and
  status (Unpaid/Overdue/Paid) all come from it for free, fetched back
  onto Commission Invoice's own `outstanding_amount` for a quick glance.
- **Payment, reversal, and write-off — all native ERPNext mechanics,
  reused rather than reinvented.** "Create > Payment" on Commission
  Invoice calls the same `erpnext.accounts.doctype.payment_entry.
  payment_entry.get_payment_entry` core Sales Invoice's own button uses,
  then opens the resulting draft. Cancelling a Commission Invoice cascades
  to cancel its Sales Invoice (`on_cancel`) — Frappe's own `LinkExistsError`
  (e.g. an unreconciled Payment Entry still against it) surfaces as-is
  rather than being swallowed. **"Write Off & Close"**
  (`write_off_and_close`) is for a partial receipt where the balance is
  unlikely to ever come in: builds a *zero-payment* Payment Entry via that
  same `get_payment_entry`, with the whole outstanding amount set as
  `write_off_amount` against the Company's (or Accounts Settings')
  default write-off account — the same mechanism ERPNext's own "Create >
  Payment" dialog uses when you leave a write-off difference — then closes
  both the Commission Invoice and its Indent.
- **Closing the Indent.** `close_indents_on_full_payment` (`utils.py`,
  hooked to `Sales Invoice.on_update` — re-fires whenever a Payment Entry
  reconciles against it) checks the Commission Invoice's own Sales
  Invoice, not the Indent's old direct link: once `outstanding_amount`
  reaches zero, both the Commission Invoice (`commission_status =
  "Received"`) and its Indent (`indent_status = "Closed"`) update
  automatically. No manual button for the "fully received" path; "Write
  Off & Close" is the manual path for "never fully will be."
- **Reminders.** "Send Reminder" (manual, any time) and
  `send_overdue_commission_reminders` (`utils.py`, **daily** via
  `scheduler_events`) both email the Supplier's default Contact —
  automatic for anything actually overdue and still outstanding, so
  nobody has to remember to chase it.
- **Reporting.** "Commission Register" — every non-cancelled Commission
  Invoice with its Indent, Supplier, gross/discount/net/outstanding
  amounts, due date, and status. An "Outstanding Commission" Number Card
  (sum of `outstanding_amount` across everything not yet Received/Written
  Off) sits on the Commercial Dashboard alongside the existing KPIs.

**Status — entirely automatic, no manual button.** `indent_status` is
hidden on the form until the Indent is submitted (`depends_on:
eval:doc.docstatus === 1` — "removed while preparing", since it means
nothing before then). On submit it's set straight to **"In Process"**
(`Indent.on_submit`) — there's no separate "Submitted" state to click
through. From there, the *only* thing that ever moves it to **"Closed"** is
its linked Sales Invoice actually being **paid in full**:
`close_indents_on_full_payment` (`utils.py`, `Sales Invoice.on_update` —
re-fires whenever a Payment Entry reconciles against the invoice and
re-saves it) checks `outstanding_amount == 0` and closes every submitted,
not-yet-closed Indent that names that Sales Invoice. Both this and
`Indent.on_submit` write directly (`frappe.db.set_value` / a plain field
assignment inside the controller, never a manual `doc.save()` called from
outside it) — sidesteps the exact `before_update_after_submit`/`validate()`
-doesn't-run-on-update-after-submit gap documented on
`Inquiry.before_update_after_submit`, rather than risking reproducing it.

**Report.** "Indent Register" (`_create_query_report`, `ref_doctype`
`Indent`) — every non-cancelled Indent with its buyer, seller, currency,
total value and status, granted to Commercial Manager/Officer/System
Manager.

**Surfaced in the workspace**, per this app's own rule of always doing so
for anything new: Commercial Team section shortcuts for Sales Orders,
Sales Invoices, Indents, and the Indent Register report; a "Commercial"
Links card entry; a new **Commercial Dashboard** chart ("Indents by
Status") and Number Card ("Open Indents" — submitted, not yet Closed).

## Multi-price management: a dedicated Price List per Customer/Supplier

"Multiple sales and purchase prices for the same item" is entirely native
ERPNext capability — a **Price List** groups Selling or Buying prices, and
an **Item Price** row (item + price list + rate) is where an actual number
lives — so this app doesn't reinvent it, it wires it up so nobody has to
build it by hand or remember to maintain it:

- **A dedicated Price List per party, automatically.** `ensure_default_price_list`
  (`utils.py`) creates a Price List named `"<party name> - Selling"` /
  `"- Buying"` for every Customer/Supplier, and sets it as their own
  `default_price_list` (a stock field on both doctypes already — no Custom
  Field needed). Hooked to `Customer.after_insert` /
  `Supplier.after_insert`, so it happens the moment a party is created; a
  name collision (two parties sharing a display name) falls back to
  appending the party's own document name to stay unique.
  `backfill_party_price_lists` in `install.py` runs the same thing for
  every Customer/Supplier that already existed before this feature shipped,
  so it isn't limited to records created from here on.
- **Kept current automatically, from data already flowing through the
  pipeline.** `sync_item_prices_from_quotation` (Quotation `on_submit`)
  pushes each item's quoted rate into the Customer's own Price List;
  `sync_item_prices_from_supplier_quotation` (Supplier Quotation
  `on_submit`) does the same into the Supplier's own Price List once their
  RFQ reply is submitted. Both upsert *in place* (`_upsert_item_price`
  looks up the existing Item Price for that item + price list and updates
  its rate) rather than inserting a new dated row every time — Item Price's
  own duplicate check (same item/price list/UOM/valid-from/party) would
  otherwise throw on a same-day repeat and interrupt whatever submit
  triggered it.

Net effect: every Item can carry as many concurrent prices as there are
parties quoting on it — one Selling rate per Customer, one Buying rate per
Supplier — all populated without a single manual Item Price entry, and all
visible from the ordinary Price List / Item Price list views (Commercial
Officer/Manager have select/read/write/create on both, granted in
`grant_commercial_access`). This is a deliberate simplification, not full
multi-currency support: a party's Price List is created once in the site's
global default currency, and a Quotation/Supplier Quotation in a different
currency will still write its rate there as a raw number — fine for a
single-currency trading desk, but worth knowing if you deal in more than
one currency per party.

`commercial_status` advances automatically and only ever forward (never
backward, e.g. a second Quotation created after an RFQ already went out
won't reset it): "Quotation Created" on the Quotation's `after_insert`,
"RFQ Created" once `create_request_for_quotation` builds the draft, "RFQ
Sent" on the RFQ's `on_submit` (submission being the actual precondition
for `send_supplier_emails` to work).

None of this touches any ERPNext source file: `setup_quotation_integration`
in `install.py` adds one **Client Script** on Quotation (both buttons, the
second mirroring ERPNext's own Opportunity → Quotation button exactly via
`erpnext.utils.map_current_doc`) and a **Custom Field** `inquiry` (Link →
Inquiry) on both Quotation and Request for Quotation for traceability. The
server-side mappers — `make_quotation` and `create_request_for_quotation`
in `inquiry.py` — mirror
`erpnext.crm.doctype.opportunity.opportunity.make_quotation` and the RFQ
supplier/contact lookup pattern from ERPNext's own
`request_for_quotation.py`, respectively.

### "Warehouse is mandatory for stock Item"

A stock Item (`is_stock_item = 1`, the default — including every Item
quick-created inline from this app's own Item Link fields, per **Access to
every doctype Inquiry links to** above) trips ERPNext's own
`erpnext.buying.utils.validate_stock_item_warehouse` the instant its row has
a qty but no `warehouse` — thrown as `"Row #{n}: Warehouse is mandatory for
stock Item {item}"` on **every save** (not just submit) of a **Request for
Quotation** or **Supplier Quotation**, since both call this unconditionally
from their own `validate()`. **Quotation itself is unaffected** (Selling
side, no such check).

Two coordinated fixes, both self-healing on migrate:
- `create_request_for_quotation` / `get_request_for_quotation_data`
  (`inquiry.py`) now set `warehouse` on every RFQ item row they build
  (`_append_rfq_item`, shared by both) — the row-level field ERPNext's check
  actually looks at, which this app's own RFQ builders previously left
  blank. `get_request_for_quotation_data`'s response also now carries
  `warehouse` so the reverse "Get Items From → Quotation" button (which
  fills an already-open RFQ client-side, see above) picks it up too.
- `ensure_item_default_warehouse` (`utils.py`, `Item.validate`) gives a
  stock Item a default Warehouse for the site's default Company if it has
  none — core ERPNext's own backfill for this
  (`update_defaults_from_item_group`) only pulls from the *current user's*
  personal default warehouse, which no Inquiry/Commercial role here has ever
  had a reason to set, so a quick-created Item otherwise ends up with an
  empty Item Defaults table. This is what makes a **manually** added
  Supplier Quotation row auto-fill its warehouse the moment the Item is
  picked (core `get_item_details` reads Item Defaults), and it's also the
  fallback `_append_rfq_item` uses for an item that has none of its own.
  `backfill_item_default_warehouse` (`install.py`) applies the same fix to
  every stock Item that already existed before this shipped.

Warehouse resolution (`get_default_warehouse_for_company`, `utils.py`):
Stock Settings' own default warehouse if it belongs to the company, else
that company's auto-created `"Stores"` warehouse, else its first
non-group/non-disabled Warehouse.

## Item master columns everywhere in the pipeline

`setup_item_master_columns` surfaces three Item-master fields as visible
grid columns on every item table across the whole flow — **Inquiry Item**,
**Quotation Item**, **Request for Quotation Item**, and **Supplier
Quotation Item**:

- **UOM** — already exists on every one of these (core ERPNext field), just
  not shown in the grid by default on some of them; a **Property Setter**
  flips `in_list_view` on rather than touching ERPNext's own files.
- **Pharmacopeia** / **Item Grade** — this site's own `custom_pharmacopeia`
  / `custom_item_grade` fields on Item, which don't exist on any of these
  child tables at all by default. Added as fetched **Custom Fields**
  (`fetch_from: <item link fieldname>.custom_pharmacopeia`, etc.) so they
  default from the Item master automatically.

If your site doesn't actually have `custom_pharmacopeia`/`custom_item_grade`
on Item, these columns will just stay blank rather than error — remove them
via Customize Form if you don't want them.

**Editable everywhere, but only from Item's own option list.**
`setup_item_variant_dropdowns` (run right after `setup_item_master_columns`)
turns these from fetched-and-locked into editable **Select** dropdowns —
on those same four child tables, plus **Sales Order Item**, **Sales Invoice
Item**, and **Indent Item** — so a Commercial Officer can correct the
Pharmacopeia/Grade for one particular deal without it forever tracking
whatever the Item master says. The dropdown's own options are mirrored
directly from Item's own `custom_pharmacopeia`/`custom_item_grade` Select
fields (read via `frappe.get_meta("Item")`, not a hand-typed list) onto
every one of the seven child tables, via **Property Setter**, self-healing
on every migrate — so a new Pharmacopeia/Grade is only ever added in one
place (Item itself, e.g. via Customize Form), and it's available at every
transaction level on the next migrate, never as a free-text override that
could drift from what Item actually offers.

**Grid width budget.** A compact grid row only has room for so many columns
before later ones get pushed off-screen — Frappe doesn't wrap or shrink
automatically, it just stops rendering whatever doesn't fit. Quotation
Item's and Supplier Quotation Item's native in_list_view fields (`item_code`,
`qty`, and their `rate`/`amount`) already summed close to a full row on their
own; adding `uom`/`custom_pharmacopeia`/`custom_item_grade` as more
in_list_view columns without shrinking anything pushed `rate`/`amount` — both
later in `field_order` — out of the visible grid entirely, even though both
were already `in_list_view: 1` natively. That's what "rate and value aren't
shown" actually was. Fixed by tightening `item_code`/`qty`/`uom` and the two
custom fields to single-width columns via Property Setter (`rate`/`amount`
kept their native width of 2), freeing enough room for all of them to stay
on-screen together. **Inquiry Item** (this app's own doctype, not core
ERPNext, so no Property Setter needed) got the same column-width rebalance
directly in its JSON, for the same reason — its own `qty` was being pushed
out by the same crowding. **Request for Quotation Item** has neither `rate`
nor `amount` at all — an RFQ is the request sent out *before* any supplier
has quoted a price, so there's nothing to show there.

## Email formats & footer branding

`setup_email_branding` disables Frappe/ERPNext's generic "Sent via ERPNext"
outgoing-email footer (`System Settings.disable_standard_email_footer`) and
sets a placeholder `email_footer_address` that's obviously meant to be
edited — this app has no way to know your company's real name/address, so
it deliberately does not fabricate one. Update it yourself in **System
Settings > Email**. Left alone entirely if you've already customised
`email_footer_address` before installing.

`setup_email_templates` creates one editable **Email Template** — "Request
for Quotation - Supplier Message" — with a generic RFQ subject/body.
`create_request_for_quotation` sets it as the RFQ's own `email_template`
field and calls the RFQ's own `set_data_for_supplier()` method (core
ERPNext's real mechanism for this — Request for Quotation already has an
`email_template` Link field for exactly this purpose), so every RFQ starts
with a ready-to-send message instead of a blank one. Edit its wording any
time from **Settings > Email > Email Template**.

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
Employee record linked via `user_id`). For the Commercial team, either
assign **Commercial Manager**/**Commercial Officer** to real Users, or log
in as the test users created automatically (see Test logins above). Open
**Smart App** from the sidebar (or the shortcut card added to the Home
workspace) to start using it.

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

## Default currency switched to USD

`smart_app.currency_migration.switch_default_currency` runs once,
automatically, via `smart_app/patches/switch_currency_to_usd.py` on the
first `bench migrate` after this app is pulled — switching the site's
default currency to **USD everywhere this app touches currency, including
already-created and already-submitted documents**:

- **Global Defaults** and every **Company**'s `default_currency` — set via
  direct `frappe.db.set_value`, not `doc.save()`, since `Company.validate()`
  refuses to change it once the company has any GL Entry (this was asked
  for despite that).
- Every **Price List** (the ones auto-created per Customer/Supplier, the
  two core Standard Buying/Selling lists, and any other the site has) and
  every **Item Price**'s own stored `currency`.
- **Quotation** and **Supplier Quotation** — `currency` and
  `price_list_currency`, at every docstatus (draft, submitted, cancelled),
  via raw SQL rather than `doc.save()` (which Frappe blocks on an
  already-submitted document by design). **Request for Quotation** has no
  `currency` field of its own — it's a request, sent before any party has
  quoted a price — so there's nothing to change there.

**This is a relabel, not a conversion**: every rate/amount number is left
exactly as typed, only the currency tag changes — `conversion_rate` /
`plc_conversion_rate` / `base_*` fields are deliberately untouched, since
recomputing them without a real exchange rate would be a guess, not a fix.
A Quotation quoted at `5000` in the old currency reads `5000 USD` after
this runs — the number doesn't change, only its label.

**Deliberately not touched**: Purchase Order, Sales Invoice, Purchase
Invoice, Payment Entry, and GL Entry — this app never creates or owns those
records (Purchase Order is granted select+read only, for reference — see
`grant_commercial_access`), and relabeling a *posted* accounting document's
currency without also reworking its GL Entries is a books-integrity risk
outside this app's remit.

Idempotent — checks the current value everywhere before writing, so
re-running is always safe:

```bash
bench --site <your-site> execute smart_app.currency_migration.switch_default_currency
# a different target currency:
bench --site <your-site> execute smart_app.currency_migration.switch_default_currency --kwargs "{'target_currency': 'EUR'}"
```

## Supplier database import

The firm's existing supplier list (`data/Supplier_Import_2026.csv`, 345
suppliers after de-duplication) is loaded automatically — **no manual Data
Import needed**. `smart_app/patches/import_suppliers_2026.py` runs once on the
first `bench migrate` after this app is pulled and calls
`smart_app.supplier_import.import_suppliers`.

It's built so the load can't error out on a missing linked record:

- **Every Country the CSV references is created first if the site doesn't
  have it** (`ensure_country`) — with an ISO code + primary timezone from
  `KNOWN_COUNTRY_DATA`, the same shape ERPNext's own country seed uses, not a
  bare name. `"Sultanate of Oman"` in the source data is mapped to the
  canonical `"Oman"` record (via `COUNTRY_ALIASES`) so the supplier links to a
  complete Country row; if `"Oman"` itself is missing it's created properly
  instead. Two rows have a blank Country cell but an unambiguous India address
  in their details — filled in explicitly via `COUNTRY_BY_SUPPLIER`.
- **Supplier Group**: the CSV leaves it blank for every row, so each supplier
  gets the Buying Settings default, or `"All Supplier Groups"` (created as the
  root group, and set as the Buying Settings default, if the site has none).

**Upsert, not insert-only.** A Supplier already on the site (matched by name)
is updated in place with the CSV's `supplier_details` / country / type; one
that isn't is created. The three duplicate rows in the source collapse to the
first occurrence. `email_id` / `mobile_no` are only set when the supplier has
none yet (they drive primary-contact creation on save), so re-runs don't churn
contacts. Each row is written inside its own savepoint — a bad row goes to
**Error Log** and is skipped, the rest still load.

Re-run any time (idempotent), e.g. after editing the CSV:

```bash
bench --site <your-site> execute smart_app.supplier_import.import_suppliers
# preview only, writes nothing:
bench --site <your-site> execute smart_app.supplier_import.import_suppliers --kwargs "{'dry_run': True}"
```

## Roadmap

- Phase 3: commission automation for Marketers based on converted Inquiries.
