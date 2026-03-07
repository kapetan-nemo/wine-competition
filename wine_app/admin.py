from django.contrib import admin
from .models import Competition, Wine, Round, Pairing, Vote


@admin.register(Competition)
class CompetitionAdmin(admin.ModelAdmin):
    list_display = ["title", "date", "organizer", "status", "created_at"]
    list_filter = ["status", "date"]
    search_fields = ["title"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Wine)
class WineAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "competition", "order"]
    list_filter = ["competition"]
    search_fields = ["name", "country"]


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ["competition", "round_number", "status", "created_at"]
    list_filter = ["status", "competition"]
    readonly_fields = ["created_at"]


@admin.register(Pairing)
class PairingAdmin(admin.ModelAdmin):
    list_display = ["round", "wine1", "wine2", "winner", "votes_wine1", "votes_wine2"]
    list_filter = ["round__competition"]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["pairing", "wine", "cookie_id", "created_at"]
    list_filter = ["pairing__round__competition"]
    readonly_fields = ["created_at"]
