"""Database models for the Iron Fitness Gym backend."""
from datetime import timedelta   

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone
from django.utils.text import slugify

phone_validator = RegexValidator(
    regex=r"^\+?[0-9][0-9\s\-]{6,18}$",
    message="Enter a valid phone number (digits, spaces or dashes, optional leading +).",
)  

DAY_ABBR = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def format_time(t):
    """time(7, 0) -> '7AM', time(18, 30) -> '6:30PM'."""
    hour = t.hour % 12 or 12
    suffix = "AM" if t.hour < 12 else "PM"
    if t.minute == 0:
        return f"{hour}{suffix}"
    return f"{hour}:{t.minute:02d}{suffix}"


def format_days(days):
    """[0,1,2,3,4] -> 'Mon to Fri'; [1,3] -> 'Tue & Thu'; [0,2,4] -> 'Mon, Wed, Fri'."""
    days = sorted(set(days))
    if len(days) == 1:
        return DAY_ABBR[days[0]]
    if len(days) == 2:
        return f"{DAY_ABBR[days[0]]} & {DAY_ABBR[days[1]]}"
    if days[-1] - days[0] == len(days) - 1:
        return f"{DAY_ABBR[days[0]]} to {DAY_ABBR[days[-1]]}"
    return ", ".join(DAY_ABBR[d] for d in days)


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


# ---------------------------------------------------------------------------
# Members & memberships
# ---------------------------------------------------------------------------
class MemberProfile(TimeStampedModel):
    """Extra gym-specific details attached to Django's built-in User."""

    class Gender(models.TextChoices):
        MALE = "M", "Male"
        FEMALE = "F", "Female"
        OTHER = "O", "Other"
        UNSPECIFIED = "N", "Prefer not to say"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="profile"
    )
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=1, choices=Gender.choices, blank=True)
    address = models.TextField(blank=True)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(
        max_length=20, blank=True, validators=[phone_validator]
    )
    fitness_goal = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "member"
        verbose_name_plural = "members"

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return self.user.get_full_name() or self.user.username

    @property
    def email(self):
        return self.user.email

    def active_subscription(self):
        """The member's current active plan, or None."""
        today = timezone.localdate()
        return (
            self.subscriptions.filter(
                status=Subscription.Status.ACTIVE,
                start_date__lte=today,
                end_date__gte=today,
            )
            .select_related("plan")
            .order_by("-end_date")
            .first()
        )


class MembershipPlan(TimeStampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=80, unique=True, blank=True)
    price = models.DecimalField(
        max_digits=8, decimal_places=2, validators=[MinValueValidator(0)],
        help_text="Price in INR for one billing period.",
    )
    duration_days = models.PositiveIntegerField(default=30, help_text="Length of one period in days.")
    description = models.CharField(max_length=255)
    features = models.TextField(blank=True, help_text="One feature per line.")
    includes_classes = models.BooleanField(
        default=False, help_text="Members on this plan may book group classes."
    )
    includes_personal_trainer = models.BooleanField(default=False)
    is_popular = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True, help_text="Untick to hide from the website.")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "price"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def feature_list(self):
        return [line.strip() for line in self.features.splitlines() if line.strip()]


