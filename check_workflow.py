import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mudita.settings')
django.setup()

from core.models import WorkflowTypeModel

workflow_types = list(WorkflowTypeModel.objects.values_list('code', 'name'))
print("Workflow Types in database:")
for code, name in workflow_types:
    print(f"  - {code}: {name}")

if not workflow_types:
    print("  (No workflow types found)")
