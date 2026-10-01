from django.core.management.base import BaseCommand
from django.utils import timezone

from gym.models import Subscription


class Command(BaseCommand):
    help = "Mark active memberships whose end date has passed as expired. Run daily (cron / Task Scheduler)."

    def handle(self, *args, **options):
        count = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE, end_date__lt=timezone.localdate()
        ).update(status=Subscription.Status.EXPIRED)
        self.stdout.write(self.style.SUCCESS(f"{count} membership(s) marked as expired."))
