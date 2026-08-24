app_name = "smart_app"
app_title = "Smart App"
app_publisher = "Smart Chem"
app_description = "Inquiry management and trading workflow automation, built on ERPNext v15."
app_email = "admin@smartchem.local"
app_license = "mit"
app_version = "0.1.0"

# Fixtures
# ------------------
# Roles are hand-authored fixtures so they exist as soon as the app's
# DocTypes (which reference them in their permissions table) are synced.
fixtures = [
	{
		"doctype": "Role",
		"filters": [
			[
				"name",
				"in",
				[
					"Inquiry Manager",
					"Inquiry Officer",
					"Marketer",
					"Inquiry User",
					"Commercial Manager",
					"Commercial Officer",
				],
			]
		],
	}
]

# Installation
# ------------------
after_install = "smart_app.install.after_install"
after_migrate = "smart_app.install.after_migrate"

# Permissions
# ------------------
# Commercial Manager/Officer only ever have a reason to see a *submitted*
# Inquiry -- restricted at the doctype level (list view, reports, kanban,
# search, direct URL access), not just via the Number Card filters.
permission_query_conditions = {
	"Inquiry": "smart_app.smart_app.doctype.inquiry.inquiry.get_permission_query_conditions",
}
has_permission = {
	"Inquiry": "smart_app.smart_app.doctype.inquiry.inquiry.has_permission",
}

# Document Events
# ------------------
doc_events = {
	"Employee": {
		"on_update": [
			"smart_app.smart_app.utils.auto_assign_marketer_role",
			"smart_app.smart_app.utils.sync_marketer_user_permission",
		],
	},
	"User": {
		"validate": [
			"smart_app.smart_app.utils.sync_inquiry_user_role",
			"smart_app.smart_app.utils.sync_module_profile",
		],
		"on_update": [
			"smart_app.smart_app.utils.sync_marketer_user_permission_for_user",
			"smart_app.smart_app.utils.sync_commercial_officer_user_permission",
		],
	},
	"Quotation": {
		"after_insert": "smart_app.smart_app.utils.update_inquiry_on_quotation_created",
	},
	"Request for Quotation": {
		"on_submit": "smart_app.smart_app.utils.update_inquiry_on_rfq_submit",
	},
	"Item": {
		"validate": "smart_app.smart_app.utils.enforce_single_preferred_supplier",
	},
}
