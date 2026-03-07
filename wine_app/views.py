import uuid
import random
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from .models import Competition, Wine, Round, Pairing, Vote
from .forms import CompetitionForm, WineForm


def get_or_create_cookie_id(request):
    cookie_name = "wine_competition_id"
    cookie_id = request.COOKIES.get(cookie_name)
    if not cookie_id:
        cookie_id = str(uuid.uuid4())
    return cookie_id


def home(request):
    competitions = Competition.objects.exclude(status="draft")
    return render(request, "home.html", {"competitions": competitions})


def register(request):
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация успешна!")
            return redirect("home")
    else:
        form = UserCreationForm()
    return render(request, "register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "Вход выполнен!")
            return redirect("home")
    else:
        form = AuthenticationForm()
    return render(request, "login.html", {"form": form})


def logout_view(request):
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect("home")


@login_required
def competition_list(request):
    competitions = Competition.objects.filter(organizer=request.user)
    return render(request, "competition_list.html", {"competitions": competitions})


@login_required
def competition_create(request):
    if request.method == "POST":
        form = CompetitionForm(request.POST)
        if form.is_valid():
            competition = form.save(commit=False)
            competition.organizer = request.user
            competition.save()
            messages.success(request, "Соревнование создано!")
            return redirect("competition_detail", competition_id=competition.id)
    else:
        form = CompetitionForm()
    return render(request, "competition_create.html", {"form": form})


@login_required
def competition_detail(request, competition_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )
    wines = competition.wines.all()
    rounds = competition.rounds.all().order_by("-round_number")

    current_round = competition.current_round

    return render(
        request,
        "competition_detail.html",
        {
            "competition": competition,
            "wines": wines,
            "rounds": rounds,
            "current_round": current_round,
        },
    )


@login_required
def wine_add(request, competition_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )

    if competition.status != "draft":
        messages.error(
            request, "Нельзя добавлять вина в запущенное или завершённое соревнование."
        )
        return redirect("competition_detail", competition_id=competition.id)

    if request.method == "POST":
        form = WineForm(request.POST, request.FILES)
        if form.is_valid():
            wine = form.save(commit=False)
            wine.competition = competition
            wine.order = competition.wines.count() + 1
            wine.save()
            messages.success(request, "Вино добавлено!")
            return redirect("competition_detail", competition_id=competition.id)
    else:
        form = WineForm()
    return render(request, "wine_form.html", {"form": form, "competition": competition})


@login_required
def start_competition(request, competition_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )

    if competition.status != "draft":
        messages.error(request, "Соревнование уже запущено.")
        return redirect("competition_detail", competition_id=competition.id)

    if competition.wines.count() < 2:
        messages.error(request, "Нужно минимум 2 вина для начала.")
        return redirect("competition_detail", competition_id=competition.id)

    competition.status = "running"
    competition.save()

    first_round = Round.objects.create(
        competition=competition,
        round_number=1,
        status="active",
    )

    create_pairings(first_round)

    messages.success(request, "Соревнование запущено!")
    return redirect("competition_detail", competition_id=competition.id)


def create_pairings(round_obj):
    competition = round_obj.competition

    if round_obj.round_number == 1:
        wines = list(competition.wines.all())
    else:
        previous_round = Round.objects.get(
            competition=competition, round_number=round_obj.round_number - 1
        )
        wines = [p.winner for p in previous_round.pairings.all() if p.winner]

    random.shuffle(wines)

    pairings = []
    for i in range(0, len(wines) - 1, 2):
        if i + 1 < len(wines):
            pairing = Pairing.objects.create(
                round=round_obj,
                wine1=wines[i],
                wine2=wines[i + 1],
                order=i // 2,
                status="pending",
            )
            pairings.append(pairing)

    if len(wines) % 2 == 1 and wines:
        last_wine = wines[-1]
        if Round.objects.filter(
            competition=competition, round_number=round_obj.round_number - 1
        ).exists():
            prev_round = Round.objects.get(
                competition=competition, round_number=round_obj.round_number - 1
            )
            if prev_round.pairings.count() > 0:
                last_pairing = prev_round.pairings.order_by("-order").first()
                if last_pairing and not last_pairing.winner:
                    last_pairing.wine2 = last_wine
                    last_pairing.save()

    return pairings


@login_required
def end_round(request, competition_id, round_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )
    round_obj = get_object_or_404(Round, id=round_id, competition=competition)

    if round_obj.status != "active":
        messages.error(request, "Раунд не активен.")
        return redirect("competition_detail", competition_id=competition.id)

    for pairing in round_obj.pairings.all():
        if pairing.votes_wine1 > pairing.votes_wine2:
            pairing.winner = pairing.wine1
        elif pairing.votes_wine2 > pairing.votes_wine1:
            pairing.winner = pairing.wine2
        else:
            winner = random.choice([pairing.wine1, pairing.wine2])
            pairing.winner = winner
        pairing.save()

    round_obj.status = "completed"
    round_obj.save()

    remaining_wines = [p.winner for p in round_obj.pairings.all() if p.winner]

    if len(remaining_wines) <= 1:
        competition.status = "finished"
        competition.save()
        messages.success(request, "Соревнование завершено!")
    else:
        next_round = Round.objects.create(
            competition=competition,
            round_number=round_obj.round_number + 1,
            status="active",
        )
        create_pairings(next_round)
        messages.success(
            request,
            f"Раунд {round_obj.round_number} завершён. Начат раунд {next_round.round_number}!",
        )

    return redirect("competition_detail", competition_id=competition.id)


@login_required
def start_pairing(request, competition_id, pairing_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )
    pairing = get_object_or_404(Pairing, id=pairing_id, round__competition=competition)

    if pairing.status != "pending":
        messages.error(request, "Пара уже активна или завершена.")
        return redirect("competition_detail", competition_id=competition.id)

    active_pairings = Pairing.objects.filter(
        round__competition=competition, round__status="active", status="active"
    )
    if active_pairings.exists():
        messages.error(
            request, "Уже есть активная пара. Завершите её перед запуском новой."
        )
        return redirect("competition_detail", competition_id=competition.id)

    pairing.status = "active"
    pairing.save()

    messages.success(
        request, f"Пара {pairing.wine1.name} vs {pairing.wine2.name} активирована!"
    )
    return redirect("competition_detail", competition_id=competition.id)


@login_required
def end_pairing(request, competition_id, pairing_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )
    pairing = get_object_or_404(Pairing, id=pairing_id, round__competition=competition)

    if pairing.status != "active":
        messages.error(request, "Пара не активна.")
        return redirect("competition_detail", competition_id=competition.id)

    if pairing.votes_wine1 > pairing.votes_wine2:
        pairing.winner = pairing.wine1
    elif pairing.votes_wine2 > pairing.votes_wine1:
        pairing.winner = pairing.wine2
    else:
        pairing.winner = random.choice([pairing.wine1, pairing.wine2])

    pairing.status = "completed"
    pairing.save()

    messages.success(request, f"Пара завершена! Победитель: {pairing.winner.name}")
    return redirect("competition_detail", competition_id=competition.id)


@ensure_csrf_cookie
def competition_view(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    current_round = competition.current_round

    cookie_id = get_or_create_cookie_id(request)
    response = render(
        request,
        "voting.html",
        {
            "competition": competition,
            "current_round": current_round,
            "cookie_id": cookie_id,
        },
    )
    response.set_cookie("wine_competition_id", cookie_id, max_age=60 * 60 * 24 * 365)
    return response


@require_POST
def vote(request, pairing_id):
    pairing = get_object_or_404(Pairing, id=pairing_id)
    wine_id = request.POST.get("wine_id")
    participant_name = request.POST.get("participant_name", "").strip()

    cookie_id = request.COOKIES.get("wine_competition_id")
    if not cookie_id:
        return JsonResponse({"error": "Cookie not found"}, status=400)

    if Vote.objects.filter(pairing=pairing, cookie_id=cookie_id).exists():
        return JsonResponse({"error": "Already voted"}, status=400)

    wine = get_object_or_404(
        Wine, id=wine_id, id__in=[pairing.wine1.id, pairing.wine2.id]
    )

    Vote.objects.create(
        pairing=pairing,
        wine=wine,
        cookie_id=cookie_id,
        participant_name=participant_name,
    )

    if wine == pairing.wine1:
        pairing.votes_wine1 += 1
    else:
        pairing.votes_wine2 += 1
    pairing.save()

    return JsonResponse(
        {
            "success": True,
            "votes_wine1": pairing.votes_wine1,
            "votes_wine2": pairing.votes_wine2,
        }
    )


def statistics(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    wine_stats = []
    for wine in competition.wines.all():
        votes = Vote.objects.filter(wine=wine).count()
        wine_stats.append({"wine": wine, "votes": votes})

    wine_stats.sort(key=lambda x: x["votes"], reverse=True)

    return render(
        request,
        "statistics.html",
        {
            "competition": competition,
            "wine_stats": wine_stats,
        },
    )


def tournament(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    rounds = competition.rounds.all().order_by("round_number")

    return render(
        request,
        "tournament.html",
        {
            "competition": competition,
            "rounds": rounds,
        },
    )


@login_required
def reset_competition(request, competition_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )

    Round.objects.filter(competition=competition).delete()

    competition.status = "draft"
    competition.save()

    messages.success(
        request, "Соревнование сброшено. Можете добавить вина и запустить заново."
    )
    return redirect("competition_detail", competition_id=competition.id)
