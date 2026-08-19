from django.contrib import admin
from django.urls import include, path, re_path
from django.conf.urls.static import static
from django.conf import settings
from views.dashboard import (
    auth_views,
    user_views,
    role_views,
    language_views,
    text_key_views,
    employer_views,
    employee_views,
    attachment_views,
    bulk_views,
)
from views.dashboard import page_views as dashboard_page_views

handler500 = dashboard_page_views.internal_server_error
urlpatterns = (
    [
        path(settings.ADMIN_LOGIN_URL, admin.site.urls),
        # ================================================================================================
        # DASHBOARD URL
        # ================================================================================================
        path("", dashboard_page_views.dashboard, name="dashboard"),
        path("dashboard/bulk/delete/<str:model_name>/", bulk_views.bulk_delete, name="bulk_delete"),
        path("dashboard/bulk/export/<str:model_name>/<str:file_format>/", bulk_views.bulk_export, name="bulk_export"),
        
        path(
            "under-maintenance/",
            dashboard_page_views.under_maintenance,
            name="under_maintenance",
        ),
        path(
            settings.DASHBOARD_LOGIN_URL,
            auth_views.dashboard_login,
            name="dashboard_login",
        ),
        path(
            settings.DASHBOARD_LOGOUT_URL,
            auth_views.dashboard_logout,
            name="dashboard_logout",
        ),
        path("dashboard/welcome/", auth_views.dashboard_welcome, name="dashboard_welcome"),
        path("dashboard/profile/", auth_views.profile, name="dashboard_profile"),
        path(
            "dashboard/site-settings/",
            dashboard_page_views.site_settings,
            name="site_settings",
        ),
        # ========================
        # UserModel
        # ========================
        path("dashboard/user/list/", user_views.user_list, name="user_list"),
        path("dashboard/user/create/", user_views.user_create, name="user_create"),
        path(
            "dashboard/user/update/<uuid:pk>/",
            user_views.user_update,
            name="user_update",
        ),
        path(
            "dashboard/user/delete/<uuid:pk>/",
            user_views.user_delete,
            name="user_delete",
        ),
        path(
            "dashboard/user/export/excel/",
            user_views.user_export_excel,
            name="user_export_excel",
        ),
        path(
            "dashboard/user/export/pdf/",
            user_views.user_export_pdf,
            name="user_export_pdf",
        ),
        # ========================
        # RoleModel
        # ========================
        path("dashboard/role/list/", role_views.role_list, name="role_list"),
        path("dashboard/role/create/", role_views.role_create, name="role_create"),
        path(
            "dashboard/role/update/<uuid:pk>/",
            role_views.role_update,
            name="role_update",
        ),
        path(
            "dashboard/role/delete/<uuid:pk>/",
            role_views.role_delete,
            name="role_delete",
        ),
        path(
            "dashboard/role/export/excel/",
            role_views.role_export_excel,
            name="role_export_excel",
        ),
        path(
            "dashboard/role/export/pdf/",
            role_views.role_export_pdf,
            name="role_export_pdf",
        ),
        # ========================
        # LanguageModel
        # ========================
        path(
            "dashboard/language/list/",
            language_views.language_list,
            name="language_list",
        ),
        path("set-language/", language_views.set_language, name="set_language"),
        path(
            "dashboard/language/create/",
            language_views.language_create,
            name="language_create",
        ),
        path(
            "dashboard/language/update/<uuid:pk>/",
            language_views.language_update,
            name="language_update",
        ),
        path(
            "dashboard/language/delete/<uuid:pk>/",
            language_views.language_delete,
            name="language_delete",
        ),
        # ========================
        # TextKeyModel
        # ========================
        path(
            "dashboard/text-key/list/",
            text_key_views.text_key_list,
            name="text_key_list",
        ),
        path(
            "dashboard/text-key/create/",
            text_key_views.text_key_create,
            name="text_key_create",
        ),
        path(
            "dashboard/text-key/update/<uuid:pk>/",
            text_key_views.text_key_update,
            name="text_key_update",
        ),
        path(
            "dashboard/text-key/delete/<uuid:pk>/",
            text_key_views.text_key_delete,
            name="text_key_delete",
        ),
        path(
            "dashboard/translations/save/",
            text_key_views.save_translation,
            name="save_translation",
        ),
        # ========================
        # EmployerModel
        # ========================
        path(
            "dashboard/employer/list/",
            employer_views.employer_list,
            name="employer_list",
        ),
        path(
            "dashboard/employer/create/",
            employer_views.employer_create,
            name="employer_create",
        ),
        path(
            "dashboard/employer/update/<uuid:pk>/",
            employer_views.employer_update,
            name="employer_update",
        ),
        path(
            "dashboard/employer/detail/<uuid:pk>/",
            employer_views.employer_detail,
            name="employer_detail",
        ),
        path(
            "dashboard/employer/delete/<uuid:pk>/",
            employer_views.employer_delete,
            name="employer_delete",
        ),
        path(
            "dashboard/employer/export/excel/",
            employer_views.employer_export_excel,
            name="employer_export_excel",
        ),
        path(
            "dashboard/employer/export/pdf/",
            employer_views.employer_export_pdf,
            name="employer_export_pdf",
        ),
        path(
            "dashboard/employer/search/",
            employer_views.employer_search,
            name="employer_search",
        ),
        path("dashboard/business-type/quick-add/", employer_views.business_type_quick_add, name="business_type_quick_add"),
        path("dashboard/employer/quick-add/", employer_views.employer_quick_add, name="employer_quick_add"),
        # ========================
        # EmployeeModel
        # ========================
        path(
            "dashboard/employee/list/",
            employee_views.employee_list,
            name="employee_list",
        ),
        path(
            "dashboard/employee/create/",
            employee_views.employee_create,
            name="employee_create",
        ),
        path(
            "dashboard/employee/update/<uuid:pk>/",
            employee_views.employee_update,
            name="employee_update",
        ),
        path(
            "dashboard/employee/detail/<uuid:pk>/",
            employee_views.employee_detail,
            name="employee_detail",
        ),
        path(
            "dashboard/employee/delete/<uuid:pk>/",
            employee_views.employee_delete,
            name="employee_delete",
        ),
        path(
            "dashboard/employee/export/excel/",
            employee_views.employee_export_excel,
            name="employee_export_excel",
        ),
        path(
            "dashboard/employee/export/pdf/",
            employee_views.employee_export_pdf,
            name="employee_export_pdf",
        ),
        path(
            "dashboard/employee/history/<uuid:pk>/",
            employee_views.employee_employment_history,
            name="employee_employment_history",
        ),  # sidebar ရဲ့ "Employment history"
        path("dashboard/employee/preview/<uuid:pk>/", employee_views.employee_preview, name="employee_preview"),
        # ========================
        # Attachments (Address / Document) — Employer & Employee နှစ်ခုလုံးအတွက် generic
        # <str:model_name> = "employer" | "employee" (helpers/allowed_models.py ထဲက model_name)
        # ========================
        path(
            "dashboard/address/add/<str:model_name>/<uuid:object_id>/",
            attachment_views.address_add,
            name="address_add",
        ),
        path(
            "dashboard/address/update/<uuid:pk>/",
            attachment_views.address_update,
            name="address_update",
        ),
        path(
            "dashboard/address/delete/<uuid:pk>/",
            attachment_views.address_delete,
            name="address_delete",
        ),
        path(
            "dashboard/document/upload/<str:model_name>/<uuid:object_id>/",
            attachment_views.document_upload,
            name="document_upload",
        ),
        path(
            "dashboard/document/delete/<uuid:pk>/",
            attachment_views.document_delete,
            name="document_delete",
        ),
        path(
            "dashboard/document-type/list/",
            attachment_views.document_type_list,
            name="document_type_list",
        ),
        path(
            "dashboard/document-type/create/",
            attachment_views.document_type_create,
            name="document_type_create",
        ),
        # ========================
        # Lock Screen
        # ========================
        path("lock-screen/", dashboard_page_views.lock_screen, name="lock_screen"),
        path("unlock/", dashboard_page_views.unlock, name="unlock"),
        path("locked/", dashboard_page_views.locked, name="locked"),
        # ========================
        # PWA
        # ========================
        path("", include("pwa.urls")),
        # ========================
        # Page Not Found
        # ========================
        re_path(r"^.*/$", dashboard_page_views.page_not_found),
    ]
    + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
)
