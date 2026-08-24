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
| `inquiry_status` | Open / Quotation / Replied / Converted / Lost / Closed — driven by the **Inquiry Workflow**. Every state uses the same `allow_edit` role (the internal Inquiry User umbrella role — see below), so Inquiry Officer/Marketer/Inquiry Manager/Commercial Manager can all edit an Inquiry regardless of its current status; which specific *transitions* are allowed is still role-gated (only Marketer/Inquiry Manager can Convert, only Inquiry Manager can Close/Reopen) |
| `category` | Link → Inquiry Category (NPD / Commercial, manager-editable) |
| `company` | for multi-company setups |
| `inquiry_source` | Link → Customer — quick-create a new Customer inline, just like any other Link |
| `customer_name` | auto-fetched, read-only |
| `contact_person` / `contact_display` / `contact_email` / `contact_mobile` / `customer_address` / `address_display` | auto-fetched from the Customer's default Contact/Address, **Permission Level 1** — hidden from **Inquiry Officer** and **Marketer**, visible to **Inquiry Manager** / **System Manager** only |
| `is_for_referred_party` + referred party fields | when checked, capture a new party's details; a **Create Customer** button appears to turn them into a real Customer |
| `marketer` | Link → Employee, restricted by query to employees whose linked User has the **Marketer** role; auto-set when a Marketer creates a new Inquiry |
| `inquiry_officer` | Link → User, defaults to the current user |
| `items` | Table → Inquiry Item (Item + Quantity) — feeds the Quotation/RFQ pipeline below |
| `shipment_mode` / `payment_mode` / `incoterm` | Links to the three manager-editable master lists |
| `amended_from` | standard field for a submittable doctype |
| `commercial_officer` | Link → User, `allow_on_submit` — set by Commercial Manager once submitted; restricted by query to Commercial Officer role holders |
| `commercial_status` | Unassigned / Assigned / Quotation Created / RFQ Created / RFQ Sent — read-only, advanced automatically as the Commercial pipeline progresses, never manually edited |
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
- A **Commercial Team** section: the Commercial Pipeline Kanban (filtered to
  submitted Inquiries only), the Commercial Assignment Overview report,
  Quotation/Request for Quotation/Supplier Quotation lists, and the two
  core purchase-history/comparison reports (see Phase 2 below).

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
  `create_customer_from_referred_party`). `commercial_status` still flips to
  "Assigned" automatically, since the method runs Inquiry's full save cycle
  server-side including `sync_commercial_status()`.
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
  `commercial_officer is not set`).
- **Kanban Board** "Commercial Pipeline", grouped by `commercial_status`,
  filtered to submitted Inquiries only.
- **Query Report** "Commercial Assignment Overview" — every submitted
  Inquiry with its Commercial Officer and status.

Clicking any of the three Number Cards (Frappe's standard behaviour, not
custom code) navigates to the Inquiry list pre-filtered to that card's exact
criteria — e.g. clicking **Assigned Inquiries** shows only those, and since
`commercial_officer`/`commercial_status` are both list-view columns already,
you see who each one is assigned to and its status right there without
opening each record.

All three (plus shortcuts to Quotation/RFQ/Supplier Quotation lists and the
two core reports below) live under a **Commercial Team** section on the
Smart App workspace.

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
deliberately: submitting it and clicking "Send Supplier Emails" (both
native Request for Quotation actions, which themselves require the site's
Portal Settings to have Request for Quotation enabled) are explicit human
steps, not automated — this reaches external suppliers, so a review
checkpoint stays in the loop.

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
  child tables at all by default. Added as fetched, read-only **Custom
  Fields** (`fetch_from: <item link fieldname>.custom_pharmacopeia`, etc.)
  so they populate automatically and can't drift from the Item master.

If your site doesn't actually have `custom_pharmacopeia`/`custom_item_grade`
on Item, these columns will just stay blank rather than error — remove them
via Customize Form if you don't want them.

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

## Roadmap

- Phase 3: commission automation for Marketers based on converted Inquiries.
