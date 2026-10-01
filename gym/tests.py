"""Run with:  DB_ENGINE=sqlite python manage.py test   (no MySQL privileges needed)."""
import copy
import importlib
import os
import shutil
import tempfile
from datetime import time, timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from iron_fitness.urls import asset_patterns, urlpatterns as project_urlpatterns

from .models import (
    Booking, ClassSchedule, Enquiry, GymClass, MemberProfile, MembershipPlan, Subscription, Trainer,
    format_days,
)

# URLconf used by the static-file test (the real one only serves ./frontend assets when DEBUG=True).
urlpatterns = [*project_urlpatterns, *asset_patterns]

User = get_user_model()
PASSWORD = "Str0ng!Pass#2026"

# Minimal stand-ins for the site's own pages, so the tests never depend on your real HTML.
STUB_PAGES = {
    "index.html": "home",
    "about.html": "about",
    "services.html": "services",
    "classes.html": "{% for c in classes %}{{ c.name }}|{{ c.schedule_display }};{% endfor %}",
    "membership.html": "{% for p in plans %}{{ p.name }}-{{ p.price|floatformat:'0' }};{% endfor %}",
    "contact.html": "<form method='post'>{% csrf_token %}</form>{{ form.errors }}",
}


class SiteTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls._stub_dir = tempfile.mkdtemp()
        for name, content in STUB_PAGES.items():
            (Path(cls._stub_dir) / name).write_text(content, encoding="utf-8")
        templates = copy.deepcopy(settings.TEMPLATES)
        templates[0]["DIRS"] = [cls._stub_dir, *templates[0]["DIRS"]]
        cls._override = override_settings(TEMPLATES=templates)
        cls._override.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._override.disable()
        shutil.rmtree(cls._stub_dir, ignore_errors=True)

    # helpers ---------------------------------------------------------------
    def make_member(self, email="member@example.com", plan=None):
        user = User.objects.create_user(username=email, email=email, password=PASSWORD, first_name="Test")
        profile = MemberProfile.objects.create(user=user, phone="9876543210")
        if plan:
            Subscription.objects.create(member=profile, plan=plan).activate()
        return user, profile

    def make_plans(self):
        self.basic = MembershipPlan.objects.create(name="Basic Plan", price=999, description="Gym only")
        self.standard = MembershipPlan.objects.create(
            name="Standard Plan", price=1499, description="Classes", includes_classes=True
        )

    def make_class(self, capacity=20, weekday=0):
        gym_class = GymClass.objects.create(name="Yoga", capacity=capacity)
        slot = ClassSchedule.objects.create(
            gym_class=gym_class, day_of_week=weekday, start_time=time(6, 0), end_time=time(7, 0)
        )
        return gym_class, slot

    @staticmethod
    def next_date(weekday):
        d = timezone.localdate() + timedelta(days=1)
        while d.weekday() != weekday:
            d += timedelta(days=1)
        return d


class HelperTests(TestCase):
    def test_format_days(self):
        self.assertEqual(format_days([0, 1, 2, 3, 4]), "Mon to Fri")
        self.assertEqual(format_days([1, 3]), "Tue & Thu")
        self.assertEqual(format_days([0, 2, 4]), "Mon, Wed, Fri")
        self.assertEqual(format_days([0, 1, 2, 3, 4, 5]), "Mon to Sat")


