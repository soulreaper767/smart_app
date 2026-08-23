// Copyright (c) 2026, Smart Chem and contributors
// For license information, please see license.txt

frappe.ui.form.on("Inquiry", {
	setup: function (frm) {
		frm.set_query("marketer", function () {
			return { query: "smart_app.smart_app.doctype.inquiry.inquiry.get_marketers" };
		});
		frm.set_query("commercial_officer", function () {
			return { query: "smart_app.smart_app.doctype.inquiry.inquiry.get_commercial_officers" };
		});
	},

	onload: function (frm) {
		if (frm.is_new() && !frm.doc.marketer && frappe.user_roles.includes("Marketer")) {
			frappe.call({
				method: "smart_app.smart_app.doctype.inquiry.inquiry.get_my_marketer_employee",
				callback: function (r) {
					if (r.message) {
						frm.set_value("marketer", r.message);
					}
				},
			});
		}

		if (frm.is_new() && !frm.doc.company) {
			const default_company = frappe.defaults.get_user_default("Company");
			if (default_company) {
				frm.set_value("company", default_company);
			}
		}
	},

	refresh: function (frm) {
		frm.trigger("set_status_indicator");
		frm.trigger("show_create_customer_button");
	},

	set_status_indicator: function (frm) {
		const colors = {
			Open: "orange",
			Quotation: "blue",
			Replied: "purple",
			Converted: "green",
			Lost: "red",
			Closed: "gray",
		};
		if (frm.doc.inquiry_status) {
			frm.page.set_indicator(frm.doc.inquiry_status, colors[frm.doc.inquiry_status] || "gray");
		}
	},

	show_create_customer_button: function (frm) {
		if (!frm.is_new() && frm.doc.is_for_referred_party && frm.doc.referred_party_name && !frm.doc.new_customer) {
			frm.add_custom_button(__("Create Customer"), function () {
				frappe.call({
					method: "smart_app.smart_app.doctype.inquiry.inquiry.create_customer_from_referred_party",
					args: { inquiry_name: frm.doc.name },
					freeze: true,
					freeze_message: __("Creating Customer..."),
					callback: function (r) {
						if (r.message) {
							frm.reload_doc();
						}
					},
				});
			}).addClass("btn-primary");
		}
	},

	inquiry_source: function (frm) {
		if (!frm.doc.inquiry_source) {
			frm.set_value("contact_person", null);
			frm.set_value("contact_display", null);
			frm.set_value("contact_email", null);
			frm.set_value("contact_mobile", null);
			frm.set_value("customer_address", null);
			frm.set_value("address_display", null);
			return;
		}
		frappe.call({
			method: "smart_app.smart_app.doctype.inquiry.inquiry.get_customer_contact_details",
			args: { customer: frm.doc.inquiry_source },
			callback: function (r) {
				if (r.message) {
					Object.keys(r.message).forEach((key) => frm.set_value(key, r.message[key]));
				}
			},
		});
	},

	is_for_referred_party: function (frm) {
		frm.trigger("show_create_customer_button");
	},
});
