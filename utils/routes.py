from django.urls import reverse_lazy


def routes(request):
    return {
        # ======================================== Auth ========================================
        "dashboard_login_url": reverse_lazy("dashboard_login"),
        "dashboard_logout_url": reverse_lazy("dashboard_logout"),
        "dashboard_profile_url": reverse_lazy("dashboard_profile"),
        "admin_url": reverse_lazy("admin"),
        "site_settings_url": reverse_lazy("site_settings"),
        "pos_url": reverse_lazy("pos"),
        "lock_screen_url": reverse_lazy("lock_screen"),
        "locked_url": reverse_lazy("locked"),
        "unlock_url": reverse_lazy("unlock"),
        "under_maintenance_url": reverse_lazy("under_maintenance"),
        # ======================================== Dashboard ========================================
        "dashboard_url": reverse_lazy("dashboard"),
        # ======================================== UserModel ========================================
        "user_list_url": reverse_lazy("user_list"),
        "user_create_url": reverse_lazy("user_create"),
        "user_export_excel_url": reverse_lazy("user_export_excel"),
        "user_export_pdf_url": reverse_lazy("user_export_pdf"),
        # ======================================== LanguageModel ========================================
        "language_list_url": reverse_lazy("language_list"),
        "language_create_url": reverse_lazy("language_create"),
        # ======================================== TextKeyModel ========================================
        "text_key_list_url": reverse_lazy("text_key_list"),
        "text_key_create_url": reverse_lazy("text_key_create"),
        # ======================================== RoleModel ========================================
        "role_list_url": reverse_lazy("role_list"),
        "role_create_url": reverse_lazy("role_create"),
        "role_export_excel_url": reverse_lazy("role_export_excel"),
        "role_export_pdf_url": reverse_lazy("role_export_pdf"),
    }
