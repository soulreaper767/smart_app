# Copyright (c) 2026, Smart Chem and contributors
# For license information, please see license.txt

"""
DocType class overrides (hooks.py `override_doctype_class`) -- for the rare
case a Custom Field/Property Setter/Client Script/doc_event can't reach,
because the behaviour lives inside a core controller method itself, not
something that runs around it.
"""

from erpnext.buying.doctype.request_for_quotation.request_for_quotation import (
	RequestforQuotation,
)


class CustomRequestForQuotation(RequestforQuotation):
	def on_submit(self):
		"""Core ERPNext's own on_submit unconditionally calls
		self.send_to_supplier() -- so the native "Submit" toolbar button and
		this app's own "Submit & Send to Suppliers" button (RFQ_CLIENT_SCRIPT_JS,
		install.py) both ended up emailing every supplier, and both failed
		outright on any site with no outgoing Email Account configured, even
		for a plain Submit that was never meant to send anything. Sending is
		now opt-in, gated on the `send_email_on_submit` Custom Field
		(setup_quotation_integration) -- ticked only by the "Submit & Send
		to Suppliers" button just before it calls frm.savesubmit(), so it's
		part of that one save+submit request. A plain Submit leaves it
		unchecked and just submits."""
		self.db_set("status", "Submitted")
		for supplier in self.suppliers:
			supplier.email_sent = 0
			supplier.quote_status = "Pending"
		if self.get("send_email_on_submit"):
			self.send_to_supplier()
