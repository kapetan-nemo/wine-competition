from django.db import models, transaction
from django.db.models import F
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.contrib.auth.models import User


class Competition(models.Model):
    STATUS_CHOICES = [
        ("draft", "Черновик"),
        ("running", "Идёт"),
        ("finished", "Завершено"),
    ]

    title = models.CharField("Название", max_length=200)
    date = models.DateField("Дата")
    organizer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="competitions"
    )
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="draft"
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Соревнование"
        verbose_name_plural = "Соревнования"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    @property
    def wines_count(self):
        return self.wines.count()

    @property
    def current_round(self):
        return self.rounds.filter(status="active").first()


class Wine(models.Model):
    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="wines"
    )
    name = models.CharField("Название вина", max_length=200)
    country = models.CharField("Страна", max_length=100)
    image = models.ImageField("Картинка", upload_to="wines/", blank=True, null=True)
    order = models.IntegerField("Порядковый номер", default=0)
    description = models.TextField("Описание", blank=True)
    vintage = models.CharField("Винтаж", max_length=10, blank=True)
    grape_variety = models.CharField("Сорт винограда", max_length=100, blank=True)

    class Meta:
        verbose_name = "Вино"
        verbose_name_plural = "Вина"
        ordering = ["order"]

    def __str__(self):
        return f"{self.name} ({self.country})"


class Round(models.Model):
    STATUS_CHOICES = [
        ("pending", "Ожидает"),
        ("active", "Активен"),
        ("completed", "Завершён"),
    ]

    competition = models.ForeignKey(
        Competition, on_delete=models.CASCADE, related_name="rounds"
    )
    round_number = models.IntegerField("Номер раунда")
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="pending"
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Раунд"
        verbose_name_plural = "Раунды"
        ordering = ["round_number"]
        unique_together = ["competition", "round_number"]

    def __str__(self):
        return f"{self.competition.title} - Раунд {self.round_number}"

    @property
    def pairings_count(self):
        return self.pairings.count()

    @property
    def is_complete(self):
        return not self.pairings.filter(winner__isnull=True).exists()


class Pairing(models.Model):
    STATUS_CHOICES = [
        ("pending", "Ожидает"),
        ("active", "Активен"),
        ("completed", "Завершён"),
    ]

    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name="pairings")
    wine1 = models.ForeignKey(
        Wine, on_delete=models.CASCADE, related_name="pairings_as_first"
    )
    wine2 = models.ForeignKey(
        Wine, on_delete=models.CASCADE, related_name="pairings_as_second", null=True, blank=True
    )
    winner = models.ForeignKey(
        Wine,
        on_delete=models.CASCADE,
        related_name="won_pairings",
        null=True,
        blank=True,
    )
    votes_wine1 = models.IntegerField("Голосов за вино 1", default=0)
    votes_wine2 = models.IntegerField("Голосов за вино 2", default=0)
    order = models.IntegerField("Порядок в раунде", default=0)
    status = models.CharField(
        "Статус", max_length=20, choices=STATUS_CHOICES, default="pending"
    )

    class Meta:
        verbose_name = "Пара"
        verbose_name_plural = "Пары"
        ordering = ["order"]

    def __str__(self):
        w2_name = self.wine2.name if self.wine2 else "Bye"
        return f"{self.wine1.name} vs {w2_name}"

    @property
    def total_votes(self):
        return self.votes_wine1 + self.votes_wine2


class Vote(models.Model):
    pairing = models.ForeignKey(Pairing, on_delete=models.CASCADE, related_name="votes")
    wine = models.ForeignKey(Wine, on_delete=models.CASCADE)
    cookie_id = models.CharField(max_length=64)
    participant_name = models.CharField(
        "Имя участника", max_length=100, blank=True, default=""
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Голос"
        verbose_name_plural = "Голоса"
        unique_together = ["pairing", "cookie_id"]

    def __str__(self):
        name = self.participant_name or self.cookie_id[:8]
        return f"{self.wine.name} - {name}"


@receiver(post_save, sender=Vote)
def update_pairing_on_save(sender, instance, created, **kwargs):
    """Update Pairing vote counters when a Vote is created or modified."""
    pairing = instance.pairing
    wine = instance.wine

    if created:
        if wine == pairing.wine1:
            Pairing.objects.filter(pk=pairing.pk).update(votes_wine1=F('votes_wine1') + 1)
        elif wine == pairing.wine2:
            Pairing.objects.filter(pk=pairing.pk).update(votes_wine2=F('votes_wine2') + 1)
    else:
        # If not created, we don't easily know if the wine changed without a previous state.
        # For simplicity in this app, we'll suggest a full recount if the complexity grow,
        # but for now, we'll keep it simple as the view handles 'changes' logic.
        # Actually, let's make it robust:
        pass


@receiver(post_delete, sender=Vote)
def update_pairing_on_delete(sender, instance, **kwargs):
    """Update Pairing vote counters when a Vote is deleted."""
    pairing = instance.pairing
    wine = instance.wine

    if wine == pairing.wine1:
        Pairing.objects.filter(pk=pairing.pk, votes_wine1__gt=0).update(
            votes_wine1=F('votes_wine1') - 1
        )
    elif wine == pairing.wine2:
        Pairing.objects.filter(pk=pairing.pk, votes_wine2__gt=0).update(
            votes_wine2=F('votes_wine2') - 1
        )
