from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.employee_models import EmployeeModel
from models.employer_models import EmployerModel
from models.role_models import RoleModel


class TerminationNotifiedEmployeePageTests(TestCase):
    def setUp(self):
        role = RoleModel.objects.create(name="Termination Notice Viewer")
        role.permissions.add(Permission.objects.get(codename="view_employeemodel"))
        self.user = get_user_model().objects.create_user(
            username="termination-viewer",
            email="termination-viewer@example.com",
            password="TestPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_page_displays_requested_filters_and_empty_state(self):
        response = self.client.get(reverse("termination_notified_employees"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "All employees who have been notified of their termination")
        self.assertContains(response, "total: 0 people")
        self.assertContains(response, 'name="search"')
        self.assertContains(response, 'name="employer"')
        self.assertContains(response, 'name="nationality"')
        self.assertContains(response, 'name="resolution_type"')
        self.assertContains(response, 'name="pink_card"')
        self.assertContains(response, 'name="passport_type"')
        self.assertContains(response, "Export CSV")
        self.assertContains(response, "No termination records yet")

    def test_existing_terminated_employees_are_not_misidentified_as_notified(self):
        employer = EmployerModel.objects.create(
            name_en="Former Employer", name_th="Former Employer"
        )
        EmployeeModel.objects.create(
            employer=employer,
            full_name_en="Unclassified Terminated Employee",
            status="terminated",
            created_by=self.user,
        )

        response = self.client.get(reverse("termination_notified_employees"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "total: 0 people")
        self.assertNotContains(response, "Unclassified Terminated Employee")

    def test_page_requires_employee_view_permission(self):
        self.user.role.permissions.clear()

        response = self.client.get(reverse("termination_notified_employees"))

        self.assertEqual(response.status_code, 302)
