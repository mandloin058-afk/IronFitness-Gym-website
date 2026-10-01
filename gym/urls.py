from django.contrib.auth import views as auth_views
from django.urls import path
from . import views
from .forms import LoginForm

urlpatterns = [
    path("", views.home, name="home"),
    path("index.html", views.home, name="index"),
    path("about.html", views.about_page, name="about"),
    path("services.html", views.services_page, name="services"),
    path("classes.html", views.classes_page, name="classes"),
    path("membership.html", views.membership_page, name="membership"),
    path("contact.html", views.contact_page, name="contact"),
    path("trainers.html", views.trainers_page, name="trainers"),
    path("register/", views.register, name="register"),
    path("login/", auth_views.LoginView.as_view(
        template_name="gym/login.html",
        authentication_form=LoginForm,
        redirect_authenticated_user=True,
    ), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("membership/join/<slug:slug>/", views.join_plan, name="join_plan"),
    path("book/", views.book_class, name="book_class"),
    path("bookings/<int:pk>/cancel/", views.cancel_booking, name="cancel_booking"),
]
