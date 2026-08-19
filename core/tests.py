from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.role_models import RoleModel

User = get_user_model()


class DashboardWelcomeAccessTests(TestCase):
    def setUp(self):
        self.role = RoleModel.objects.create(name="Employee Manager")
        self.role.permissions.add(
            Permission.objects.get(codename="view_employeemodel")
        )

    def test_login_redirects_to_welcome_page_and_shows_allowed_links(self):
        user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass123!",
            role=self.role,
            is_staff=True,
        )

        self.client.login(email="manager@example.com", password="StrongPass123!")
        response = self.client.get(reverse("dashboard_welcome"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Go to Dashboard")
        self.assertContains(response, "Manage Employees")

    def test_welcome_page_hides_links_when_user_lacks_permissions(self):
        user = User.objects.create_user(
            username="basicuser",
            email="basicuser@example.com",
            password="StrongPass123!",
            role=RoleModel.objects.create(name="No Access Role"),
            is_staff=False,
        )

        self.client.login(email="basicuser@example.com", password="StrongPass123!")
        response = self.client.get(reverse("dashboard_welcome"))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Go to Dashboard")
        self.assertNotContains(response, "Manage Employees")
