from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BookingForm, ContactForm, RegistrationForm
from .models import (
    Booking,
    GymClass,
    MemberProfile,
    MembershipPlan,
    Subscription,
    Trainer,
)


# ---------------------------------------------------------------------------
# Public pages
# ---------------------------------------------------------------------------

def home(request):
    plans = MembershipPlan.objects.filter(is_active=True)[:3]
    trainers = Trainer.objects.filter(is_active=True)[:3]
    classes = (
        GymClass.objects
        .filter(is_active=True)
        .select_related("trainer")[:4]
    )

    return render(
        request,
        "gym/index.html",
        {
            "plans": plans,
            "trainers": trainers,
            "classes": classes,
        },
    )


def about_page(request):
    return render(request, "about.html")


def services_page(request):
    return render(request, "services.html")


def classes_page(request):
    classes = (
        GymClass.objects
        .filter(is_active=True)
        .select_related("trainer")
        .prefetch_related("schedules")
    )

    return render(
        request,
        "classes.html",
        {"classes": classes},
    )


def membership_page(request):
    plans = MembershipPlan.objects.filter(is_active=True)

    return render(
        request,
        "membership.html",
        {"plans": plans},
    )


def trainers_page(request):
    trainers = Trainer.objects.filter(is_active=True)

    return render(
        request,
        "gym/trainers.html",
        {"trainers": trainers},
    )


def contact_page(request):
    plans = MembershipPlan.objects.filter(is_active=True)

    if request.method == "POST":
        form = ContactForm(request.POST)

        if form.is_valid():
            form.save()

            messages.success(
                request,
                "Thank you! We've received your message and will get back to you soon.",
            )

            return redirect("contact")

    else:
        initial = {}

        if request.user.is_authenticated:
            initial.update(
                name=request.user.get_full_name(),
                email=request.user.email,
            )

        plan = plans.filter(
            slug=request.GET.get("plan", "")
        ).first()

        if plan:
            initial["plan"] = plan.pk

        form = ContactForm(initial=initial)

    return render(
        request,
        "contact.html",
        {
            "form": form,
            "plans": plans,
        },
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()

            # Create MemberProfile for the new user
            MemberProfile.objects.get_or_create(user=user)

            login(request, user)

            messages.success(
                request,
                f"Welcome to Iron Fitness, {user.first_name}! Your account is ready.",
            )

            return redirect("dashboard")

    else:
        form = RegistrationForm()

    return render(
        request,
        "gym/register.html",
        {"form": form},
    )


# ---------------------------------------------------------------------------
# Member Profile
# ---------------------------------------------------------------------------

def _get_profile(user):
    """
    Get the MemberProfile for the logged-in user.
    If it does not exist, create it automatically.
    """
    profile, created = MemberProfile.objects.get_or_create(
        user=user
    )

    return profile


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def dashboard(request):
    profile = _get_profile(request.user)

    today = timezone.localdate()

    bookings = (
        profile.bookings
        .select_related("schedule__gym_class__trainer")
    )

    context = {
        "profile": profile,

        "active_subscription": profile.active_subscription(),

        "subscriptions": (
            profile.subscriptions
            .select_related("plan")
        ),

        "upcoming": (
            bookings
            .filter(
                date__gte=today,
                status=Booking.Status.CONFIRMED,
            )
            .order_by(
                "date",
                "schedule__start_time",
            )
        ),

        "history": (
            bookings
            .filter(
                Q(date__lt=today)
                | ~Q(status=Booking.Status.CONFIRMED)
            )
            .order_by("-date")[:10]
        ),
    }

    return render(
        request,
        "gym/dashboard.html",
        context,
    )


# ---------------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------------

@login_required
def join_plan(request, slug):
    plan = get_object_or_404(
        MembershipPlan,
        slug=slug,
        is_active=True,
    )

    profile = _get_profile(request.user)

    if request.method == "POST":

        already = profile.subscriptions.filter(
            plan=plan,
            status__in=[
                Subscription.Status.PENDING,
                Subscription.Status.ACTIVE,
            ],
        ).exists()

        if already:
            messages.info(
                request,
                f"You already have a pending or active {plan.name} membership.",
            )

        else:
            Subscription.objects.create(
                member=profile,
                plan=plan,
                status=Subscription.Status.PENDING,
            )

            messages.success(
                request,
                f"Your {plan.name} request has been received. "
                "The front desk will activate it once payment is made.",
            )

        return redirect("dashboard")

    return render(
        request,
        "gym/join_plan.html",
        {"plan": plan},
    )


# ---------------------------------------------------------------------------
# Class bookings
# ---------------------------------------------------------------------------

@login_required
def book_class(request):
    profile = _get_profile(request.user)

    if request.method == "POST":

        form = BookingForm(
            request.POST,
            member=profile,
        )

        if form.is_valid():

            try:
                booking = form.save()

            except ValidationError as exc:
                form.add_error(None, exc)

            else:
                messages.success(
                    request,
                    f"Booked: {booking.schedule.gym_class.name} "
                    f"on {booking.date:%a, %d %b %Y}.",
                )

                return redirect("dashboard")

    else:
        initial = {}

        schedule_id = request.GET.get("schedule", "")

        if schedule_id.isdigit():
            initial["schedule"] = int(schedule_id)

        form = BookingForm(
            initial=initial,
            member=profile,
        )

    return render(
        request,
        "gym/book_class.html",
        {"form": form},
    )


# ---------------------------------------------------------------------------
# Cancel booking
# ---------------------------------------------------------------------------

@login_required
@require_POST
def cancel_booking(request, pk):

    booking = get_object_or_404(
        Booking,
        pk=pk,
        member=_get_profile(request.user),
    )

    if booking.status != Booking.Status.CONFIRMED:

        messages.info(
            request,
            "That booking is not active.",
        )

    elif booking.date < timezone.localdate():

        messages.error(
            request,
            "Past bookings can't be cancelled.",
        )

    else:

        booking.status = Booking.Status.CANCELLED

        booking.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        messages.success(
            request,
            "Your booking has been cancelled.",
        )

    return redirect("dashboard")