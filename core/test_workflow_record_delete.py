from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.employee_models import EmployeeModel
from models.employer_models import EmployerModel
from models.role_models import RoleModel
from models.workflow_models import EmployeeWorkflowModel, WorkflowTypeModel


class WorkflowRecordDeleteTests(TestCase):
    def setUp(self):
        self.role = RoleModel.objects.create(name="Workflow Record Manager")
        self.role.permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    "view_employeeworkflowmodel",
                    "delete_employeeworkflowmodel",
                    "add_employeeworkflowmodel",
                ]
            )
        )
        self.user = get_user_model().objects.create_user(
            username="workflow-record-manager",
            email="workflow-record-manager@example.com",
            password="StrongPass123!",
            role=self.role,
            is_staff=True,
        )
        self.client.force_login(self.user)

        self.employer = EmployerModel.objects.create(
            name_en="Workflow Employer",
            name_th="Workflow Employer",
        )
        self.employee = EmployeeModel.objects.create(
            employer=self.employer,
            full_name_en="Workflow Employee",
            created_by=self.user,
        )
        self.workflow_type = WorkflowTypeModel.objects.create(
            code="workflow-record-delete-test",
            name="Workflow Record Delete Test",
        )
        self.workflow = EmployeeWorkflowModel.objects.create(
            employee=self.employee,
            workflow_type=self.workflow_type,
            created_by=self.user,
        )

    def test_selected_workflow_record_is_soft_deleted_without_removing_employee(self):
        response = self.client.post(
            reverse("workflow_records_delete", args=[self.workflow_type.code]),
            {"workflow_ids": str(self.workflow.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"success": True, "deleted_count": 1})

        self.workflow.refresh_from_db()
        self.employee.refresh_from_db()
        self.assertTrue(self.workflow.is_deleted)
        self.assertFalse(self.employee.is_deleted)

        cards_response = self.client.get(
            reverse(
                "workflow_employer_employees",
                args=[self.workflow_type.code, self.employer.id],
            )
        )
        self.assertEqual(cards_response.status_code, 200)
        self.assertNotContains(cards_response, self.employee.full_name_en)

        add_employee_response = self.client.get(
            reverse("workflow_add_employee_modal", args=[self.workflow_type.code])
        )
        self.assertContains(add_employee_response, self.employee.full_name_en)

        re_enrolled_workflow, created = EmployeeWorkflowModel.get_or_start(
            self.employee,
            self.workflow_type,
            user=self.user,
        )
        self.assertTrue(created)
        self.assertNotEqual(re_enrolled_workflow.id, self.workflow.id)

    def test_workflow_dashboard_fragment_is_available_for_in_place_refresh(self):
        response = self.client.get(
            reverse("workflow_dashboard", args=[self.workflow_type.code]),
            {"_workflow_fragment": "dashboard"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="workflowDashboardContent"')
        self.assertContains(response, reverse("workflow_records_delete", args=[self.workflow_type.code]))

    def test_invalid_or_missing_selected_ids_are_rejected(self):
        url = reverse("workflow_records_delete", args=[self.workflow_type.code])

        self.assertEqual(self.client.post(url).status_code, 400)
        response = self.client.post(url, {"workflow_ids": "not-a-uuid"})
        self.assertEqual(response.status_code, 400)
        self.workflow.refresh_from_db()
        self.assertFalse(self.workflow.is_deleted)
