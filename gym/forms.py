from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import (
    Booking,
    ClassSchedule,
    Enquiry,
    MemberProfile,
    MembershipPlan,
    format_time,
    phone_validator,
)

User = get_user_model()


class BootstrapFormMixin:
    """Adds Bootstrap's `form-control` class to visible widgets (Bootstrap 4 and 5)."""

    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if widget.is_hidden:
                continue
            css = "form-check-input" if isinstance(widget, forms.CheckboxInput) else "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


# ---------------------------------------------------------------------------
# Registration & login
# ---------------------------------------------------------------------------
class RegistrationForm(BootstrapFormMixin, forms.Form):
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(max_length=150)
    phone = forms.CharField(max_length=20, validators=[phone_validator])
    gender = forms.ChoiceField(
        choices=[("", "Select gender (optional)")] + list(MemberProfile.Gender.choices),
        required=False,
    )
    date_of_birth = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    fitness_goal = forms.CharField(max_length=200, required=False)
    password1 = forms.CharField(
        label="Password", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )
    password2 = forms.CharField(
        label="Confirm password", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "new-password"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if (
            User.objects.filter(username__iexact=email).exists()
            or User.objects.filter(email__iexact=email).exists()
        ):
            raise ValidationError("An account with this email already exists. Try logging in instead.")
        return email

    def clean_date_of_birth(self):
        dob = self.cleaned_data.get("date_of_birth")
        if dob and dob > timezone.localdate():
            raise ValidationError("Date of birth cannot be in the future.")
        return dob

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "The two passwords do not match.")
        elif p1:
            candidate = User(
                username=cleaned.get("email", ""),
                email=cleaned.get("email", ""),
                first_name=cleaned.get("first_name", ""),
                last_name=cleaned.get("last_name", ""),
            )
            try:
                validate_password(p1, candidate)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return cleaned

    @transaction.atomic
    def save(self):
        d = self.cleaned_data
        user = User.objects.create_user(
            username=d["email"],  # the email is the login name
            email=d["email"],
            password=d["password1"],
            first_name=d["first_name"],
            last_name=d.get("last_name", ""),
        )
        MemberProfile.objects.create(
            user=user,
            phone=d["phone"],
            gender=d.get("gender", ""),
            date_of_birth=d.get("date_of_birth"),
            fitness_goal=d.get("fitness_goal", ""),
        )
        return user


