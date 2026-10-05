# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

LOGISTIC_ROLES = {"Logistic Manager", "Logistic Officer", "System Manager"}


class Shipment(Document):
	def validate(self):
		self.set_status()

	def set_status(self):
		"""Self-healing, forward-only progress indicator -- computed from
		which fields are actually filled in rather than tracked as a
		separate manual field, so it can never drift out of sync with the
		real paperwork. Never regresses: once a later stage's fields are
		filled, earlier ones being edited afterwards (e.g. correcting a
		reference number) doesn't walk the status back down."""
		order = ["Pending Assignment", "Assigned", "In Progress", "Arrived", "Completed"]
		current_index = order.index(self.shipment_status) if self.shipment_status in order else 0

		computed = "Pending Assignment"
		if self.logistic_officer:
			computed = "Assigned"
		if any(
			[
				self.bc_lc_tt_reference,
				self.bc_attachment,
				self.form5_status,
				self.shipment_plan_requested,
				self.shipment_documents_draft,
				self.awb_bl_draft,
				self.drap_noc_attachment,
			]
		):
			computed = "In Progress"
		if self.shipment_arrival_date:
			computed = "Arrived"
		if self.payment_swift_attachment:
			computed = "Completed"

		computed_index = order.index(computed)
		if computed_index > current_index:
			self.shipment_status = computed


@frappe.whitelist()
def get_logistic_officers(doctype, txt, searchfield, start, page_len, filters):
	"""Link-field query: only Users with the Logistic Officer role -- same
	shape as Inquiry's own get_commercial_officers, so a Logistic Manager
	assigning one is only ever offered actual Logistic Officers."""
	return frappe.db.sql(
		"""
		select u.name, u.full_name
		from `tabUser` u
		inner join `tabHas Role` hr on hr.parent = u.name and hr.parenttype = 'User'
		where hr.role = 'Logistic Officer'
			and u.enabled = 1
			and (u.name like %(txt)s or u.full_name like %(txt)s)
		order by u.full_name
		limit %(page_len)s offset %(start)s
		""",
		{"txt": f"%{txt}%", "start": start, "page_len": page_len},
	)


@frappe.whitelist()
def assign_logistic_officer(shipment_name, region=None, logistic_officer=None):
	"""Used by the Assign/Reassign button on the Shipment form -- step 12,
	"Assignment of region wise shipments". Same explicit-role-check +
	ignore_permissions=True pattern as Inquiry's own
	assign_commercial_officer, for the same reason: routing this through
	Document.check_permission's full has_permission -> get_doc_permissions
	-> has_user_permission chain proved unreliable for exactly this kind of
	one-field reassignment in that case, so this sidesteps it entirely."""
	if not (LOGISTIC_ROLES & set(frappe.get_roles(frappe.session.user))):
		frappe.throw(_("Only a Logistic Manager can assign a Logistic Officer."), frappe.PermissionError)

	if logistic_officer and "Logistic Officer" not in frappe.get_roles(logistic_officer):
		frappe.throw(_("{0} does not have the Logistic Officer role.").format(logistic_officer))

	doc = frappe.get_doc("Shipment", shipment_name)
	doc.region = region
	doc.logistic_officer = logistic_officer
	doc.save(ignore_permissions=True)

	return {"region": doc.region, "logistic_officer": doc.logistic_officer, "shipment_status": doc.shipment_status}


@frappe.whitelist()
def create_shipment_from_indent(indent_name):
	"""The "Create > Shipment" button on a submitted Indent (indent.js) --
	Stage E of the trading desk process (logistics: region assignment,
	BC/LC/TT, Form 5, shipment plan/documents, Airway Bill, DRAP NOC, DHL
	arrival, payment swift). Left for the Logistic Manager to assign from
	here, same as a fresh Inquiry starts unassigned."""
	if not frappe.has_permission("Shipment", "create"):
		frappe.throw(_("You do not have permission to create a Shipment."), frappe.PermissionError)

	indent = frappe.get_doc("Indent", indent_name)
	indent.check_permission("read")
	if indent.docstatus != 1:
		frappe.throw(_("Only a submitted Indent can have a Shipment."))

	shipment = frappe.new_doc("Shipment")
	shipment.indent = indent.name
	shipment.insert(ignore_permissions=True, ignore_mandatory=True)
	return shipment.name
