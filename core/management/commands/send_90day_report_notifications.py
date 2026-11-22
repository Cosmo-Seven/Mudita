from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import EmployeeModel
from helpers.web_push import push_to_user


class Command(BaseCommand):
    help = (
        "Send weekly web push reminders to employees whose 90-day report "
        "deadline is approaching."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show who would be notified without sending any push.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ignore the weekly interval and notify everyone in the window.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        force = options["force"]

        window_days = settings.NINETY_DAY_NOTIFY_WINDOW_DAYS
        interval_days = settings.NINETY_DAY_NOTIFY_INTERVAL_DAYS
        now = timezone.now()
        today = timezone.localdate()

        employees = (
            EmployeeModel.objects.filter(
                is_deleted=False,
                user__isnull=False,
                report_90day_date__isnull=False,
                report_90day_date__gte=today,
                report_90day_date__lte=today + timedelta(days=window_days),
            )
            .select_related("user")
            .order_by("report_90day_date")
        )

        notified = 0
        skipped = 0
        delivered_total = 0

        for employee in employees:
            last_notified = employee.report_90day_last_notified_at
            if (
                not force
                and last_notified is not None
                and now - last_notified < timedelta(days=interval_days)
            ):
                skipped += 1
                continue

            days_left = employee.days_until_90day_report
            payload = {
                "title": "Mudita · 90-Day Report Reminder",
                "body": (
                    f"Your 90-day report is due on "
                    f"{employee.report_90day_date:%d %b %Y} ({days_left} days left). "
                    "Open the worker portal for details."
                ),
                "url": "/worker/",
                "tag": f"report-90day-{employee.id}",
            }

            if dry_run:
                self.stdout.write(
                    f"[dry-run] {employee.full_name_en} "
                    f"(due {employee.report_90day_date}, {days_left} days left)"
                )
                continue

            delivered = push_to_user(employee.user, payload)
            if delivered:
                notified += 1
                delivered_total += delivered
                employee.report_90day_last_notified_at = now
                employee.save(update_fields=["report_90day_last_notified_at", "updated_at"])
            else:
                skipped += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"[dry-run] {employees.count()} employee(s) in the window.")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Notified {notified} employee(s) "
                f"via {delivered_total} subscription(s); skipped {skipped}."
            )
        )
