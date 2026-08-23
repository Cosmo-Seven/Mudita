from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.role_models import RoleModel

User = get_user_model()


class DashboardLoginTests(TestCase):
    def setUp(self):
        self.role = RoleModel.objects.create(name="Employee Manager")
        self.role.permissions.add(
            Permission.objects.get(codename="view_employeemodel")
        )

    def test_login_redirects_to_dashboard(self):
        User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass123!",
            role=self.role,
            is_staff=True,
        )

        response = self.client.post(
            reverse("dashboard_login"),
            {"email": "manager@example.com", "password": "StrongPass123!"},
        )

        self.assertRedirects(response, reverse("dashboard"))

    def test_authenticated_user_visiting_login_is_redirected_to_dashboard(self):
        User.objects.create_user(
            username="basicuser",
            email="basicuser@example.com",
            password="StrongPass123!",
            role=RoleModel.objects.create(name="No Access Role"),
            is_staff=False,
        )

        self.client.login(email="basicuser@example.com", password="StrongPass123!")
        response = self.client.get(reverse("dashboard_login"))

        self.assertRedirects(response, reverse("dashboard"))
