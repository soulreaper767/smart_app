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

		// Commercial Manager assigns via the dedicated "Assign"/"Reassign"
		// button (see show_assign_button below), which is guaranteed to
		// work regardless of the Inquiry Workflow's own toolbar behaviour --
		// direct field edit + relying on a native Save button is what broke
		// for this role in the first place, so route them away from that.
		if (frappe.user_roles.includes("Commercial Manager") && !frappe.user_roles.includes("Inquiry Manager")) {
			frm.set_df_property("commercial_officer", "read_only", 1);
		}
	},

	onload: function (frm) {
		if (frm.is_new() && !frm.doc.marketer && frappe.user_roles.includes("Marketer")) {
			frappe.call({
				method: "smart_app.smart_app.doctype.inquiry.inquiry.get_my_marketer",
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
		frm.trigger("show_assign_button");
		frm.trigger("show_submit_button");
		frm.trigger("show_create_quotation_button");

		// status_change_reason only ever makes sense for the *next* edit --
		// a freshly loaded/saved doc has nothing pending, so start hidden
		// and non-mandatory again every time (see the inquiry_status
		// trigger below, which is what actually reveals it).
		frm.set_df_property("status_change_reason", "hidden", 1);
		frm.set_df_property("status_change_reason", "reqd", 0);
	},

	show_assign_button: function (frm) {
		// A dedicated one-click action for Commercial Manager instead of
		// making them edit the commercial_officer field directly and then
		// find a way to save. Calls our own assign_commercial_officer
		// method (explicit role check + ignore_permissions=True server-side)
		// rather than frappe.client.set_value, which routes through
		// Document.check_permission -> has_permission -> get_doc_permissions
		// -> has_user_permission -- several layers of evaluation that proved
		// too hard to reason about precisely from outside a live site, and
		// kept rejecting a write that should have been allowed. This
		// sidesteps that whole stack. commercial_status still flips to
		// "Assigned" automatically via sync_commercial_status(), since the
		// method runs Inquiry's full save cycle server-side.
		if (frm.doc.docstatus === 1 && frappe.user_roles.includes("Commercial Manager")) {
			const label = frm.doc.commercial_officer ? __("Reassign") : __("Assign");
			frm.add_custom_button(label, function () {
				frappe.prompt(
					[
						{
							fieldname: "commercial_officer",
							label: __("Commercial Officer"),
							fieldtype: "Link",
							options: "User",
							reqd: 1,
							default: frm.doc.commercial_officer,
							get_query: function () {
								return {
									query: "smart_app.smart_app.doctype.inquiry.inquiry.get_commercial_officers",
								};
							},
						},
					],
					function (values) {
						frappe.call({
							method: "smart_app.smart_app.doctype.inquiry.inquiry.assign_commercial_officer",
							args: {
								inquiry_name: frm.doc.name,
								commercial_officer: values.commercial_officer,
							},
							freeze: true,
							freeze_message: __("Assigning..."),
							callback: function () {
								frm.reload_doc();
							},
						});
					},
					__("Assign Commercial Officer"),
					__("Assign")
				);
			}).addClass("btn-primary");
		}
	},

	show_create_quotation_button: function (frm) {
		// Mirrors ERPNext's own Opportunity -> "Create > Quotation" button
		// exactly (same frappe.model.open_mapped_doc call), so a Commercial
		// Officer/Manager doesn't have to go the other way round (open a
		// blank Quotation and use "Get Items From") just to start one.
		if (frm.doc.docstatus === 1 && frappe.model.can_create("Quotation")) {
			frm.add_custom_button(
				__("Quotation"),
				function () {
					frappe.model.open_mapped_doc({
						method: "smart_app.smart_app.doctype.inquiry.inquiry.make_quotation",
						frm: frm,
					});
				},
				__("Create")
			);
		}
	},

	show_submit_button: function (frm) {
		// The Inquiry Workflow hides the native Submit button whenever any
		// workflow transition is available (Frappe's own workflow.js hides
		// btn_primary/btn_secondary as soon as one action is shown) -- which
		// is effectively always, since every active state has an outgoing
		// transition. A custom button lives outside that toolbar slot, so it
		// is never touched by that hide-logic; frm.savesubmit() is the exact
		// same call the native Submit button itself makes.
		if (!frm.is_new() && frm.doc.docstatus === 0 && frappe.model.can_submit(frm.doctype)) {
			frm.add_custom_button(__("Submit"), function () {
				frm.savesubmit();
			}).addClass("btn-primary");
		}
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
				if (!r.message) return;
				// marketer is handled separately from the rest -- only set
				// it when this Customer actually has a default (a blank
				// result means "no default on file", not "clear whatever
				// Marketer is already on this Inquiry").
				const { marketer, ...rest } = r.message;
				Object.keys(rest).forEach((key) => frm.set_value(key, rest[key]));
				if (marketer) {
					frm.set_value("marketer", marketer);
				}
			},
		});
	},

	marketer: function (frm) {
		// Keeping the Customer's own default Marketer in step is opt-in,
		// per change, never automatic -- see update_customer_marketer
		// (inquiry.py). Every change is logged regardless (marketer_history,
		// Inquiry.log_marketer_change), independent of this prompt.
		if (!frm.doc.marketer || !frm.doc.inquiry_source) return;

		frappe.db.get_value("Customer", frm.doc.inquiry_source, "marketer").then((r) => {
			const current = r.message && r.message.marketer;
			if (current === frm.doc.marketer) return;
			frappe.confirm(
				__("Update {0}'s default Marketer to {1} as well?", [frm.doc.customer_name || frm.doc.inquiry_source, frm.doc.marketer]),
				function () {
					frappe.call({
						method: "smart_app.smart_app.doctype.inquiry.inquiry.update_customer_marketer",
						args: { customer: frm.doc.inquiry_source, marketer: frm.doc.marketer },
					});
				}
			);
		});
	},

	inquiry_status: function (frm) {
		// Reveal + require the reason the moment Status is actually edited
		// (including via a Workflow transition button, which sets this
		// field's value the same way a plain field edit would before
		// saving) -- see enforce_status_change_reason (inquiry.py) for the
		// server-side backstop, and refresh above for why this resets.
		frm.set_df_property("status_change_reason", "hidden", 0);
		frm.set_df_property("status_change_reason", "reqd", 1);
		frm.scroll_to_field("status_change_reason");
	},

	is_for_referred_party: function (frm) {
		frm.trigger("show_create_customer_button");
	},
});
