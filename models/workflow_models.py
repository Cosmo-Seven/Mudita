from django.db import models
from models.base_models import BaseModel
from models.employee_models import EmployeeModel
from models.employer_models import EmployerModel


class WorkflowTypeModel(BaseModel):
    """Tab ၄ ခု: Notification of joining/changing employer, Notification of departure,
    Import MOU, Renew MOU — dynamic lookup, admin ကနေ ထပ်ထည့်နိုင်"""
    code = models.SlugField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    class Meta:
        app_label = "core"
        db_table = "workflow_types"
        ordering = ["order"]
        verbose_name = "Workflow Type"


class WorkflowStageModel(BaseModel):
    """'Submit a request' -> 'Pay' -> ... -> 'finish' စတဲ့ stage sequence.
    Workflow type တစ်ခုချင်းစီအတွက် stage set ကွဲနိုင်တာမို့ FK ချိတ်ထားတယ်"""
    workflow_type = models.ForeignKey(WorkflowTypeModel, on_delete=models.CASCADE, related_name="stages")
    name = models.CharField(max_length=255)
    order = models.PositiveIntegerField(default=0)
    is_terminal = models.BooleanField(default=False)     # "finish" stage
    is_cancel_stage = models.BooleanField(default=False)  # "Cancelled" state

    def __str__(self):
        return f"{self.workflow_type.code}: {self.name}"

    class Meta:
        app_label = "core"
        db_table = "workflow_stages"
        ordering = ["workflow_type", "order"]
        unique_together = ("workflow_type", "order")
        verbose_name = "Workflow Stage"


class EmployeeWorkflowModel(BaseModel):
    """Employee တစ်ယောက်ရဲ့ workflow instance တစ်ခု (e.g. 'employer entry/change'
    process တစ်ခု စတင်ခြင်း) — employee တစ်ယောက်ကို workflow type တစ်ခုအောက်မှာ
    process အများကြီး run နိုင်တယ် (renew ထပ်လုပ်ရင် instance အသစ်)"""
    STATUS_CHOICES = (
        ("in_progress", "In Progress"),
        ("finished", "Finished"),
        ("cancelled", "Cancelled"),
    )

    employee = models.ForeignKey(EmployeeModel, on_delete=models.CASCADE, related_name="workflows")
    workflow_type = models.ForeignKey(WorkflowTypeModel, on_delete=models.PROTECT, related_name="workflows")
    current_stage = models.ForeignKey(WorkflowStageModel, on_delete=models.PROTECT, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="in_progress")

    note = models.TextField(blank=True)
    appointment_date = models.DateField(null=True, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return f"{self.employee.full_name_en} — {self.workflow_type.name}"

    class Meta:
        app_label = "core"
        db_table = "employee_workflows"
        verbose_name = "Employee Workflow"


class EmployeeWorkflowStageLogModel(BaseModel):
    """Stage တစ်ခုချင်းစီ ဖြတ်သန်းသွားတဲ့ history — checkmark (✓) logic ကို
    ဒီ table ကနေ ဆုံးဖြတ်တယ် (log ရှိရင် done, current_stage ဆိုရင် current, မရှိရင် pending)"""
    workflow = models.ForeignKey(EmployeeWorkflowModel, on_delete=models.CASCADE, related_name="stage_logs")
    stage = models.ForeignKey(WorkflowStageModel, on_delete=models.PROTECT)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        db_table = "employee_workflow_stage_logs"
        unique_together = ("workflow", "stage")
        verbose_name = "Workflow Stage Log"