def sidebar(request):
    return {
        "SIDEBAR_MENU": [
            {
                "title": "main",
                "permissions": ["is_staff"],
                "items": [
                    {
                        "label": "dashboard",
                        "url_name": "dashboard",
                        "icon": "ti ti-layout-grid",
                    },
                ],
            },
            {
                "title": "employer_management",
                "permissions": ["view_employermodel", "view_employeemodel"],
                "items": [
                    {
                        "label": "employers",
                        "url_name": "employer_list",
                        "icon": "ti ti-building-store",
                        "permission": "view_employermodel",
                    },
                    {
                        "label": "employees",
                        "url_name": "employee_list",
                        "icon": "ti ti-users",
                        "permission": "view_employeemodel",
                    },
                ],
            },
            {
                "title": "user_management",
                "permissions": [
                    "view_usermodel",
                    "view_rolemodel",
                ],
                "items": [
                    {
                        "label": "users",
                        "url_name": "user_list",
                        "icon": "ti ti-shield-up",
                        "permission": "view_usermodel",
                    },
                    {
                        "label": "roles_and_permissions",
                        "url_name": "role_list",
                        "icon": "ti ti-jump-rope",
                        "permission": "view_rolemodel",
                    },
                ],
            },
            {
                "title": "settings",
                "permissions": [
                    "view_sitemodel",
                    "view_languagemodel",
                    "view_textkeymodel",
                ],
                "items": [
                    {
                        "label": "company_settings",
                        "url_name": "site_settings",
                        "icon": "ti ti-building",
                        "permission": "view_sitemodel",
                    },
                    {
                        "label": "language_settings",
                        "url_name": "language_list",
                        "icon": "ti ti-language",
                        "permission": "view_languagemodel",
                    },
                    {
                        "label": "translate_key_settings",
                        "url_name": "text_key_list",
                        "icon": "ti ti-message-language",
                        "permission": "view_textkeymodel",
                    },
                ],
            },
        ]
    }
