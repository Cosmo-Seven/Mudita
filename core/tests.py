from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from models.role_models import RoleModel
from models.employee_models import EmployeeModel
from models.employer_models import EmployerModel
from models.workflow_models import (
    EmployeeWorkflowModel,
    WorkflowJobModel,
    WorkflowStageModel,
    WorkflowTypeModel,
)
from views.dashboard.workflow_job_views import _seed_workflow_type_stages
from views.dashboard.workflow_views import WorkflowEmployeeCreateForm

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

    def test_login_welcome_message_is_shown_only_once(self):
        response = self.client.post(
            reverse("dashboard_login"),
            {"email": "manager@example.com", "password": "StrongPass123!"},
            follow=True,
        )

        self.assertContains(response, "Welcome manager")
        self.assertNotContains(self.client.get(reverse("dashboard")), "Welcome manager")

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

    def test_user_list_history_restore_includes_new_roles(self):
        self.role.permissions.add(Permission.objects.get(codename="view_usermodel"))
        new_role = RoleModel.objects.create(name="Newly Added Role")

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("user_list"),
            HTTP_HX_REQUEST="true",
            HTTP_HX_HISTORY_RESTORE_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'hx-history="false"')
        self.assertContains(response, f'<option value="{new_role.id}">{new_role.name}</option>')

    def test_workflow_steps_modal_uses_delegated_actions_without_inline_script(self):
        self.role.permissions.add(
            Permission.objects.get(codename="view_workflowstagemodel"),
            Permission.objects.get(codename="add_workflowstagemodel"),
            Permission.objects.get(codename="delete_workflowstagemodel"),
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
        self.assertContains(response, 'class="workflow-step-drag-handle btn btn-xs btn-outline-secondary px-2 py-1"')
        self.assertContains(response, 'draggable="true"')
        self.assertContains(response, 'hx-select="unset"', count=4)
        self.assertContains(response, 'hx-push-url="false"', count=4)
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

    def test_workflow_stage_create_htmx_response_keeps_existing_stages(self):
        self.role.permissions.add(Permission.objects.get(codename="add_workflowstagemodel"))
        workflow_type = WorkflowTypeModel.objects.create(code="stage_create_htmx", name="Stage Create")
        WorkflowStageModel.objects.create(workflow_type=workflow_type, name="Existing Step", order=1)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("workflow_stage_create", args=[workflow_type.code]),
            {"name": "New Step"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Existing Step")
        self.assertContains(response, "New Step")
        self.assertEqual(list(workflow_type.stages.order_by("order").values_list("name", flat=True)), ["Existing Step", "New Step"])

    def test_workflow_stage_reorder_moves_step_up_and_down(self):
        self.role.permissions.add(Permission.objects.get(codename="change_workflowstagemodel"))
        workflow_type = WorkflowTypeModel.objects.create(code="stage_reorder", name="Stage Reorder")
        stages = [
            WorkflowStageModel.objects.create(workflow_type=workflow_type, name=name, order=order)
            for order, name in enumerate(("First", "Second", "Third"), start=1)
        ]
        self.client.force_login(self.user)

        up_response = self.client.post(
            reverse("workflow_stage_reorder", args=[stages[1].id, "up"]),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(up_response.status_code, 200)
        self.assertEqual(
            list(workflow_type.stages.order_by("order").values_list("name", flat=True)),
            ["Second", "First", "Third"],
        )

        down_response = self.client.post(
            reverse("workflow_stage_reorder", args=[stages[1].id, "down"]),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(down_response.status_code, 200)
        self.assertEqual(
            list(workflow_type.stages.order_by("order").values_list("name", flat=True)),
            ["First", "Second", "Third"],
        )

    def test_workflow_stage_move_reorders_to_requested_position(self):
        self.role.permissions.add(Permission.objects.get(codename="change_workflowstagemodel"))
        workflow_type = WorkflowTypeModel.objects.create(code="stage_move", name="Stage Move")
        stages = [
            WorkflowStageModel.objects.create(workflow_type=workflow_type, name=name, order=order)
            for order, name in enumerate(("First", "Second", "Third", "Fourth"), start=1)
        ]
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("workflow_stage_move", args=[stages[3].id, 2]),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fourth")
        self.assertEqual(
            list(workflow_type.stages.order_by("order").values_list("name", flat=True)),
            ["First", "Fourth", "Second", "Third"],
        )
        self.assertEqual(
            list(workflow_type.stages.order_by("order").values_list("order", flat=True)),
            [1, 2, 3, 4],
        )

    def test_workflow_stage_delete_htmx_response_keeps_remaining_stages(self):
        self.role.permissions.add(
            Permission.objects.get(codename="view_workflowstagemodel"),
            Permission.objects.get(codename="delete_workflowstagemodel"),
        )
        workflow_type = WorkflowTypeModel.objects.create(code="stage_delete_htmx", name="Stage Delete")
        deleted_stage = WorkflowStageModel.objects.create(workflow_type=workflow_type, name="Remove Me", order=1)
        WorkflowStageModel.objects.create(workflow_type=workflow_type, name="Keep Me", order=2)

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("workflow_stage_delete", args=[deleted_stage.id]),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Remove Me")
        self.assertContains(response, "Keep Me")
        self.assertFalse(WorkflowStageModel.objects.filter(pk=deleted_stage.pk).exists())

    def test_workflow_stage_delete_is_hidden_without_permission(self):
        self.role.permissions.add(Permission.objects.get(codename="view_workflowstagemodel"))
        workflow_type = WorkflowTypeModel.objects.create(code="stage_delete_hidden", name="Stage Delete")
        stage = WorkflowStageModel.objects.create(workflow_type=workflow_type, name="Keep Me", order=1)

        self.client.force_login(self.user)
        response = self.client.get(reverse("workflow_steps_modal", args=[workflow_type.code]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Keep Me")
        self.assertNotContains(response, 'data-workflow-step-action="delete-step"')

        denied_response = self.client.post(
            reverse("workflow_stage_delete", args=[stage.id]),
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(denied_response.status_code, 403)
        self.assertTrue(WorkflowStageModel.objects.filter(pk=stage.pk).exists())

    def test_workflow_stage_delete_in_use_returns_modal_error(self):
        self.role.permissions.add(
            Permission.objects.get(codename="view_workflowstagemodel"),
            Permission.objects.get(codename="delete_workflowstagemodel"),
        )
        workflow_type = WorkflowTypeModel.objects.create(code="stage_delete_in_use", name="Stage Delete")
        stage = WorkflowStageModel.objects.create(workflow_type=workflow_type, name="In Use", order=1)
        employer = EmployerModel.objects.create(name_en="Employer", name_th="นายจ้าง")
        employee = EmployeeModel.objects.create(employer=employer, full_name_en="Employee")
        EmployeeWorkflowModel.objects.create(
            employee=employee,
            workflow_type=workflow_type,
            current_stage=stage,
        )

        self.client.force_login(self.user)
        response = self.client.post(
            reverse("workflow_stage_delete", args=[stage.id]),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This step is already in use and cannot be deleted.")
        self.assertTrue(WorkflowStageModel.objects.filter(pk=stage.pk).exists())

    def test_workflow_type_creation_seeds_unique_stage_list(self):
        first = WorkflowTypeModel.objects.create(code="alpha_job", name="Alpha Job")
        second = WorkflowTypeModel.objects.create(code="beta_job", name="Beta Job")
        _seed_workflow_type_stages(first, ["Start Alpha Job", "Review Alpha Job", "Complete Alpha Job"])
        _seed_workflow_type_stages(second, ["Start Beta Job", "Review Beta Job", "Complete Beta Job"])

        self.assertEqual(list(first.stages.values_list("name", flat=True)), ["Start Alpha Job", "Review Alpha Job", "Complete Alpha Job"])
        self.assertEqual(list(second.stages.values_list("name", flat=True)), ["Start Beta Job", "Review Beta Job", "Complete Beta Job"])
        self.assertNotEqual(list(first.stages.values_list("name", flat=True)), list(second.stages.values_list("name", flat=True)))


class WorkflowJobCreateTests(TestCase):
    def setUp(self):
        self.role = RoleModel.objects.create(name="Workflow Job Manager")
        self.role.permissions.add(
            Permission.objects.get(codename="view_workflowtypemodel"),
            Permission.objects.get(codename="view_employeeworkflowmodel"),
            Permission.objects.get(codename="add_employeeworkflowmodel"),
            Permission.objects.get(codename="add_employeemodel"),
            Permission.objects.get(codename="add_workflowtypemodel"),
        )
        self.user = User.objects.create_user(
            username="workflow-manager",
            email="workflow-manager@example.com",
            password="StrongPass123!",
            role=self.role,
            is_staff=True,
        )
        self.employer = EmployerModel.objects.create(name_th="นายจ้าง", name_en="Employer A")
        self.other_employer = EmployerModel.objects.create(name_th="นายจ้าง 2", name_en="Employer B")
        self.employee_a = EmployeeModel.objects.create(
            employer=self.employer, full_name_en="Employee A", status="active"
        )
        self.employee_b = EmployeeModel.objects.create(
            employer=self.employer, full_name_en="Employee B", status="active"
        )
        self.other_employee = EmployeeModel.objects.create(
            employer=self.other_employer, full_name_en="Employee C", status="active"
        )
        self.workflow_type = WorkflowTypeModel.objects.create(
            code="mou_import", name="MOU Import"
        )
        self.first_stage = WorkflowStageModel.objects.create(
            workflow_type=self.workflow_type, name="Collect documents", order=1
        )
        self.client.force_login(self.user)

    def test_create_job_saves_workset_without_creating_employee_workflows(self):
        response = self.client.post(
            reverse("workflow_job_create"),
            {
                "workflow_type_id": str(self.workflow_type.id),
                "employer_id": str(self.employer.id),
                "project_name": "January MOU Batch",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Refresh"], "true")
        workset = WorkflowJobModel.objects.get()
        self.assertEqual(workset.workflow_type, self.workflow_type)
        self.assertEqual(workset.employer, self.employer)
        self.assertEqual(workset.project_name, "January MOU Batch")
        self.assertEqual(workset.created_by, self.user)
        self.assertFalse(EmployeeWorkflowModel.objects.exists())

    def test_create_job_requires_work_type_and_active_employer(self):
        response = self.client.post(
            reverse("workflow_job_create"),
            {
                "workflow_type_id": "",
                "employer_id": "",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Choose a work type.")
        self.assertContains(response, "Choose an active employer.")
        self.assertFalse(WorkflowJobModel.objects.exists())

    def test_create_job_form_only_asks_for_work_type_employer_and_work_set_name(self):
        EmployeeWorkflowModel.objects.create(
            employee=self.employee_a,
            workflow_type=self.workflow_type,
            current_stage=self.first_stage,
        )

        response = self.client.get(
            reverse("workflow_job_create"),
            {
                "workflow_type_id": str(self.workflow_type.id),
                "employer_id": str(self.employer.id),
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="workflow_type_id"')
        self.assertContains(response, 'name="employer_id"')
        self.assertContains(response, 'name="project_name"')
        self.assertNotContains(response, 'name="employee_ids"')
        self.assertNotContains(response, "Employees")
        self.assertContains(response, "Project Name / Work Set Name")
        self.assertContains(response, "Job type")

    def test_employee_can_be_added_to_existing_workset(self):
        workset = WorkflowJobModel.objects.create(
            workflow_type=self.workflow_type,
            employer=self.employer,
            project_name="January MOU Batch",
        )

        response = self.client.get(
            reverse("workflow_add_employee_modal", args=[self.workflow_type.code]),
            {
                "employer_id": str(self.employer.id),
                "workflow_job_id": str(workset.id),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'name="workflow_job_id" value="{workset.id}"')
        self.assertContains(response, "January MOU Batch")

        response = self.client.post(
            reverse("workflow_add_employee", args=[self.workflow_type.code]),
            {
                "mode": "existing",
                "employer_id": str(self.employer.id),
                "workflow_job_id": str(workset.id),
                "employee_ids": [str(self.employee_a.id)],
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        workflow = EmployeeWorkflowModel.objects.get(employee=self.employee_a)
        self.assertEqual(workflow.workflow_job, workset)
        self.assertEqual(workflow.project_name, "January MOU Batch")

    def test_empty_workset_is_visible_under_employer_before_employees_are_added(self):
        workset = WorkflowJobModel.objects.create(
            workflow_type=self.workflow_type,
            employer=self.employer,
            project_name="January MOU Batch",
        )

        dashboard_response = self.client.get(
            reverse("workflow_dashboard", args=[self.workflow_type.code])
        )
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertContains(dashboard_response, "Create Job")
        self.assertContains(dashboard_response, "openAddEmployeeModal")
        self.assertEqual(
            dashboard_response.content.count(b'class="card mb-2 employer-workflow-row"'),
            1,
        )

        employer_response = self.client.get(
            reverse(
                "workflow_employer_employees",
                args=[self.workflow_type.code, self.employer.id],
            )
        )
        self.assertEqual(employer_response.status_code, 200)
        self.assertContains(employer_response, "January MOU Batch")
        self.assertContains(employer_response, f"'{workset.id}'")
        self.assertContains(employer_response, "0")

    def test_create_job_button_only_shows_for_mou_import_and_social_security(self):
        dashboard_url = reverse("workflow_dashboard", args=[self.workflow_type.code])
        response = self.client.get(dashboard_url)
        self.assertContains(response, "Create Job")
        self.assertNotContains(
            response,
            f"onclick=\"openAddEmployeeModal('{self.workflow_type.code}')\"",
        )

        other_workflow = WorkflowTypeModel.objects.create(
            code="custom_test_workflow",
            name="Custom Test Workflow",
        )
        response = self.client.get(
            reverse("workflow_dashboard", args=[other_workflow.code])
        )
        self.assertNotContains(response, "Create Job")
        self.assertContains(
            response,
            f"onclick=\"openAddEmployeeModal('{other_workflow.code}')\"",
        )

        social_security = WorkflowTypeModel.objects.create(
            code="social_security",
            name="Social Security",
        )
        response = self.client.get(
            reverse("workflow_dashboard", args=[social_security.code])
        )
        self.assertContains(response, "Create Job")
        self.assertNotContains(
            response,
            f"onclick=\"openAddEmployeeModal('{social_security.code}')\"",
        )

        renamed_social_security = WorkflowTypeModel.objects.create(
            code="pre_production_preparation",
            name="Social Security submission.",
        )
        response = self.client.get(
            reverse("workflow_dashboard", args=[renamed_social_security.code])
        )
        self.assertContains(response, "Create Job")
        self.assertNotContains(
            response,
            f"onclick=\"openAddEmployeeModal('{renamed_social_security.code}')\"",
        )

    def test_workflow_add_employee_modal_offers_manual_employee_creation(self):
        response = self.client.get(
            reverse("workflow_add_employee_modal", args=[self.workflow_type.code]),
            {"employer_id": str(self.employer.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "New / Manual")
        self.assertContains(response, 'name="mode" value="manual"')
        self.assertContains(response, 'name="full_name_en"')
        self.assertContains(response, 'name="login_email"')
        self.assertContains(response, 'name="date_of_birth"')
        self.assertContains(response, 'name="height_cm"')
        self.assertContains(response, 'name="employee_ids"')
        self.assertContains(response, f'value="{self.employee_a.id}"')
        self.assertContains(
            response,
            f'<option value="{self.employer.id}" selected>{self.employer.name_en}</option>',
            html=True,
        )
        for field_name in WorkflowEmployeeCreateForm.Meta.fields:
            self.assertContains(response, f'name="{field_name}"')
        self.assertContains(response, 'hx-encoding="multipart/form-data"')

    def test_manual_workflow_employee_creation_creates_and_enrolls_employee(self):
        response = self.client.post(
            reverse("workflow_add_employee", args=[self.workflow_type.code]),
            {
                "mode": "manual",
                "employer": str(self.employer.id),
                "full_name_en": "New Workflow Employee",
                "login_email": "new.employee@example.com",
                "date_of_birth": "2000-01-15",
                "height_cm": "172.5",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Trigger"], "workflowEmployeesAdded")
        employee = EmployeeModel.objects.get(full_name_en="New Workflow Employee")
        self.assertEqual(employee.employer, self.employer)
        self.assertEqual(employee.login_email, "new.employee@example.com")
        self.assertEqual(str(employee.height_cm), "172.5")
        workflow = EmployeeWorkflowModel.objects.get(
            employee=employee, workflow_type=self.workflow_type
        )
        self.assertEqual(workflow.current_stage, self.first_stage)
        self.assertContains(response, "New Workflow Employee")
        self.assertContains(response, 'id="manual-employee-pane" role="tabpanel"')

    def test_manual_workflow_employee_creation_shows_validation_errors(self):
        response = self.client.post(
            reverse("workflow_add_employee", args=[self.workflow_type.code]),
            {
                "mode": "manual",
                "employer": str(self.employer.id),
                "full_name_en": "",
                "login_email": "not-an-email",
                "date_of_birth": "not-a-date",
                "height_cm": "not-a-number",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.")
        self.assertContains(response, "Enter a valid email address.")
        self.assertFalse(
            EmployeeModel.objects.filter(
                employer=self.employer, full_name_en=""
            ).exists()
        )
        self.assertFalse(EmployeeWorkflowModel.objects.exists())

    def test_manual_workflow_employee_creation_requires_employee_permission(self):
        self.role.permissions.remove(Permission.objects.get(codename="add_employeemodel"))

        response = self.client.get(
            reverse("workflow_add_employee_modal", args=[self.workflow_type.code])
        )
        self.assertNotContains(response, "New / Manual")

        response = self.client.post(
            reverse("workflow_add_employee", args=[self.workflow_type.code]),
            {
                "mode": "manual",
                "employer": str(self.employer.id),
                "full_name_en": "Should Not Be Created",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            EmployeeModel.objects.filter(full_name_en="Should Not Be Created").exists()
        )

    def test_change_employer_modal_lists_existing_employees_across_employers(self):
        change_workflow = WorkflowTypeModel.objects.create(
            code="employer_entry_change", name="Employer Entry / Change"
        )
        resigned = EmployeeModel.objects.create(
            employer=self.other_employer,
            full_name_en="Resigned Employee",
            status="terminated",
        )
        pending = EmployeeModel.objects.create(
            employer=self.employer,
            full_name_en="Pending Employee",
        )

        response = self.client.get(
            reverse("workflow_add_employee_modal", args=[change_workflow.code]),
            {"employer_id": str(self.employer.id)},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resigned Employee")
        self.assertContains(response, "Pending Employee")
        self.assertContains(response, f'value="{resigned.id}"')
        self.assertContains(response, f'value="{pending.id}"')
        self.assertContains(response, 'name="employer_id"')
        self.assertContains(
            response,
            f'<option value="{self.employer.id}" selected>{self.employer.name_en}</option>',
            html=True,
        )
        self.assertEqual(resigned.employer, self.other_employer)

    def test_change_employer_add_moves_selected_employee_to_target_employer(self):
        change_workflow = WorkflowTypeModel.objects.create(
            code="employer_entry_change", name="Employer Entry / Change"
        )
        employee = EmployeeModel.objects.create(
            employer=self.other_employer,
            full_name_en="Resigned Employee",
            status="terminated",
        )

        response = self.client.post(
            reverse("workflow_add_employee", args=[change_workflow.code]),
            {
                "mode": "existing",
                "employer_id": str(self.employer.id),
                "employee_ids": [str(employee.id)],
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        employee.refresh_from_db()
        self.assertEqual(employee.employer, self.employer)
        self.assertEqual(employee.status, "terminated")
        self.assertTrue(
            EmployeeWorkflowModel.objects.filter(
                employee=employee, workflow_type=change_workflow
            ).exists()
        )

    def test_workflow_dashboard_shows_all_workflow_types_in_tabs(self):
        response = self.client.get(
            reverse("workflow_dashboard", args=[self.workflow_type.code])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["workflow_types"]), 6)
        self.assertCountEqual(
            [wt.code for wt in response.context["workflow_types"]],
            [
                "employer_entry_change",
                "employer_exit_notice",
                "pre_production_preparation",
                "employer_transfer_package",
                "mou_import",
                "renewal_mou",
            ],
        )

    def test_workflow_list_calendar_shows_appointments_and_changes_month(self):
        appointment_date = date.today() + timedelta(days=2)
        EmployeeWorkflowModel.objects.create(
            employee=self.employee_a,
            workflow_type=self.workflow_type,
            appointment_date=appointment_date,
        )

        response = self.client.get(reverse("workflow_job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context["calendar_days"]), 42)
        self.assertEqual(
            next(
                day["appointment_count"]
                for day in response.context["calendar_days"]
                if day["date"] == appointment_date
            ),
            1,
        )
        self.assertEqual(
            list(response.context["upcoming_appointments"])[0].employee.full_name_en,
            self.employee_a.full_name_en,
        )
        self.assertContains(response, "Monthly Overview")

        response = self.client.get(reverse("workflow_job_list"), {"month": "2027-01"})
        self.assertEqual(response.context["calendar_month"], date(2027, 1, 1))

        dashboard_response = self.client.get(
            reverse("workflow_dashboard", args=[self.workflow_type.code])
        )
        self.assertNotContains(dashboard_response, "Monthly Overview")

    def test_workflow_dashboard_shows_one_employer_row_with_all_employees_nested(self):
        EmployeeWorkflowModel.objects.create(
            employee=self.employee_a,
            workflow_type=self.workflow_type,
            current_stage=self.first_stage,
        )
        EmployeeWorkflowModel.objects.create(
            employee=self.employee_b,
            workflow_type=self.workflow_type,
            current_stage=self.first_stage,
        )

        response = self.client.get(
            reverse("workflow_dashboard", args=[self.workflow_type.code])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.content.count(b'class="card mb-2 employer-workflow-row"'),
            1,
        )

        nested_response = self.client.get(
            reverse(
                "workflow_employer_employees",
                args=[self.workflow_type.code, self.employer.id],
            )
        )
        self.assertEqual(nested_response.status_code, 200)
        self.assertContains(nested_response, "Employee A")
        self.assertContains(nested_response, "Employee B")

    def test_workflow_card_opens_job_form_with_work_type_selected(self):
        response = self.client.get(reverse("workflow_job_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'hx-get="/dashboard/workflow/jobs/create/?workflow_type_id={self.workflow_type.id}"',
        )
        form_response = self.client.get(
            reverse("workflow_job_create"),
            {"workflow_type_id": str(self.workflow_type.id)},
        )
        self.assertContains(
            form_response,
            f'value="{self.workflow_type.id}"',
        )
        self.assertContains(form_response, "selected>")

    def test_work_type_creation_remains_available_separately(self):
        response = self.client.post(
            reverse("workflow_type_create"),
            {
                "name": "Renewal MOU",
                "group": "employer_notification",
                "code": "renewal_mou",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(WorkflowTypeModel.objects.filter(code="renewal_mou").exists())

    def test_renamed_work_type_stays_renamed_after_workflow_job_list_refresh(self):
        self.role.permissions.add(
            Permission.objects.get(codename="change_workflowtypemodel")
        )
        workflow_type = WorkflowTypeModel.objects.create(
            code="employer_entry_change",
            name="Employer Entry / Change",
        )

        response = self.client.post(
            reverse("workflow_job_update", args=[workflow_type.id]),
            {
                "name": "Updated Employer Workflow",
                "group": "employer_notification",
                "icon": "ti ti-user-plus",
                "subtitle": "Updated workflow",
                "order": "1",
            },
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["HX-Refresh"], "true")

        refreshed_response = self.client.get(reverse("workflow_job_list"))
        self.assertEqual(refreshed_response.status_code, 200)
        self.assertContains(refreshed_response, "Updated Employer Workflow")
        workflow_type.refresh_from_db()
        self.assertEqual(workflow_type.name, "Updated Employer Workflow")
