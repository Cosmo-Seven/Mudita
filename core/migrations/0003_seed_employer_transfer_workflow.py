# core/migrations/0003_seed_employer_transfer_workflow.py
from django.db import migrations

# Client-specified 4 stages for the "employee transfer" process.
# Each stage is tracked per employee as Pending / In-Progress / Completed
# (derived from EmployeeWorkflowModel.current_stage + EmployeeWorkflowStageLogModel,
# same mechanism already used by the other workflow types).
STAGES = [
    "Employer Change",
    "Social Security & Tax ID",
    "Pink Card Registration",
    "Bank Account Opening",
]


def seed(apps, schema_editor):
    WorkflowTypeModel = apps.get_model("core", "WorkflowTypeModel")
    WorkflowStageModel = apps.get_model("core", "WorkflowStageModel")

    wf_type, _ = WorkflowTypeModel.objects.get_or_create(
        code="employer_transfer_package",
        defaults={
            "name": "Employer Transfer Process",
            "subtitle": "Employer Change \u2192 Social Security & Tax ID \u2192 Pink Card \u2192 Bank Account",
            "icon": "ti ti-arrows-right-left",
            "group": "employer_transfer",
            "order": 5,
        },
    )
    for idx, name in enumerate(STAGES, start=1):
        WorkflowStageModel.objects.get_or_create(
            workflow_type=wf_type, order=idx,
            defaults={"name": name, "is_terminal": idx == len(STAGES)},
        )


def unseed(apps, schema_editor):
    WorkflowTypeModel = apps.get_model("core", "WorkflowTypeModel")
    WorkflowTypeModel.objects.filter(code="employer_transfer_package").delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0002_seed_preparation_workflow")]
    operations = [migrations.RunPython(seed, unseed)]