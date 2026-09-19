# core/migrations/0004_seed_notification_workflow_types.py
from django.db import migrations

# "Processing" tab (sidebar: processing / url: workflow_notification)
# 4 sibling workflow types shown as tabs together (same group="employer_notification").
WORKFLOW_TYPES = [
    {
        "code": "employer_entry_change",
        "name": "Notification of Employment (Entry/Change)",
        "order": 1,
        "stages": [
            "Submit Request",
            "Document Review",
            "Payment",
            "Processing",
            "Completed",
        ],
    },
    {
        "code": "departure",
        "name": "Notification of Departure",
        "order": 2,
        "stages": [
            "Submit Request",
            "Document Review",
            "Processing",
            "Completed",
        ],
    },
    {
        "code": "import_mou",
        "name": "Import MOU",
        "order": 3,
        "stages": [
            "Submit Request",
            "Document Review",
            "Processing",
            "Completed",
        ],
    },
    {
        "code": "renew_mou",
        "name": "Renew MOU",
        "order": 4,
        "stages": [
            "Submit Request",
            "Document Review",
            "Payment",
            "Processing",
            "Completed",
        ],
    },
]


def seed(apps, schema_editor):
    WorkflowTypeModel = apps.get_model("core", "WorkflowTypeModel")
    WorkflowStageModel = apps.get_model("core", "WorkflowStageModel")

    for wt_data in WORKFLOW_TYPES:
        wf_type, _ = WorkflowTypeModel.objects.get_or_create(
            code=wt_data["code"],
            defaults={
                "name": wt_data["name"],
                "order": wt_data["order"],
                "group": "employer_notification",
            },
        )
        for idx, name in enumerate(wt_data["stages"], start=1):
            WorkflowStageModel.objects.get_or_create(
                workflow_type=wf_type, order=idx,
                defaults={"name": name, "is_terminal": idx == len(wt_data["stages"])},
            )


def unseed(apps, schema_editor):
    WorkflowTypeModel = apps.get_model("core", "WorkflowTypeModel")
    WorkflowTypeModel.objects.filter(
        code__in=[wt["code"] for wt in WORKFLOW_TYPES]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [("core", "0003_seed_employer_transfer_workflow")]
    operations = [migrations.RunPython(seed, unseed)]
