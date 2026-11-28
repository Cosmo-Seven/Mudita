from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.employee_models import EmployeeModel
from models.employer_models import EmployerModel
from models.role_models import RoleModel
from models.workflow_models import EmployeeRequestModel


class ResignationAndTerminationFlowTests(TestCase):
    def setUp(self):
        role = RoleModel.objects.create(name="Termination Manager")
        role.permissions.add(Permission.objects.get(codename="view_employeemodel"))
        self.user = get_user_model().objects.create_user(
            username="termination-manager",
            email="termination-manager@example.com",
            password="TestPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(self.user)
        self.employer = EmployerModel.objects.create(
            name_en="Acme Co", name_th="Acme Co"
        )

    def _resignation(self, name="Resigning Employee", status="active"):
        employee = EmployeeModel.objects.create(
            employer=self.employer,
            full_name_en=name,
            status=status,
            created_by=self.user,
        )
        resignation = EmployeeRequestModel.objects.create(
            employee=employee,
            request_type="resignation",
            reason="Personal reasons",
            created_by=self.user,
        )
        return employee, resignation

    def test_resignation_list_shows_pending_resignations(self):
        employee, _ = self._resignation()

        response = self.client.get(reverse("resignation_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resigning Employee")
        self.assertContains(response, "Personal reasons")
        self.assertContains(response, "Total: 1")

    def test_terminate_action_marks_employee_terminated(self):
        employee, resignation = self._resignation()

        response = self.client.post(
            reverse("resignation_list"),
            {
                "request_id": str(resignation.id),
                "action": "terminate",
                "staff_note": "Approved by HR",
            },
        )

        self.assertRedirects(response, reverse("resignation_list"))
        employee.refresh_from_db()
        resignation.refresh_from_db()
        self.assertEqual(resignation.status, "approved")
        self.assertEqual(resignation.staff_note, "Approved by HR")
        self.assertIsNotNone(resignation.reviewed_at)
        self.assertEqual(employee.status, "terminated")

    def test_reject_action_keeps_employee_active(self):
        employee, resignation = self._resignation()

        self.client.post(
            reverse("resignation_list"),
            {"request_id": str(resignation.id), "action": "reject"},
        )

        employee.refresh_from_db()
        resignation.refresh_from_db()
        self.assertEqual(resignation.status, "rejected")
        self.assertEqual(employee.status, "active")

    def test_termination_list_only_shows_terminated_employees(self):
        self._resignation(name="Active Employee", status="active")
        self._resignation(name="Terminated Employee", status="terminated")

        response = self.client.get(reverse("termination_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Terminated Employee")
        self.assertNotContains(response, "Active Employee")

    def test_resignation_list_requires_employee_view_permission(self):
        self.user.role.permissions.clear()

        response = self.client.get(reverse("resignation_list"))

        self.assertEqual(response.status_code, 302)

    def test_termination_list_requires_employee_view_permission(self):
        self.user.role.permissions.clear()

        response = self.client.get(reverse("termination_list"))

        self.assertEqual(response.status_code, 302)
