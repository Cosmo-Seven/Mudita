from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.employee_models import EmployeeModel
from models.employer_models import EmployerModel
from models.role_models import RoleModel
from models.group_models import GroupModel, TeamModel


class GroupTeamManagementPageTests(TestCase):
    def setUp(self):
        role = RoleModel.objects.create(name="Group Team Manager")
        role.permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    "view_employermodel",
                    "view_employeemodel",
                    "view_groupmodel",
                    "add_groupmodel",
                    "change_groupmodel",
                    "delete_groupmodel",
                    "add_teammodel",
                    "change_teammodel",
                    "delete_teammodel",
                    "change_employeemodel",
                ]
            )
        )
        self.user = get_user_model().objects.create_user(
            username="group-team-manager",
            email="group-team-manager@example.com",
            password="TestPass123!",
            role=role,
            is_staff=True,
        )
        self.client.force_login(self.user)

    def test_page_shows_employer_and_independent_options(self):
        response = self.client.get(reverse("group_team_management"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Managing groups and teams.")
        self.assertContains(response, reverse("employer_list"))
        self.assertContains(response, "Affiliated with an employer.")
        self.assertContains(response, "Independent / No employer")
        self.assertContains(response, reverse("independent_group_list"))

    def test_page_requires_employer_view_permission(self):
        self.user.role.permissions.clear()

        response = self.client.get(reverse("group_team_management"))

        self.assertEqual(response.status_code, 302)

    def test_employer_manager_can_open_independent_groups_without_group_permission(self):
        self.user.role.permissions.remove(
            Permission.objects.get(codename="view_groupmodel")
        )

        response = self.client.get(reverse("independent_group_list"))

        self.assertEqual(response.status_code, 200)

    def test_groups_teams_and_single_employee_membership_crud(self):
        group_response = self.client.post(
            reverse("group_create"), {"name": "Warehouse"}
        )
        self.assertRedirects(group_response, reverse("independent_group_list"))
        group = GroupModel.objects.get(name="Warehouse")

        self.client.post(
            reverse("group_update", args=[group.id]), {"name": "Main warehouse"}
        )
        group.refresh_from_db()
        self.assertEqual(group.name, "Main warehouse")

        self.client.post(
            reverse("team_create", args=[group.id]), {"name": "Morning shift"}
        )
        team = TeamModel.objects.get(group=group, name="Morning shift")
        employer = EmployerModel.objects.create(
            name_en="Test Employer", name_th="Test Employer"
        )
        employee = EmployeeModel.objects.create(
            employer=employer,
            full_name_en="Test Employee",
            created_by=self.user,
        )

        self.client.post(
            reverse("team_add_employee", args=[team.id]),
            {"employee": str(employee.id)},
        )
        employee.refresh_from_db()
        self.assertEqual(employee.team_id, team.id)

        other_team = TeamModel.objects.create(
            group=group, name="Evening shift", created_by=self.user
        )
        self.client.post(
            reverse("team_add_employee", args=[other_team.id]),
            {"employee": str(employee.id)},
        )
        employee.refresh_from_db()
        self.assertEqual(employee.team_id, team.id)

        self.client.post(reverse("team_update", args=[team.id]), {"name": "Day shift"})
        team.refresh_from_db()
        self.assertEqual(team.name, "Day shift")

        self.client.post(
            reverse("team_remove_employee", args=[team.id, employee.id])
        )
        employee.refresh_from_db()
        self.assertIsNone(employee.team_id)

        self.client.post(
            reverse("team_add_employee", args=[other_team.id]),
            {"employee": str(employee.id)},
        )
        self.client.post(reverse("team_delete", args=[other_team.id]))
        self.assertFalse(TeamModel.objects.filter(pk=other_team.id).exists())
        employee.refresh_from_db()
        self.assertIsNone(employee.team_id)

        self.client.post(
            reverse("team_add_employee", args=[team.id]),
            {"employee": str(employee.id)},
        )

        self.client.post(reverse("group_delete", args=[group.id]))
        self.assertFalse(GroupModel.objects.filter(pk=group.id).exists())
        self.assertFalse(TeamModel.objects.filter(group_id=group.id).exists())
        employee.refresh_from_db()
        self.assertIsNone(employee.team_id)

    def test_independent_group_page_displays_group_team_and_employee(self):
        group = GroupModel.objects.create(name="Warehouse")
        team = TeamModel.objects.create(group=group, name="Morning shift")
        employer = EmployerModel.objects.create(
            name_en="Test Employer", name_th="Test Employer"
        )
        EmployeeModel.objects.create(
            employer=employer,
            team=team,
            full_name_en="Test Employee",
            created_by=self.user,
        )

        response = self.client.get(reverse("independent_group_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Warehouse")
        self.assertContains(response, "Morning shift")
        self.assertContains(response, "Test Employee")

    def test_team_members_and_employee_options_are_grouped_by_employer(self):
        group = GroupModel.objects.create(name="Warehouse")
        team = TeamModel.objects.create(group=group, name="Morning shift")
        alpha_employer = EmployerModel.objects.create(
            name_en="Alpha Employer", name_th="Alpha Employer"
        )
        beta_employer = EmployerModel.objects.create(
            name_en="Beta Employer", name_th="Beta Employer"
        )
        EmployeeModel.objects.create(
            employer=alpha_employer,
            team=team,
            full_name_en="Alpha Employee",
            created_by=self.user,
        )
        EmployeeModel.objects.create(
            employer=beta_employer,
            team=team,
            full_name_en="Beta Employee",
            created_by=self.user,
        )
        EmployeeModel.objects.create(
            employer=beta_employer,
            full_name_en="Available Employee",
            created_by=self.user,
        )

        response = self.client.get(reverse("independent_group_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="independent-employer-group"')
        self.assertContains(response, 'class="independent-employer-group"', count=2)
        self.assertContains(response, "Alpha Employer")
        self.assertContains(response, "Beta Employer")
        self.assertContains(response, '<optgroup label="Beta Employer">')
        self.assertContains(response, "Available Employee")
        self.assertContains(response, "ti-folder")
        self.assertContains(response, "ti-map-pin")
        self.assertContains(response, "ti-download")
        self.assertContains(response, "ti-x")
        self.assertContains(response, "Remove from team")
        self.assertContains(response, "openIndependentEmployeePreview")
        self.assertLess(
            response.content.index(b"Alpha Employee"),
            response.content.index(b"Beta Employee"),
        )
