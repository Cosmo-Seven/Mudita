from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from helpers.employee_import import import_employees
from models.employee_models import Employee90DayReportModel, EmployeeModel
from models.employer_models import EmployerModel
from models.role_models import RoleModel


class NinetyDayReportHistoryTests(TestCase):
    def setUp(self):
        role = RoleModel.objects.create(name="90-Day Report Manager")
        role.permissions.add(
            Permission.objects.get(codename="change_employeemodel"),
            Permission.objects.get(codename="view_employeemodel"),
        )
        self.user = get_user_model().objects.create_user(
            username="90day-manager",
            email="90day-manager@example.com",
            password="TestPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.employer = EmployerModel.objects.create(
            name_en="Acme Co", name_th="Acme Co"
        )

    def _employee(self, name="Worker"):
        return EmployeeModel.objects.create(
            employer=self.employer,
            full_name_en=name,
            status="active",
            created_by=self.user,
        )

    def _add_report_date(self, employee, raw_date):
        return self.client.post(
            reverse("employee_update", args=[employee.id]),
            {
                "full_name_en": employee.full_name_en,
                "status": "active",
                "phone": "",
                "report_90day_new_date": raw_date,
            },
        )

    def test_update_saves_record_and_auto_calculates_next_due(self):
        employee = self._employee()
        report_date = date(2026, 1, 10)

        response = self._add_report_date(employee, "2026-01-10")

        self.assertRedirects(response, reverse("employee_list"))
        record = Employee90DayReportModel.objects.get(employee=employee)
        self.assertEqual(record.report_date, report_date)
        self.assertEqual(record.created_by, self.user)
        employee.refresh_from_db()
        self.assertEqual(employee.report_90day_date, report_date + timedelta(days=90))

    def test_report_dates_are_kept_without_limit(self):
        employee = self._employee("Worker B")
        raw_dates = ["2025-01-05", "2025-04-05", "2025-07-05", "2025-10-05"]

        for raw_date in raw_dates:
            self._add_report_date(employee, raw_date)

        self.assertEqual(employee.report_90day_records.count(), 4)
        employee.refresh_from_db()
        self.assertEqual(
            employee.report_90day_date, date(2025, 10, 5) + timedelta(days=90)
        )

    def test_duplicate_report_date_is_not_saved_twice(self):
        employee = self._employee("Worker C")

        self._add_report_date(employee, "2026-02-01")
        self._add_report_date(employee, "2026-02-01")

        self.assertEqual(employee.report_90day_records.count(), 1)

    def test_update_page_lists_report_history(self):
        employee = self._employee("Worker D")
        Employee90DayReportModel.objects.create(
            employee=employee, report_date=date(2025, 2, 2), created_by=self.user
        )

        response = self.client.get(reverse("employee_update", args=[employee.id]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "02 Feb 2025")
        self.assertContains(response, "90 Day Report History")

    def test_import_creates_unlimited_report_records(self):
        rows = [
            {
                "row_number": 2,
                "data": {
                    "full_name_en": "Imported Worker",
                    "report_90day_date": date(2026, 3, 1) + timedelta(days=90),
                    "_90day_reports": [date(2025, 12, 1), date(2026, 3, 1)],
                },
            }
        ]

        created, skipped, errors = import_employees(
            rows, employer=self.employer, created_by=self.user, with_accounts=False
        )

        self.assertEqual(len(created), 1)
        self.assertEqual(errors, [])
        employee = EmployeeModel.objects.get(full_name_en="Imported Worker")
        self.assertEqual(employee.report_90day_records.count(), 2)
        self.assertEqual(
            employee.report_90day_date, date(2026, 3, 1) + timedelta(days=90)
        )
