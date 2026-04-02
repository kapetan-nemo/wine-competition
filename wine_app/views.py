import uuid
import re
import random
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Max, Count, Q, Prefetch
from django.db.models.functions import Coalesce
from .models import Competition, Wine, Round, Pairing, Vote
from .forms import CompetitionForm, WineForm, CustomUserCreationForm, CustomAuthenticationForm

logger = logging.getLogger(__name__)

# Compiled UUID-v4 pattern for validating voter cookie_id
_COOKIE_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
)


def generate_cookie_id(request):
    """Return existing voter UUID from cookies, or generate a new one.

    NOTE: The caller is responsible for setting the cookie in the response.
    """
    cookie_id = request.COOKIES.get("wine_competition_id")
    if not cookie_id:
        cookie_id = str(uuid.uuid4())
    return cookie_id


def home(request):
    competitions_list = Competition.objects.exclude(status="draft").order_by("-date", "-id")
    paginator = Paginator(competitions_list, 10)
    page_number = request.GET.get("page")
    competitions = paginator.get_page(page_number)
    return render(request, "home.html", {"competitions": competitions})


def register(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация успешна!")
            return redirect("home")
    else:
        form = CustomUserCreationForm()
    return render(request, "register.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = CustomAuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "Вход выполнен!")
            return redirect("home")
    else:
        form = CustomAuthenticationForm()
    return render(request, "login.html", {"form": form})


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "Вы вышли из системы.")
    return redirect("home")


@login_required
def competition_list(request):
    competitions_list = Competition.objects.filter(organizer=request.user).order_by("-date", "-id")
    paginator = Paginator(competitions_list, 10)
    page_number = request.GET.get("page")
    competitions = paginator.get_page(page_number)
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
    rounds = competition.rounds.prefetch_related(
        Prefetch(
            'pairings',
            queryset=Pairing.objects.select_related('wine1', 'wine2', 'winner').order_by('order'),
        )
    ).all().order_by("-round_number")

    current_round = competition.current_round
    all_pairings_completed = False
    current_pairings = None
    if current_round:
        all_pairings_completed = not current_round.pairings.exclude(status="completed").exists()
        current_pairings = current_round.pairings.select_related('wine1', 'wine2', 'winner').all()

    return render(
        request,
        "competition_detail.html",
        {
            "competition": competition,
            "wines": wines,
            "rounds": rounds,
            "current_round": current_round,
            "current_pairings": current_pairings,
            "all_pairings_completed": all_pairings_completed,
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
            wine.order = competition.wines.aggregate(
                m=Coalesce(Max('order'), 0)
            )['m'] + 1
            wine.save()
            messages.success(request, "Вино добавлено!")
            return redirect("competition_detail", competition_id=competition.id)
    else:
        form = WineForm()
    return render(request, "wine_form.html", {"form": form, "competition": competition})


@login_required
def existing_wines_api(request, competition_id):
    """Return JSON list of wines from this user's other competitions."""
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )
    # Only show wines from THIS user's competitions (not all users)
    other_wines = Wine.objects.filter(
        competition__organizer=request.user
    ).exclude(
        competition=competition
    ).select_related('competition').order_by('-competition__created_at', 'name')

    # Also exclude wines already in this competition (by name+country)
    existing_names = set(
        competition.wines.values_list('name', 'country')
    )

    wines_data = []
    for wine in other_wines:
        if (wine.name, wine.country) in existing_names:
            continue
        wines_data.append({
            'id': wine.id,
            'name': wine.name,
            'country': wine.country,
            'vintage': wine.vintage or '',
            'grape_variety': wine.grape_variety or '',
            'competition_title': wine.competition.title,
            'has_image': bool(wine.image),
        })

    return JsonResponse({'wines': wines_data})


@require_POST
@login_required
def wine_copy(request, competition_id, wine_id):
    """Copy a wine from this user's other competition into this one."""
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )

    if competition.status != 'draft':
        return JsonResponse({'error': 'Нельзя добавлять вина в запущенное соревнование.'}, status=400)

    # Only allow copying wines from this user's own competitions
    source_wine = get_object_or_404(Wine, id=wine_id, competition__organizer=request.user)

    # Check if wine with same name already exists in this competition
    if competition.wines.filter(name=source_wine.name, country=source_wine.country).exists():
        return JsonResponse({'error': 'Это вино уже добавлено в соревнование.'}, status=400)

    new_wine = Wine.objects.create(
        competition=competition,
        name=source_wine.name,
        country=source_wine.country,
        image=source_wine.image,
        description=source_wine.description,
        vintage=source_wine.vintage,
        grape_variety=source_wine.grape_variety,
        order=competition.wines.aggregate(
            m=Coalesce(Max('order'), 0)
        )['m'] + 1,
    )

    return JsonResponse({
        'success': True,
        'wine': {
            'id': new_wine.id,
            'name': new_wine.name,
            'country': new_wine.country,
        }
    })


@require_POST
@login_required
def start_competition(request, competition_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )

    if competition.wines.count() < 2:
        messages.error(request, "Нужно минимум 2 вина для начала.")
        return redirect("competition_detail", competition_id=competition.id)

    # Atomic status transition: prevents race condition on double-click
    updated = Competition.objects.filter(
        id=competition.id, status="draft"
    ).update(status="running")
    if not updated:
        messages.error(request, "Соревнование уже запущено или завершено.")
        return redirect("competition_detail", competition_id=competition.id)
    competition.refresh_from_db()

    first_round = Round.objects.create(
        competition=competition,
        round_number=1,
        status="active",
    )

    create_pairings(first_round)

    messages.success(request, "Соревнование запущено!")
    return redirect("competition_detail", competition_id=competition.id)


def get_next_power_of_2(n):
    """Returns the smallest power of 2 greater than or equal to n."""
    if n == 0:
        return 1
    p = 1
    while p < n:
        p *= 2
    return p

def create_pairings(round_obj):
    competition = round_obj.competition

    if round_obj.round_number == 1:
        wines = list(competition.wines.all())
        random.shuffle(wines)
    else:
        previous_round = Round.objects.get(
            competition=competition, round_number=round_obj.round_number - 1
        )
        wines = [p.winner for p in previous_round.pairings.all() if p.winner]

    if not wines:
        logger.error(
            "create_pairings called with empty wines list for competition %d round %d — this is a bug",
            competition.id, round_obj.round_number,
        )
        return []

    num_wines = len(wines)
    pairings = []
    
    if round_obj.round_number == 1 and num_wines > 1:
        # In Round 1, calculate how many Byes we need to reach a power of 2
        p = get_next_power_of_2(num_wines)
        num_byes = p - num_wines
        num_playing = num_wines - num_byes
        
        # 'num_playing' wines will play in (num_playing / 2) pairings
        playing_wines = wines[:num_playing]
        bye_wines = wines[num_playing:]
        
        order_idx = 0
        
        # Create active pairings
        for i in range(0, len(playing_wines), 2):
            pairing = Pairing.objects.create(
                round=round_obj,
                wine1=playing_wines[i],
                wine2=playing_wines[i + 1],
                winner=None,
                order=order_idx,
                status="pending",
            )
            pairings.append(pairing)
            order_idx += 1
            
        # Create Bye pairings
        for wine in bye_wines:
            pairing = Pairing.objects.create(
                round=round_obj,
                wine1=wine,
                wine2=None,
                winner=wine,
                order=order_idx,
                status="completed",
            )
            pairings.append(pairing)
            order_idx += 1
            
    else:
        # Round 2 and onwards, or 1/0 wines total - normal sequential pairing
        for i in range(0, len(wines), 2):
            if i + 1 < len(wines):
                wine2 = wines[i + 1]
                status = "pending"
                winner = None
            else:
                # This should only happen if there's an odd number of wines
                # AFTER Round 1 (which shouldn't happen with the new logic, but handled for safety)
                wine2 = None
                status = "completed"
                winner = wines[i]

            pairing = Pairing.objects.create(
                round=round_obj,
                wine1=wines[i],
                wine2=wine2,
                winner=winner,
                order=i // 2,
                status=status,
            )
            pairings.append(pairing)

    return pairings


@require_POST
@login_required
def end_round(request, competition_id, round_id):
    competition = get_object_or_404(
        Competition, id=competition_id, organizer=request.user
    )
    round_obj = get_object_or_404(Round, id=round_id, competition=competition)

    if round_obj.status != "active":
        messages.error(request, "Раунд не активен.")
        return redirect("competition_detail", competition_id=competition.id)

    for pairing in round_obj.pairings.select_related('wine1', 'wine2').all():
        if pairing.status == "completed" and pairing.winner is not None:
            continue

        if pairing.wine2 is None:
            pairing.winner = pairing.wine1
            pairing.status = "completed"
            pairing.save()
            continue

        if pairing.votes_wine1 > pairing.votes_wine2:
            pairing.winner = pairing.wine1
        elif pairing.votes_wine2 > pairing.votes_wine1:
            pairing.winner = pairing.wine2
        else:
            winner = random.choice([pairing.wine1, pairing.wine2])
            logger.info(
                "Tie in pairing %d (competition %d, round %d) — winner chosen by random: %s",
                pairing.id, competition.id, round_obj.round_number, winner.name
            )
            pairing.winner = winner
        pairing.status = "completed"
        pairing.save()

    round_obj.status = "completed"
    round_obj.save()

    remaining_wines = [p.winner for p in round_obj.pairings.select_related('winner').all() if p.winner]

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


@require_POST
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
        request, f"Пара {pairing.wine1.name} vs {pairing.wine2.name if pairing.wine2 else 'Bye'} активирована!"
    )
    return redirect("competition_detail", competition_id=competition.id)


