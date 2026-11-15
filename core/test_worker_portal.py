from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse

from models.employee_models import EmployeeModel
from models.employer_models import EmployerModel
from models.role_models import RoleModel
from models.workflow_models import EmployeeRequestModel


User = get_user_model()


class WorkerPortalTests(TestCase):
    def setUp(self):
        self.worker_user = User.objects.create_user(
            username="Worker One",
            email="worker@example.com",
            password="StrongPass123!",
        )
        self.employer = EmployerModel.objects.create(
            name_en="Thai Employer", name_th="นายจ้าง"
        )
        self.employee = EmployeeModel.objects.create(
            employer=self.employer,
            user=self.worker_user,
            full_name_en="Worker One",
            report_90day_date=date.today() + timedelta(days=10),
        )

    def test_staff_creates_worker_account_without_registration(self):
        response = self.client.get("/")
        self.assertRedirects(response, reverse("dashboard_login"))

        role = RoleModel.objects.create(name="Employee Creator")
        role.permissions.add(Permission.objects.get(codename="add_employeemodel"))
        manager = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(manager)
        response = self.client.post(
            reverse("employee_create"),
            {
                "employer": str(self.employer.pk),
                "full_name_en": "New Worker",
                "phone": "",
                "login_email": "new-worker@example.com",
                "worker_password": "StrongPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("employee_list"))
        employee = EmployeeModel.objects.get(full_name_en="New Worker")
        self.assertIsNotNone(employee.user)
        self.assertFalse(employee.user.is_staff)
        self.assertTrue(check_password("StrongPass123!", employee.user.password))

    def test_employee_create_shows_employers_in_native_select(self):
        role = RoleModel.objects.create(name="Employee Form Manager")
        role.permissions.add(Permission.objects.get(codename="add_employeemodel"))
        manager = User.objects.create_user(
            username="form-manager",
            email="form-manager@example.com",
            password="StrongPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(manager)

        response = self.client.get(reverse("employee_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'<select class="form-select" name="employer" required>')
        self.assertContains(response, f'value="{self.employer.pk}">{self.employer.name_en}')

    def test_worker_login_redirects_to_portal_with_report_reminder(self):
        response = self.client.post(
            reverse("dashboard_login"),
            {"email": "worker@example.com", "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("worker_profile"))
        response = self.client.get(reverse("worker_portal"))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["report_reminder"])
        self.assertContains(response, "90-Day Report")
        self.assertContains(response, "Next reporting deadline")
        self.assertContains(response, "dashboard/css/worker-portal.css")
        self.assertContains(response, "worker-hero")
        self.assertNotContains(response, "register")

    def test_worker_profile_shows_only_linked_employee_information(self):
        other_user = User.objects.create_user(
            username="Other Worker",
            email="other@example.com",
            password="StrongPass123!",
        )
        EmployeeModel.objects.create(
            employer=self.employer,
            user=other_user,
            full_name_en="Other Worker Secret",
        )
        self.client.force_login(self.worker_user)

        response = self.client.get(reverse("worker_profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "dashboard/css/worker-portal.css")
        self.assertContains(response, "worker-profile-layout")
        self.assertContains(response, "Worker One")
        self.assertContains(response, "Thai Employer")
        self.assertNotContains(response, "Other Worker Secret")

    def test_worker_is_redirected_away_from_dashboard_and_staff_pages(self):
        self.client.force_login(self.worker_user)

        for path in (reverse("dashboard"), reverse("employee_list"), reverse("dashboard_profile")):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertRedirects(response, reverse("worker_profile"))

    def test_worker_can_submit_job_change_and_resignation_requests(self):
        self.client.force_login(self.worker_user)
        missing_target = self.client.post(
            reverse("submit_employee_request"),
            {"request_type": "job_change", "reason": "Want to change jobs"},
        )
        self.assertRedirects(missing_target, reverse("worker_portal"))
        self.assertEqual(EmployeeRequestModel.objects.count(), 0)

        response = self.client.post(
            reverse("submit_employee_request"),
            {
                "request_type": "job_change",
                "desired_job": "Factory B",
                "reason": "Want to change jobs",
            },
        )
        self.assertRedirects(response, reverse("worker_portal"))
        self.assertEqual(EmployeeRequestModel.objects.get().employee, self.employee)

        response = self.client.post(
            reverse("submit_employee_request"),
            {
                "request_type": "resignation",
                "reason": "Returning home",
            },
        )
        self.assertRedirects(response, reverse("worker_portal"))
        self.assertEqual(EmployeeRequestModel.objects.count(), 2)

    def test_staff_can_review_request_and_worker_sees_response(self):
        employee_request = EmployeeRequestModel.objects.create(
            employee=self.employee,
            request_type="resignation",
            reason="Returning home",
        )
        role = RoleModel.objects.create(name="Worker Request Reviewer")
        role.permissions.add(Permission.objects.get(codename="view_employeemodel"))
        staff_user = User.objects.create_user(
            username="reviewer",
            email="reviewer@example.com",
            password="StrongPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(staff_user)

        response = self.client.get(reverse("employee_request_list"))
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            reverse("employee_request_list"),
            {
                "request_id": str(employee_request.pk),
                "status": "approved",
                "staff_note": "Approved",
            },
        )
        self.assertRedirects(response, reverse("employee_request_list"))
        employee_request.refresh_from_db()
        self.assertEqual(employee_request.status, "approved")
        self.assertEqual(employee_request.staff_note, "Approved")
        self.assertIsNotNone(employee_request.reviewed_at)

        self.client.force_login(self.worker_user)
        response = self.client.get(reverse("worker_portal"))
        self.assertContains(response, "Approved")
