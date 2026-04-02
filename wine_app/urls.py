from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("register/", views.register, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("competitions/", views.competition_list, name="competition_list"),
    path("competitions/create/", views.competition_create, name="competition_create"),
    path(
        "competitions/<int:competition_id>/",
        views.competition_detail,
        name="competition_detail",
    ),
    path(
        "competitions/<int:competition_id>/add-wine/", views.wine_add, name="wine_add"
    ),
    path(
        "competitions/<int:competition_id>/existing-wines/",
        views.existing_wines_api,
        name="existing_wines_api",
    ),
    path(
        "competitions/<int:competition_id>/copy-wine/<int:wine_id>/",
        views.wine_copy,
        name="wine_copy",
    ),
    path(
        "competitions/<int:competition_id>/start/",
        views.start_competition,
        name="start_competition",
    ),
    path(
        "competitions/<int:competition_id>/end-round/<int:round_id>/",
        views.end_round,
        name="end_round",
    ),
    path(
        "competitions/<int:competition_id>/start-pairing/<int:pairing_id>/",
        views.start_pairing,
        name="start_pairing",
    ),
    path(
        "competitions/<int:competition_id>/end-pairing/<int:pairing_id>/",
        views.end_pairing,
        name="end_pairing",
    ),
    path(
        "competitions/<int:competition_id>/reset/",
        views.reset_competition,
        name="reset_competition",
    ),
    path(
        "competition/<int:competition_id>/",
        views.competition_view,
        name="competition_view",
    ),
    path("vote/<int:pairing_id>/", views.vote, name="vote"),
    path(
        "competition/<int:competition_id>/statistics/",
        views.statistics,
        name="statistics",
    ),
    path(
        "competition/<int:competition_id>/tournament/",
        views.tournament,
        name="tournament",
    ),
]