class PublicPageTests(SiteTestCase):
    def test_static_pages_render(self):
        for name in ("home", "index", "about", "services", "contact"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_membership_and_classes_show_database_content(self):
        self.make_plans()
        gym_class, _ = self.make_class()
        ClassSchedule.objects.create(gym_class=gym_class, day_of_week=2, start_time=time(6, 0), end_time=time(7, 0))
        ClassSchedule.objects.create(gym_class=gym_class, day_of_week=4, start_time=time(6, 0), end_time=time(7, 0))
        self.assertContains(self.client.get(reverse("membership")), "Basic Plan-999;")
        self.assertContains(self.client.get(reverse("classes")), "Yoga|Mon, Wed, Fri, 6AM - 7AM;")

    def test_trainers_page(self):
        self.assertEqual(self.client.get(reverse("trainers")).status_code, 200)


class ContactTests(SiteTestCase):
    @override_settings(GYM_NOTIFY_EMAIL="owner@example.com")
    def test_contact_creates_enquiry_and_sends_email(self):
        resp = self.client.post(reverse("contact"), {
            "name": "Asha", "email": "asha@example.com", "phone": "+91 98765 43210",
            "subject": "Timings", "message": "What are your Sunday hours?",
        })
        self.assertRedirects(resp, reverse("contact"))
        enquiry = Enquiry.objects.get()
        self.assertEqual(enquiry.kind, Enquiry.Kind.CONTACT)
        self.assertEqual(len(mail.outbox), 1)

    def test_membership_enquiry_kind(self):
        self.make_plans()
        self.client.post(reverse("contact"), {
            "name": "Asha", "email": "asha@example.com", "message": "Tell me more", "plan": self.standard.pk,
        })
        self.assertEqual(Enquiry.objects.get().kind, Enquiry.Kind.MEMBERSHIP)

    def test_honeypot_blocks_bots(self):
        self.client.post(reverse("contact"), {
            "name": "Bot", "email": "bot@example.com", "message": "spam", "website": "http://spam.example",
        })
        self.assertEqual(Enquiry.objects.count(), 0)

    def test_invalid_form_not_saved(self):
        self.client.post(reverse("contact"), {"name": "", "email": "not-an-email", "message": ""})
        self.assertEqual(Enquiry.objects.count(), 0)


class AccountTests(SiteTestCase):
    def register(self, email="new@example.com", **overrides):
        data = {
            "first_name": "Ravi", "last_name": "Kumar", "email": email, "phone": "9876543210",
            "password1": PASSWORD, "password2": PASSWORD,
        }
        data.update(overrides)
        return self.client.post(reverse("register"), data)

    def test_registration_creates_user_profile_and_logs_in(self):
        resp = self.register()
        self.assertRedirects(resp, reverse("dashboard"))
        user = User.objects.get(email="new@example.com")
        self.assertEqual(user.username, "new@example.com")
        self.assertEqual(user.profile.phone, "9876543210")
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_duplicate_email_rejected_case_insensitively(self):
        self.register("dup@example.com")
        self.client.logout()
        self.register("DUP@example.com")
        self.assertEqual(User.objects.count(), 1)

    def test_password_mismatch_rejected(self):
        self.register(password2="different")
        self.assertEqual(User.objects.count(), 0)

    def test_login_with_email(self):
        self.make_member("login@example.com")
        resp = self.client.post(reverse("login"), {"username": "LOGIN@example.com", "password": PASSWORD})
        self.assertRedirects(resp, reverse("dashboard"))

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("dashboard"))
        self.assertRedirects(resp, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_logout_requires_post(self):
        self.make_member()
        self.client.login(username="member@example.com", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        self.client.post(reverse("logout"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 302)


class MembershipTests(SiteTestCase):
    def test_join_plan_creates_pending_subscription_and_admin_activation_works(self):
        self.make_plans()
        _, profile = self.make_member()
        self.client.login(username="member@example.com", password=PASSWORD)
        url = reverse("join_plan", args=[self.standard.slug])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.client.post(url)
        sub = Subscription.objects.get()
        self.assertEqual(sub.status, Subscription.Status.PENDING)
        self.assertIsNone(profile.active_subscription())
        sub.activate()
        self.assertEqual(profile.active_subscription(), sub)
        self.assertEqual((sub.end_date - sub.start_date).days, self.standard.duration_days)

    def test_duplicate_request_ignored(self):
        self.make_plans()
        self.make_member()
        self.client.login(username="member@example.com", password=PASSWORD)
        url = reverse("join_plan", args=[self.standard.slug])
        self.client.post(url)
        self.client.post(url)
        self.assertEqual(Subscription.objects.count(), 1)


class BookingTests(SiteTestCase):
    def book(self, slot, when):
        return self.client.post(reverse("book_class"), {"schedule": slot.pk, "date": when.isoformat()})

    def test_booking_needs_class_including_plan(self):
        self.make_plans()
        _, slot = self.make_class()
        self.make_member(plan=self.basic)
        self.client.login(username="member@example.com", password=PASSWORD)
        self.book(slot, self.next_date(0))
        self.assertEqual(Booking.objects.count(), 0)

    def test_booking_success_then_duplicate_rejected(self):
        self.make_plans()
        _, slot = self.make_class()
        self.make_member(plan=self.standard)
        self.client.login(username="member@example.com", password=PASSWORD)
        when = self.next_date(0)
        self.assertRedirects(self.book(slot, when), reverse("dashboard"))
        self.book(slot, when)
        self.assertEqual(Booking.objects.count(), 1)

    def test_wrong_weekday_rejected(self):
        self.make_plans()
        _, slot = self.make_class(weekday=0)
        self.make_member(plan=self.standard)
        self.client.login(username="member@example.com", password=PASSWORD)
        self.book(slot, self.next_date(1))
        self.assertEqual(Booking.objects.count(), 0)

    def test_past_date_rejected(self):
        self.make_plans()
        _, slot = self.make_class()
        self.make_member(plan=self.standard)
        self.client.login(username="member@example.com", password=PASSWORD)
        self.book(slot, self.next_date(0) - timedelta(days=7))
        self.assertEqual(Booking.objects.count(), 0)

    def test_capacity_enforced_and_cancel_frees_a_place(self):
        self.make_plans()
        _, slot = self.make_class(capacity=1)
        self.make_member("a@example.com", plan=self.standard)
        self.make_member("b@example.com", plan=self.standard)
        when = self.next_date(0)

        self.client.login(username="a@example.com", password=PASSWORD)
        self.book(slot, when)
        booking = Booking.objects.get()
        self.client.logout()

        self.client.login(username="b@example.com", password=PASSWORD)
        self.book(slot, when)
        self.assertEqual(Booking.objects.count(), 1)  # full
        self.client.logout()

        self.client.login(username="a@example.com", password=PASSWORD)
        self.client.post(reverse("cancel_booking", args=[booking.pk]))
        booking.refresh_from_db()
        self.assertEqual(booking.status, Booking.Status.CANCELLED)
        self.client.logout()

        self.client.login(username="b@example.com", password=PASSWORD)
        self.book(slot, when)
        self.assertEqual(Booking.objects.filter(status=Booking.Status.CONFIRMED).count(), 1)

    def test_cannot_cancel_someone_elses_booking(self):
        self.make_plans()
        _, slot = self.make_class()
        _, owner = self.make_member("owner@example.com", plan=self.standard)
        self.make_member("other@example.com", plan=self.standard)
        booking = Booking.objects.create(member=owner, schedule=slot, date=self.next_date(0))
        self.client.login(username="other@example.com", password=PASSWORD)
        self.assertEqual(self.client.post(reverse("cancel_booking", args=[booking.pk])).status_code, 404)

    @override_settings(REQUIRE_ACTIVE_MEMBERSHIP_FOR_BOOKING=False)
    def test_membership_rule_can_be_switched_off(self):
        _, slot = self.make_class()
        self.make_member()
        self.client.login(username="member@example.com", password=PASSWORD)
        self.book(slot, self.next_date(0))
        self.assertEqual(Booking.objects.count(), 1)


class PageSmokeTests(SiteTestCase):
    def test_auth_pages_render(self):
        for name in ("register", "login"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 200, name)

    def test_member_pages_render_and_dashboard_lists_booking(self):
        self.make_plans()
        _, slot = self.make_class()
        self.make_member(plan=self.standard)
        self.client.login(username="member@example.com", password=PASSWORD)

        resp = self.client.get(f"{reverse('book_class')}?schedule={slot.pk}")
        self.assertContains(resp, f'value="{slot.pk}" selected')
        self.assertEqual(self.client.get(reverse("join_plan", args=[self.standard.slug])).status_code, 200)

        self.client.post(reverse("book_class"), {"schedule": slot.pk, "date": self.next_date(0).isoformat()})
        dashboard = self.client.get(reverse("dashboard"))
        self.assertContains(dashboard, "Yoga")
        self.assertContains(dashboard, "Standard Plan")

    def test_staff_account_without_profile_can_open_dashboard(self):
        User.objects.create_superuser("boss@example.com", "boss@example.com", PASSWORD)
        self.client.login(username="boss@example.com", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)


class AdminTests(SiteTestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser("admin@example.com", "admin@example.com", PASSWORD)
        self.client.force_login(self.admin_user)

    def test_every_admin_page_loads(self):
        self.make_plans()
        gym_class, slot = self.make_class()
        _, profile = self.make_member(plan=self.standard)
        Booking.objects.create(member=profile, schedule=slot, date=self.next_date(0))
        Enquiry.objects.create(name="A", email="a@example.com", message="hi")
        Trainer.objects.create(name="T", specialization="S")
        for model in ("memberprofile", "membershipplan", "subscription", "trainer", "gymclass", "booking", "enquiry"):
            for view in ("changelist", "add"):
                url = reverse(f"admin:gym_{model}_{view}")
                self.assertEqual(self.client.get(url).status_code, 200, url)
        for url in (
            reverse("admin:gym_gymclass_change", args=[gym_class.pk]),
            reverse("admin:gym_memberprofile_change", args=[profile.pk]),
        ):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_activate_subscription_action(self):
        self.make_plans()
        _, profile = self.make_member()
        sub = Subscription.objects.create(member=profile, plan=self.standard)
        resp = self.client.post(
            reverse("admin:gym_subscription_changelist"),
            {"action": "activate_selected", "_selected_action": [sub.pk]},
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        sub.refresh_from_db()
        self.assertEqual(sub.status, Subscription.Status.ACTIVE)
        self.assertIsNotNone(sub.end_date)

    def test_resolve_enquiry_action(self):
        enquiry = Enquiry.objects.create(name="A", email="a@example.com", message="hi")
        self.client.post(
            reverse("admin:gym_enquiry_changelist"),
            {"action": "mark_resolved", "_selected_action": [enquiry.pk]},
            follow=True,
        )
        enquiry.refresh_from_db()
        self.assertEqual(enquiry.status, Enquiry.Status.RESOLVED)

    def test_regular_member_cannot_use_admin(self):
        self.client.logout()
        self.make_member("regular@example.com")
        self.client.login(username="regular@example.com", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 302)


class FrontendAssetTests(SiteTestCase):
    def test_css_is_served_from_frontend_dir(self):
        css_dir = Path(self._stub_dir) / "css"
        css_dir.mkdir(exist_ok=True)
        (css_dir / "style.css").write_text("body{color:red}", encoding="utf-8")
        with self.settings(ROOT_URLCONF="gym.tests", FRONTEND_DIR=Path(self._stub_dir)):
            resp = self.client.get("/css/style.css")
            self.assertEqual(resp.status_code, 200)
            self.assertIn("text/css", resp["Content-Type"])
            self.assertEqual(b"".join(resp.streaming_content), b"body{color:red}")
            # only asset extensions are exposed
            self.assertEqual(self.client.get("/manage.py").status_code, 404)


class CommandTests(SiteTestCase):
    def test_seed_demo_data_is_idempotent_and_matches_website(self):
        call_command("seed_demo_data", stdout=StringIO())
        call_command("seed_demo_data", stdout=StringIO())
        self.assertEqual(MembershipPlan.objects.count(), 3)
        self.assertEqual(Trainer.objects.count(), 4)
        self.assertEqual(GymClass.objects.count(), 4)
        self.assertEqual(ClassSchedule.objects.count(), 16)
        self.assertEqual(MembershipPlan.objects.get(name="Premium Plan").price, 2499)
        self.assertEqual(GymClass.objects.get(name="Weight Training").schedule_display, "Mon to Fri, 7AM - 9AM")
        self.assertEqual(GymClass.objects.get(name="Yoga").schedule_display, "Mon, Wed, Fri, 6AM - 7AM")
        self.assertEqual(GymClass.objects.get(name="Zumba").schedule_display, "Tue & Thu, 6PM - 7PM")
        self.assertEqual(GymClass.objects.get(name="CrossFit").schedule_display, "Mon to Sat, 5PM - 6PM")

    def test_expire_subscriptions(self):
        self.make_plans()
        _, profile = self.make_member()
        today = timezone.localdate()
        old = Subscription.objects.create(
            member=profile, plan=self.standard, status=Subscription.Status.ACTIVE,
            start_date=today - timedelta(days=40), end_date=today - timedelta(days=1),
        )
        call_command("expire_subscriptions", stdout=StringIO())
        old.refresh_from_db()
        self.assertEqual(old.status, Subscription.Status.EXPIRED)


class SettingsTests(SimpleTestCase):
    def test_mysql_database_configuration(self):
        import iron_fitness.settings as project_settings

        env = {
            "DB_ENGINE": "mysql", "DB_NAME": "gymdb", "DB_USER": "gym_user",
            "DB_PASSWORD": "secret", "DB_HOST": "127.0.0.1", "DB_PORT": "3307",
        }
        try:
            with mock.patch.dict(os.environ, env):
                reloaded = importlib.reload(project_settings)
                db = reloaded.DATABASES["default"]
            self.assertEqual(db["ENGINE"], "django.db.backends.mysql")
            self.assertEqual(db["NAME"], "gymdb")
            self.assertEqual(db["USER"], "gym_user")
            self.assertEqual(db["PASSWORD"], "secret")
            self.assertEqual(db["PORT"], "3307")
            self.assertEqual(db["OPTIONS"]["charset"], "utf8mb4")
        finally:
            importlib.reload(project_settings)  # back to the environment the tests started with
