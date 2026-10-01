from django.contrib import admin, messages

from .models import (
    Booking,
    ClassSchedule,
    Enquiry,
    GymClass,
    MemberProfile,
    MembershipPlan,
    Subscription,
    Trainer,
)

admin.site.site_header = "Iron Fitness Gym - Admin"
admin.site.site_title = "Iron Fitness Admin"
admin.site.index_title = "Gym management"


# --- Members ----------------------------------------------------------------
class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0
    fields = ("plan", "status", "start_date", "end_date", "price_paid")


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ("member_name", "member_email", "phone", "gender", "created_at")
    list_filter = ("gender", "created_at")
    search_fields = ("user__email", "user__first_name", "user__last_name", "phone")
    list_select_related = ("user",)
    raw_id_fields = ("user",)
    readonly_fields = ("created_at", "updated_at")
    inlines = [SubscriptionInline]

    @admin.display(description="Name", ordering="user__first_name")
    def member_name(self, obj):
        return obj.full_name

    @admin.display(description="Email", ordering="user__email")
    def member_email(self, obj):
        return obj.user.email


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    list_display = (
        "name", "price", "duration_days", "includes_classes",
        "includes_personal_trainer", "is_popular", "is_active", "display_order",
    )
    list_editable = ("price", "is_active", "display_order")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "description")


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ("member", "plan", "status", "start_date", "end_date", "price_paid", "created_at")
    list_filter = ("status", "plan")
    search_fields = ("member__user__email", "member__user__first_name", "member__user__last_name", "member__phone")
    list_select_related = ("member__user", "plan")
    autocomplete_fields = ("member",)
    actions = ["activate_selected", "cancel_selected"]

    @admin.action(description="Activate selected memberships (starts today)")
    def activate_selected(self, request, queryset):
        count = 0
        for sub in queryset.select_related("plan"):
            if sub.status in (Subscription.Status.PENDING, Subscription.Status.EXPIRED):
                sub.activate()
                count += 1
        self.message_user(request, f"{count} membership(s) activated.", messages.SUCCESS)

    @admin.action(description="Cancel selected memberships")
    def cancel_selected(self, request, queryset):
        count = queryset.exclude(status=Subscription.Status.CANCELLED).update(status=Subscription.Status.CANCELLED)
        self.message_user(request, f"{count} membership(s) cancelled.", messages.SUCCESS)


# --- Trainers & classes -----------------------------------------------------
@admin.register(Trainer)
class TrainerAdmin(admin.ModelAdmin):
    list_display = ("name", "specialization", "experience_years", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    search_fields = ("name", "specialization")
    list_filter = ("is_active",)


class ClassScheduleInline(admin.TabularInline):
    model = ClassSchedule
    extra = 1


@admin.register(GymClass)
class GymClassAdmin(admin.ModelAdmin):
    list_display = ("name", "trainer", "capacity", "schedule_summary", "is_active")
    list_filter = ("is_active", "trainer")
    search_fields = ("name", "description")
    inlines = [ClassScheduleInline]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("trainer").prefetch_related("schedules")

    @admin.display(description="Schedule")
    def schedule_summary(self, obj):
        return obj.schedule_display


# --- Bookings ---------------------------------------------------------------
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ("member", "class_name", "date", "start_time", "status", "created_at")
    list_filter = ("status", "date", "schedule__gym_class")
    search_fields = ("member__user__email", "member__user__first_name", "member__user__last_name")
    list_select_related = ("member__user", "schedule__gym_class")
    autocomplete_fields = ("member",)
    date_hierarchy = "date"
    actions = ["mark_attended", "mark_cancelled"]

    @admin.display(description="Class", ordering="schedule__gym_class__name")
    def class_name(self, obj):
        return obj.schedule.gym_class.name

    @admin.display(description="Starts", ordering="schedule__start_time")
    def start_time(self, obj):
        return obj.schedule.start_time

    @admin.action(description="Mark selected as attended")
    def mark_attended(self, request, queryset):
        count = queryset.update(status=Booking.Status.ATTENDED)
        self.message_user(request, f"{count} booking(s) marked as attended.", messages.SUCCESS)

    @admin.action(description="Cancel selected bookings")
    def mark_cancelled(self, request, queryset):
        count = queryset.update(status=Booking.Status.CANCELLED)
        self.message_user(request, f"{count} booking(s) cancelled.", messages.SUCCESS)


# --- Enquiries --------------------------------------------------------------
@admin.register(Enquiry)
class EnquiryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "name", "email", "phone", "kind", "subject", "plan", "status")
    list_display_links = ("name",)
    list_editable = ("status",)
    list_filter = ("status", "kind", "created_at")
    search_fields = ("name", "email", "phone", "subject", "message")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_in_progress", "mark_resolved"]

    @admin.action(description="Mark selected as in progress")
    def mark_in_progress(self, request, queryset):
        count = queryset.update(status=Enquiry.Status.IN_PROGRESS)
        self.message_user(request, f"{count} enquiry(ies) marked in progress.", messages.SUCCESS)

    @admin.action(description="Mark selected as resolved")
    def mark_resolved(self, request, queryset):
        count = queryset.update(status=Enquiry.Status.RESOLVED)
        self.message_user(request, f"{count} enquiry(ies) marked resolved.", messages.SUCCESS)
