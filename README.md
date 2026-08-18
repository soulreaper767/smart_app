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
- Three roles: **Inquiry Manager**, **Inquiry Officer**, **Marketer**
- A "referred party" scenario with an automated **Create Customer** action
- A dedicated **Smart App** Workspace (shortcuts, KPIs, charts) plus a
  shortcut card added to the default **Home** workspace
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
| `inquiry_status` | Open / Quotation / Replied / Converted / Lost / Closed — driven by the **Inquiry Workflow** |
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
  amended without needing System Manager.
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
try/except and commits independently, so one failing step (e.g. a Workspace
JSON-schema difference on a future Frappe point release) never blocks the
rest. Check **Error Log** (`bench --site <your-site> console` →
`frappe.get_all("Error Log", limit=5, order_by="creation desc")`, or the Error
Log list in the desk) for the exact step and re-run
`bench --site <your-site> execute smart_app.install.setup` after fixing/
upgrading — it's fully idempotent and safe to re-run any time.

## Roadmap

- Phase 2: commission automation for Marketers based on converted Inquiries.
- Phase 2: Supplier Quotation request automation from the Inquiry `items`
  table (per-item RFQ to suppliers of that item).
