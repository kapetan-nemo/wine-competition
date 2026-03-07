from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from wine_app.models import Competition, Wine, Round, Pairing
import random


class Command(BaseCommand):
    help = "Creates demo competition with 8 wines"

    def handle(self, *args, **options):
        user, created = User.objects.get_or_create(
            username="demo", defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            user.set_password("demo123")
            user.save()
            self.stdout.write(
                self.style.SUCCESS(f"Created demo user (password: demo123)")
            )

        competition, created = Competition.objects.get_or_create(
            title="Demo Wine Tasting",
            defaults={"organizer": user, "date": "2024-12-01", "status": "running"},
        )

        if created:
            wines_data = [
                (
                    "Château Margaux 2015",
                    "Франция",
                    "Каберне Совиньон, Мерло",
                    "Легендарное красное вино из Бордо с элегантными нотами чёрной смородины, фиалки и графита",
                ),
                (
                    "Opus One 2018",
                    "США",
                    "Каберне Совиньон, Мерло",
                    "Престижное калифорнийское вино с богатым вкусом чёрных ягод, ванили и шоколада",
                ),
                (
                    "Penfolds Grange 2017",
                    "Австралия",
                    "Шираз",
                    "Австралийская икона с нотами чёрного перца, сливы и пряностей",
                ),
                (
                    "Sassicaia 2016",
                    "Италия",
                    "Каберне Совиньон, Каберне Фран",
                    "Тосканийский шедевр с элегантными танинами и нотами красных ягод",
                ),
                (
                    "Vega Sicilia Único 2011",
                    "Испания",
                    "Темпранильо",
                    "Испанский король вин с выдержкой более 10 лет, с нотами табака, кожи и вишни",
                ),
                (
                    "Château d'Yquem 2014",
                    "Франция",
                    "Семийон, Совиньон Блан",
                    "Лучшее десертное вино мира с медовыми нотами, абрикоса и специй",
                ),
                (
                    "Tignanello 2018",
                    "Италия",
                    "Санджовезе, Каберне Совиньон",
                    "Первый Super Tuscan с нотами вишни, пряностей и кожи",
                ),
                (
                    "Penfolds Grange 2019",
                    "Австралия",
                    "Шираз",
                    "Мощный австралийский шираз с нотами чёрной смородины и шоколада",
                ),
            ]

            for i, (name, country, grape, desc) in enumerate(wines_data, 1):
                Wine.objects.create(
                    competition=competition,
                    name=name,
                    country=country,
                    order=i,
                    vintage=name[-4:],
                    grape_variety=grape,
                    description=desc,
                )

            first_round = Round.objects.create(
                competition=competition, round_number=1, status="active"
            )

            wines = list(competition.wines.all())
            random.shuffle(wines)

            for i in range(0, len(wines) - 1, 2):
                Pairing.objects.create(
                    round=first_round,
                    wine1=wines[i],
                    wine2=wines[i + 1],
                    order=i // 2,
                    status="active" if i == 0 else "pending",
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Created demo competition with {len(wines_data)} wines"
                )
            )
        else:
            self.stdout.write(self.style.WARNING("Demo competition already exists"))