class LoginForm(BootstrapFormMixin, AuthenticationForm):
    username = forms.CharField(
        label="Email",
        widget=forms.EmailInput(attrs={"autofocus": True, "autocomplete": "email"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_username(self):
        return self.cleaned_data["username"].strip().lower()


# ---------------------------------------------------------------------------
# Contact / enquiry
# ---------------------------------------------------------------------------
class ContactForm(BootstrapFormMixin, forms.ModelForm):
    # Honeypot: real visitors never see or fill this field; bots often do.
    website = forms.CharField(required=False, widget=forms.TextInput(attrs={"autocomplete": "off", "tabindex": "-1"}))
    plan = forms.ModelChoiceField(
        queryset=MembershipPlan.objects.filter(is_active=True),
        required=False,
        empty_label="Interested in a plan? (optional)",
    )

    class Meta:
        model = Enquiry
        fields = ["name", "email", "phone", "subject", "message", "plan"]
        widgets = {"message": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()

    def clean_website(self):
        if self.cleaned_data.get("website"):
            raise ValidationError("Spam detected.")
        return ""

    def save(self, commit=True):
        enquiry = super().save(commit=False)
        enquiry.kind = Enquiry.Kind.MEMBERSHIP if enquiry.plan_id else Enquiry.Kind.CONTACT
        if commit:
            enquiry.save()
            self._notify(enquiry)
        return enquiry

    @staticmethod
    def _notify(enquiry):
        if not settings.GYM_NOTIFY_EMAIL:
            return
        subject_line = " ".join((enquiry.subject or enquiry.name).split())  # no newlines in headers
        body = (
            f"Type: {enquiry.get_kind_display()}\n"
            f"Name: {enquiry.name}\n"
            f"Email: {enquiry.email}\n"
            f"Phone: {enquiry.phone or '-'}\n"
            f"Plan: {enquiry.plan or '-'}\n\n"
            f"{enquiry.message}\n"
        )
        send_mail(
            subject=f"[Iron Fitness] New enquiry: {subject_line}",
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.GYM_NOTIFY_EMAIL],
            fail_silently=True,
        )


# ---------------------------------------------------------------------------
# Class booking
# ---------------------------------------------------------------------------
class BookingForm(BootstrapFormMixin, forms.Form):
    schedule = forms.ModelChoiceField(
        queryset=ClassSchedule.objects.none(), label="Class & time", empty_label="Select a class"
    )
    date = forms.DateField(label="Date", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, member, **kwargs):
        super().__init__(*args, **kwargs)
        self.member = member
        field = self.fields["schedule"]
        field.queryset = ClassSchedule.objects.filter(gym_class__is_active=True).select_related("gym_class")
        field.label_from_instance = lambda s: (
            f"{s.gym_class.name} - {s.get_day_of_week_display()} "
            f"{format_time(s.start_time)}-{format_time(s.end_time)}"
        )
        today = timezone.localdate()
        self.fields["date"].widget.attrs.update(
            {
                "min": today.isoformat(),
                "max": (today + timedelta(days=settings.BOOKING_WINDOW_DAYS)).isoformat(),
            }
        )
        self._style_fields()

    def clean_date(self):
        chosen = self.cleaned_data["date"]
        today = timezone.localdate()
        if chosen < today:
            raise ValidationError("Please choose today or a future date.")
        if chosen > today + timedelta(days=settings.BOOKING_WINDOW_DAYS):
            raise ValidationError(f"Bookings open up to {settings.BOOKING_WINDOW_DAYS} days ahead.")
        return chosen

    def clean(self):
        cleaned = super().clean()
        if settings.REQUIRE_ACTIVE_MEMBERSHIP_FOR_BOOKING:
            sub = self.member.active_subscription()
            if sub is None or not sub.plan.includes_classes:
                raise ValidationError(
                    "You need an active membership that includes classes (Standard or Premium) "
                    "to book. Request a plan on the Membership page - the front desk activates it "
                    "once payment is received."
                )
        schedule, chosen = cleaned.get("schedule"), cleaned.get("date")
        if schedule and chosen:
            if chosen.weekday() != schedule.day_of_week:
                self.add_error(
                    "date",
                    f"{schedule.gym_class.name} runs on {schedule.get_day_of_week_display()}s. "
                    "Please pick a matching date.",
                )
            elif chosen == timezone.localdate() and schedule.start_time <= timezone.localtime().time():
                self.add_error("date", "That session has already started today.")
        return cleaned

    @transaction.atomic
    def save(self):
        """Create the booking. May raise ValidationError (class full / already booked)."""
        # Lock the slot row so two people can't take the last place at the same time.
        schedule = ClassSchedule.objects.select_for_update().get(pk=self.cleaned_data["schedule"].pk)
        chosen = self.cleaned_data["date"]
        taken = Booking.objects.filter(
            schedule=schedule, date=chosen, status=Booking.Status.CONFIRMED
        ).count()
        if taken >= schedule.gym_class.capacity:
            raise ValidationError("Sorry, this class is full for the selected date.")
        booking, created = Booking.objects.get_or_create(
            member=self.member,
            schedule=schedule,
            date=chosen,
            defaults={"status": Booking.Status.CONFIRMED},
        )
        if not created:
            if booking.status == Booking.Status.CONFIRMED:
                raise ValidationError("You have already booked this class for that date.")
            booking.status = Booking.Status.CONFIRMED  # re-book after an earlier cancellation
            booking.save(update_fields=["status", "updated_at"])
        return booking
