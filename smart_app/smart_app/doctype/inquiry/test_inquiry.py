# Copyright (c) 2026, Smart Chem and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestInquiry(FrappeTestCase):
	def test_naming_series(self):
		self.assertTrue(frappe.get_meta("Inquiry").get_field("naming_series"))
