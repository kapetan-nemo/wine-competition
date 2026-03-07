from django import forms
from .models import Competition, Wine


class CompetitionForm(forms.ModelForm):
    class Meta:
        model = Competition
        fields = ["title", "date"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Название соревнования"}
            ),
            "date": forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        }


class WineForm(forms.ModelForm):
    class Meta:
        model = Wine
        fields = ["name", "country", "image", "description", "vintage", "grape_variety"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Название вина"}
            ),
            "country": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Страна происхождения"}
            ),
            "image": forms.FileInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Описание вина",
                }
            ),
            "vintage": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Год урожая"}
            ),
            "grape_variety": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Сорт винограда"}
            ),
        }
