from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.role_models import RoleModel
from models.workflow_models import WorkflowTypeModel, WorkflowStageModel

User = get_user_model()


class DashboardLoginTests(TestCase):
    def setUp(self):
        self.role = RoleModel.objects.create(name="Employee Manager")
        self.role.permissions.add(
            Permission.objects.get(codename="view_employeemodel")
        )
        self.user = User.objects.create_user(
            username="manager",
            email="manager@example.com",
            password="StrongPass123!",
            role=self.role,
            is_staff=True,
        )

    def test_login_redirects_to_dashboard(self):
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

    def test_workflow_steps_modal_uses_delegated_actions_without_inline_script(self):
        self.role.permissions.add(
            Permission.objects.get(codename="view_workflowstagemodel"),
            Permission.objects.get(codename="add_workflowstagemodel"),
        )
        workflow_type = WorkflowTypeModel.objects.create(code="test_workflow", name="Test Workflow")
        WorkflowStageModel.objects.create(workflow_type=workflow_type, name="Applied", order=1)

        self.client.force_login(self.user)
        response = self.client.get(reverse("workflow_steps_modal", args=[workflow_type.code]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-workflow-step-action="add-step"')
        self.assertContains(response, 'data-workflow-step-action="toggle-edit-step"')
        self.assertContains(response, 'data-workflow-step-action="delete-step"')
        self.assertContains(response, 'data-workflow-step-action="reorder-step"')
        self.assertNotContains(response, "<script>")

    def test_workflow_stage_create_endpoint_creates_stage(self):
        self.role.permissions.add(Permission.objects.get(codename="add_workflowstagemodel"))
        workflow_type = WorkflowTypeModel.objects.create(code="stage_create", name="Stage Create")

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("workflow_stage_create", args=[workflow_type.code]),
            {"name": "Final Review"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"success": True, "id": str(workflow_type.stages.first().id), "name": "Final Review", "order": 1})
