# core/migrations/0004_seed_preparation_workflow.py
from django.db import migrations

STAGES = [
    "Waiting for registration code.",
    "The documents are incomplete.",
    "All documents are complete.",
    "Waiting for information updates.",
    "The code is available.",
    "Reset code",
]

def seed(apps, schema_editor):
    WorkflowTypeModel = apps.get_model("core", "WorkflowTypeModel")
    WorkflowStageModel = apps.get_model("core", "WorkflowStageModel")

    wf_type, _ = WorkflowTypeModel.objects.get_or_create(
        code="pre_production_preparation",
        defaults={
            "name": "Pre-Production / Preparation",
            "subtitle": "Prepare documents and confirm data before sending to Workflow.",
            "icon": "ti ti-hierarchy-2",
            "group": "pre_production",
            "order": 0,
        },
    )
    for idx, name in enumerate(STAGES, start=1):
        WorkflowStageModel.objects.get_or_create(
            workflow_type=wf_type, order=idx,
            defaults={"name": name, "is_terminal": "code is available" in name},
        )

def unseed(apps, schema_editor):
    WorkflowTypeModel = apps.get_model("core", "WorkflowTypeModel")
    WorkflowTypeModel.objects.filter(code="pre_production_preparation").delete()

class Migration(migrations.Migration):
    dependencies = [("core", "0003_workflowtypemodel_workflowstagemodel_and_more")]
    operations = [migrations.RunPython(seed, unseed)]