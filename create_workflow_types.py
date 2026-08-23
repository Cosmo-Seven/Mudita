import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mudita.settings')
django.setup()

from core.models import WorkflowTypeModel, WorkflowStageModel

# Create workflow types if they don't exist
workflow_types_data = [
    {
        'code': 'employer_entry_change',
        'name': 'Notification of Employment (Entry/Change)',
        'order': 1,
        'stages': [
            {'name': 'Submit Request', 'order': 1},
            {'name': 'Document Review', 'order': 2},
            {'name': 'Payment', 'order': 3},
            {'name': 'Processing', 'order': 4},
            {'name': 'Completed', 'order': 5, 'is_terminal': True},
        ]
    },
    {
        'code': 'departure',
        'name': 'Notification of Departure',
        'order': 2,
        'stages': [
            {'name': 'Submit Request', 'order': 1},
            {'name': 'Document Review', 'order': 2},
            {'name': 'Processing', 'order': 3},
            {'name': 'Completed', 'order': 4, 'is_terminal': True},
        ]
    },
    {
        'code': 'import_mou',
        'name': 'Import MOU',
        'order': 3,
        'stages': [
            {'name': 'Submit Request', 'order': 1},
            {'name': 'Document Review', 'order': 2},
            {'name': 'Processing', 'order': 3},
            {'name': 'Completed', 'order': 4, 'is_terminal': True},
        ]
    },
    {
        'code': 'renew_mou',
        'name': 'Renew MOU',
        'order': 4,
        'stages': [
            {'name': 'Submit Request', 'order': 1},
            {'name': 'Document Review', 'order': 2},
            {'name': 'Payment', 'order': 3},
            {'name': 'Processing', 'order': 4},
            {'name': 'Completed', 'order': 5, 'is_terminal': True},
        ]
    },
]

for wt_data in workflow_types_data:
    workflow_type, created = WorkflowTypeModel.objects.get_or_create(
        code=wt_data['code'],
        defaults={
            'name': wt_data['name'],
            'order': wt_data['order'],
        }
    )
    if created:
        print(f"Created workflow type: {workflow_type.code} - {workflow_type.name}")
    else:
        print(f"Workflow type already exists: {workflow_type.code} - {workflow_type.name}")

    # Create stages
    for stage_data in wt_data['stages']:
        stage, created = WorkflowStageModel.objects.get_or_create(
            workflow_type=workflow_type,
            order=stage_data['order'],
            defaults={
                'name': stage_data['name'],
                'is_terminal': stage_data.get('is_terminal', False),
                'is_cancel_stage': stage_data.get('is_cancel_stage', False),
            }
        )
        if created:
            print(f"  Created stage: {stage.name}")
        else:
            print(f"  Stage already exists: {stage.name}")

print("\nWorkflow types created successfully!")