class Subscription(TimeStampedModel):
    """A member's purchase of a plan. Created as PENDING; staff activate it after payment."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending payment"
        ACTIVE = "active", "Active"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(MembershipPlan, on_delete=models.PROTECT, related_name="subscriptions")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    price_paid = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.member} - {self.plan} ({self.get_status_display()})"

    def activate(self, start=None):
        start = start or timezone.localdate()
        self.start_date = start
        self.end_date = start + timedelta(days=self.plan.duration_days)
        self.status = self.Status.ACTIVE
        if self.price_paid is None:
            self.price_paid = self.plan.price
        self.save()

    def clean(self):
        super().clean()
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before the start date."})


# ---------------------------------------------------------------------------
# Trainers & classes
# ---------------------------------------------------------------------------
class Trainer(TimeStampedModel):
    name = models.CharField(max_length=100)
    specialization = models.CharField(max_length=120)
    bio = models.TextField(blank=True)
    experience_years = models.PositiveSmallIntegerField(default=0)
    photo = models.ImageField(upload_to="trainers/", blank=True)
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    email = models.EmailField(blank=True)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class GymClass(TimeStampedModel):
    name = models.CharField(max_length=80, unique=True)
    icon = models.CharField(max_length=8, blank=True, help_text="Optional emoji shown on the website.")
    description = models.TextField(blank=True)
    trainer = models.ForeignKey(
        Trainer, null=True, blank=True, on_delete=models.SET_NULL, related_name="classes"
    )
    capacity = models.PositiveSmallIntegerField(default=20, help_text="Max members per session.")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "class"
        verbose_name_plural = "classes"

    def __str__(self):
        return self.name

    @property
    def schedule_display(self):
        """Human text like 'Mon to Fri, 7AM - 9AM' (uses prefetched schedules if available)."""
        groups = {}
        for s in self.schedules.all():
            groups.setdefault((s.start_time, s.end_time), []).append(s.day_of_week)
        parts = [
            f"{format_days(days)}, {format_time(start)} - {format_time(end)}"
            for (start, end), days in sorted(groups.items())
        ]
        return "; ".join(parts)


class ClassSchedule(TimeStampedModel):
    """A weekly recurring slot for a class (e.g. Yoga, Wednesdays 6-7AM)."""

    class Day(models.IntegerChoices):
        MONDAY = 0, "Monday"
        TUESDAY = 1, "Tuesday"
        WEDNESDAY = 2, "Wednesday"
        THURSDAY = 3, "Thursday"
        FRIDAY = 4, "Friday"
        SATURDAY = 5, "Saturday"
        SUNDAY = 6, "Sunday"

    gym_class = models.ForeignKey(GymClass, on_delete=models.CASCADE, related_name="schedules")
    day_of_week = models.PositiveSmallIntegerField(choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        ordering = ["gym_class__name", "day_of_week", "start_time"]
        unique_together = [("gym_class", "day_of_week", "start_time")]

    def __str__(self):
        return (
            f"{self.gym_class.name} - {DAY_ABBR[self.day_of_week]} "
            f"{format_time(self.start_time)}-{format_time(self.end_time)}"
        )

    def clean(self):
        super().clean()
        if self.start_time and self.end_time and self.end_time <= self.start_time:
            raise ValidationError({"end_time": "End time must be after the start time."})


# ---------------------------------------------------------------------------
# Bookings & enquiries
# ---------------------------------------------------------------------------
class Booking(TimeStampedModel):
    class Status(models.TextChoices):
        CONFIRMED = "confirmed", "Confirmed"
        CANCELLED = "cancelled", "Cancelled"
        ATTENDED = "attended", "Attended"

    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, related_name="bookings")
    schedule = models.ForeignKey(ClassSchedule, on_delete=models.CASCADE, related_name="bookings")
    date = models.DateField(help_text="The actual date of the session.")
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.CONFIRMED)

    class Meta:
        ordering = ["-date", "schedule__start_time"]
        unique_together = [("member", "schedule", "date")]

    def __str__(self):
        return f"{self.member} - {self.schedule} on {self.date}"

    def clean(self):
        super().clean()
        if self.schedule_id and self.date and self.date.weekday() != self.schedule.day_of_week:
            raise ValidationError(
                {"date": f"This class runs on {self.schedule.get_day_of_week_display()}s only."}
            )


class Enquiry(TimeStampedModel):
    """Messages from the Contact page, including membership enquiries."""

    class Kind(models.TextChoices):
        CONTACT = "contact", "General contact"
        MEMBERSHIP = "membership", "Membership enquiry"

    class Status(models.TextChoices):
        NEW = "new", "New"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"

    kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.CONTACT)
    name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, validators=[phone_validator])
    subject = models.CharField(max_length=150, blank=True)
    message = models.TextField()
    plan = models.ForeignKey(
        MembershipPlan, null=True, blank=True, on_delete=models.SET_NULL, related_name="enquiries"
    )
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.NEW)
    admin_notes = models.TextField(blank=True, help_text="Internal notes - never shown to the visitor.")

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "enquiries"

    def __str__(self):
        return f"{self.name} - {self.subject or self.get_kind_display()}"
