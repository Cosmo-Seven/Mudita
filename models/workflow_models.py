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

    group = models.CharField(max_length=50, default="employer_notification")
    icon = models.CharField(max_length=50, default="ti ti-chart-bar")
    subtitle = models.CharField(max_length=255, blank=True)

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

    # ---- Client-facing 3-state progress (Pending / In-Progress / Completed),
    # derived from status + whether any stage has been logged yet. "cancelled"
    # is reported separately since the client only asked for these 3 states. ----
    PROGRESS_PENDING = "pending"
    PROGRESS_IN_PROGRESS = "in_progress"
    PROGRESS_COMPLETED = "completed"
    PROGRESS_CANCELLED = "cancelled"

    @property
    def progress_label(self):
        if self.status == "cancelled":
            return self.PROGRESS_CANCELLED
        if self.status == "finished":
            return self.PROGRESS_COMPLETED
        if self.stage_logs.exists():
            return self.PROGRESS_IN_PROGRESS
        return self.PROGRESS_PENDING

    @classmethod
    def get_or_start(cls, employee, workflow_type, user=None):
        """Lazily enrolls an employee into a workflow type the first time any
        of its stages is touched, instead of requiring a separate 'enroll' step."""
        first_stage = workflow_type.stages.order_by("order").first()
        obj, created = cls.objects.get_or_create(
            employee=employee,
            workflow_type=workflow_type,
            defaults={"current_stage": first_stage, "status": "in_progress", "created_by": user},
        )
        return obj, created

    def toggle_stage(self, stage, user=None):
        """Click a stage chip: if not done yet, mark it (and every earlier stage)
        done and move current_stage forward; if already done, undo it (and every
        later stage) and move current_stage back to it. Keeps `status` in sync
        (auto-finish on the terminal stage, auto-reopen on undo)."""
        stages = list(self.workflow_type.stages.order_by("order"))
        is_done = self.stage_logs.filter(stage=stage).exists()

        if is_done:
            self.stage_logs.filter(stage__order__gte=stage.order).delete()
            self.current_stage = stage
            if self.status == "finished":
                self.status = "in_progress"
        else:
            for s in stages:
                if s.order <= stage.order:
                    EmployeeWorkflowStageLogModel.objects.get_or_create(workflow=self, stage=s)
            next_stage = next((s for s in stages if s.order > stage.order), None)
            self.current_stage = next_stage or stage
            if next_stage is None or stage.is_terminal:
                self.status = "finished"
            elif self.status == "cancelled":
                self.status = "in_progress"

        self.updated_by = user
        self.save(update_fields=["current_stage", "status", "updated_by", "updated_at"])
        return self


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