@require_POST
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
        logger.info(
            "Tie in end_pairing %d (competition %d) — winner chosen by random: %s",
            pairing.id, competition.id, pairing.winner.name
        )

    pairing.status = "completed"
    pairing.save()

    # Check if all pairings in this round are completed
    round_obj = pairing.round
    if not round_obj.pairings.exclude(status="completed").exists():
        messages.success(request, f"Пара завершена! Победитель: {pairing.winner.name}. Все пары завершены, можете подвести итоги раунда.")
    else:
        messages.success(request, f"Пара завершена! Победитель: {pairing.winner.name}")
        
    return redirect("competition_detail", competition_id=competition.id)


@ensure_csrf_cookie
def competition_view(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)
    current_round = competition.current_round

    cookie_id = generate_cookie_id(request)
    response = render(
        request,
        "voting.html",
        {
            "competition": competition,
            "current_round": current_round,
            "cookie_id": cookie_id,
        },
    )
    response.set_cookie(
        "wine_competition_id", cookie_id,
        max_age=60 * 60 * 24 * 365,
        samesite='Lax',
    )
    return response


@require_POST
@transaction.atomic
def vote(request, pairing_id):
    pairing = get_object_or_404(Pairing, id=pairing_id)
    wine_id = request.POST.get("wine_id")
    participant_name = request.POST.get("participant_name", "").strip()

    cookie_id = request.COOKIES.get("wine_competition_id")
    if not cookie_id:
        return JsonResponse({"error": "Cookie not found"}, status=400)

    # Validate UUID format to prevent fake cookie_id injection
    if not _COOKIE_UUID_RE.match(cookie_id):
        return JsonResponse({"error": "Invalid voter identifier"}, status=400)

    if pairing.status != "active":
        return JsonResponse({"error": "Голосование для этой пары не активно"}, status=400)

    if pairing.wine2 is None:
        return JsonResponse({"error": "Нельзя голосовать за пару без соперника"}, status=400)

    valid_ids = [pairing.wine1.id]
    if pairing.wine2:
        valid_ids.append(pairing.wine2.id)

    wine = get_object_or_404(
        Wine, id=wine_id, id__in=valid_ids
    )

    existing_vote = Vote.objects.filter(pairing=pairing, cookie_id=cookie_id).first()

    if existing_vote:
        if existing_vote.wine_id == wine.id:
            # Тот же голос — просто возвращаем текущее состояние
            return JsonResponse({
                "success": True,
                "voted_wine_id": wine.id,
                "votes_wine1": pairing.votes_wine1,
                "votes_wine2": pairing.votes_wine2,
                "changed": False,
            })
        # Меняем голос: убираем старый счёт атомарно через F()
        if existing_vote.wine_id == pairing.wine1_id:
            Pairing.objects.filter(pk=pairing.pk, votes_wine1__gt=0).update(
                votes_wine1=F('votes_wine1') - 1
            )
        else:
            Pairing.objects.filter(pk=pairing.pk, votes_wine2__gt=0).update(
                votes_wine2=F('votes_wine2') - 1
            )
        existing_vote.wine = wine
        if participant_name:
            existing_vote.participant_name = participant_name
        existing_vote.save()
    else:
        Vote.objects.create(
            pairing=pairing,
            wine=wine,
            cookie_id=cookie_id,
            participant_name=participant_name,
        )

    if wine == pairing.wine1:
        Pairing.objects.filter(pk=pairing.pk).update(votes_wine1=F('votes_wine1') + 1)
    else:
        Pairing.objects.filter(pk=pairing.pk).update(votes_wine2=F('votes_wine2') + 1)
    pairing.refresh_from_db()

    return JsonResponse({
        "success": True,
        "voted_wine_id": wine.id,
        "votes_wine1": pairing.votes_wine1,
        "votes_wine2": pairing.votes_wine2,
        "changed": existing_vote is not None,
    })


def statistics(request, competition_id):
    competition = get_object_or_404(Competition, id=competition_id)

    # Use annotate instead of N+1 queries; filter votes to this competition only
    wines_with_votes = competition.wines.annotate(
        vote_count=Count(
            'vote',
            filter=Q(vote__pairing__round__competition=competition)
        )
    ).order_by('-vote_count')

    wine_stats = [{"wine": w, "votes": w.vote_count} for w in wines_with_votes]

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
    rounds = competition.rounds.prefetch_related(
        Prefetch(
            'pairings',
            queryset=Pairing.objects.select_related('wine1', 'wine2', 'winner').order_by('order'),
        )
    ).all().order_by("round_number")

    return render(
        request,
        "tournament.html",
        {
            "competition": competition,
            "rounds": rounds,
        },
    )


@require_POST
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
