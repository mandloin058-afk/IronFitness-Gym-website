from django.contrib.auth import views as auth_views
from django.urls import path
from django.views.generic import RedirectView   # ye nayi line
from . import views
from .forms import LoginForm

urlpatterns = [
    path("", views.home, name="home"),
    path("index/", views.home, name="index"),
    path("01/", views.about_page, name="about"),
    # path("about/", views.about_page, name="about"),
    path("02/", views.services_page, name="services"),
    path("03/", views.classes_page, name="classes"),
    path("04/", views.membership_page, name="membership"),
    path("05/", views.contact_page, name="contact"),
    path("06/", views.trainers_page, name="trainers"),
    path("07/", views.register, name="register"),
    path("08/", auth_views.LoginView.as_view(
        template_name="gym/login.html",
        authentication_form=LoginForm,
        redirect_authenticated_user=True,
    ), name="login"),
    path("09/", auth_views.LogoutView.as_view(), name="logout"),
    path("10/", views.dashboard, name="dashboard"),
    path("04/join/<slug:slug>/", views.join_plan, name="join_plan"),
    path("11/", views.book_class, name="book_class"),
    path("bookings/<int:pk>/cancel/", views.cancel_booking, name="cancel_booking"),
]
