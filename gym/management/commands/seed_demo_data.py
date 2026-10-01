from datetime import time
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from gym.models import ClassSchedule, GymClass, MembershipPlan, Trainer

PLANS = [
    {
        "name": "Basic Plan", "price": Decimal("999"), "display_order": 1,
        "description": "Access to gym equipment only.",
        "features": "Access to gym equipment",
        "includes_classes": False, "includes_personal_trainer": False, "is_popular": False,
    },
    {
        "name": "Standard Plan", "price": Decimal("1499"), "display_order": 2,
        "description": "Includes classes & trainers.",
        "features": "Access to gym equipment\nGroup classes\nTrainer guidance",
        "includes_classes": True, "includes_personal_trainer": False, "is_popular": True,
    },
    {
        "name": "Premium Plan", "price": Decimal("2499"), "display_order": 3,
        "description": "All access + diet plan + personal trainer.",
        "features": "All-access pass\nDiet plan\nPersonal trainer",
        "includes_classes": True, "includes_personal_trainer": True, "is_popular": False,
    },
]

# PLACEHOLDER trainers - edit or replace them in the Django admin.
TRAINERS = [
    {"name": "Aman Verma", "specialization": "Strength & Conditioning", "experience_years": 8,
     "bio": "Placeholder bio - edit in the admin panel."},
    {"name": "Neha Kapoor", "specialization": "Yoga & Mobility", "experience_years": 6,
     "bio": "Placeholder bio - edit in the admin panel."},
    {"name": "Rohit Mehra", "specialization": "CrossFit", "experience_years": 5,
     "bio": "Placeholder bio - edit in the admin panel."},
    {"name": "Priya Nair", "specialization": "Zumba & Dance Fitness", "experience_years": 4,
     "bio": "Placeholder bio - edit in the admin panel."},
]

# Days: 0 = Monday ... 6 = Sunday. Timetable copied from the existing classes.html.
CLASSES = [
    {"name": "Weight Training", "icon": "\U0001F3CB\uFE0F", "trainer": "Aman Verma", "capacity": 25,
     "description": "Guided strength training with free weights and machines.",
     "days": [0, 1, 2, 3, 4], "start": time(7, 0), "end": time(9, 0)},
    {"name": "Yoga", "icon": "\U0001F9D8", "trainer": "Neha Kapoor", "capacity": 20,
     "description": "Flexibility, balance and breathing to start your day.",
     "days": [0, 2, 4], "start": time(6, 0), "end": time(7, 0)},
    {"name": "Zumba", "icon": "\U0001F525", "trainer": "Priya Nair", "capacity": 30,
     "description": "High-energy dance workout set to Latin and pop music.",
     "days": [1, 3], "start": time(18, 0), "end": time(19, 0)},
    {"name": "CrossFit", "icon": "\U0001F4AA", "trainer": "Rohit Mehra", "capacity": 15,
     "description": "Functional, high-intensity training for all levels.",
     "days": [0, 1, 2, 3, 4, 5], "start": time(17, 0), "end": time(18, 0)},
]


class Command(BaseCommand):
    help = (
        "Load starter plans, trainers and classes matching the current website. "
        "Safe to re-run: existing records are never overwritten."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        created = {"plans": 0, "trainers": 0, "classes": 0, "slots": 0}

        for data in PLANS:
            data = dict(data)
            _, was_created = MembershipPlan.objects.get_or_create(name=data.pop("name"), defaults=data)
            created["plans"] += was_created

        trainers = {}
        for data in TRAINERS:
            data = dict(data)
            trainer, was_created = Trainer.objects.get_or_create(name=data.pop("name"), defaults=data)
            trainers[trainer.name] = trainer
            created["trainers"] += was_created

        for data in CLASSES:
            gym_class, was_created = GymClass.objects.get_or_create(
                name=data["name"],
                defaults={
                    "icon": data["icon"],
                    "description": data["description"],
                    "capacity": data["capacity"],
                    "trainer": trainers.get(data["trainer"]),
                },
            )
            created["classes"] += was_created
            if was_created:
                for day in data["days"]:
                    ClassSchedule.objects.create(
                        gym_class=gym_class, day_of_week=day,
                        start_time=data["start"], end_time=data["end"],
                    )
                    created["slots"] += 1

        self.stdout.write(self.style.SUCCESS(
            "Seeded {plans} plans, {trainers} trainers, {classes} classes, {slots} weekly slots.".format(**created)
        ))
