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
			["name", "in", ["Inquiry Manager", "Inquiry Officer", "Marketer", "Inquiry User"]]
		],
	}
]

# Installation
# ------------------
after_install = "smart_app.install.after_install"
after_migrate = "smart_app.install.after_migrate"

# Document Events
# ------------------
doc_events = {
	"Employee": {
		"on_update": "smart_app.smart_app.utils.sync_marketer_user_permission",
	},
	"User": {
		"validate": [
			"smart_app.smart_app.utils.sync_inquiry_user_role",
			"smart_app.smart_app.utils.sync_module_profile",
		],
		"on_update": "smart_app.smart_app.utils.sync_marketer_user_permission_for_user",
	},
}
