from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Competition, Wine
import io


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

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image:
            if image.size > 5 * 1024 * 1024:
                raise ValidationError("Размер файла не должен превышать 5 MB.")
            # Verify actual image content using Pillow (checks magic bytes, not HTTP header)
            try:
                from PIL import Image
                content = image.read()
                image.seek(0)
                img = Image.open(io.BytesIO(content))
                img.verify()  # Raises if not a valid image
            except Exception:
                raise ValidationError("Загруженный файл должен быть изображением.")
        return image


class CustomUserCreationForm(UserCreationForm):
    """Форма регистрации с русскими лейблами и Bootstrap CSS-классами."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        label_map = {
            'username': 'Имя пользователя',
            'password1': 'Пароль',
            'password2': 'Подтверждение пароля',
        }
        for field_name, label in label_map.items():
            if field_name in self.fields:
                self.fields[field_name].label = label


class CustomAuthenticationForm(AuthenticationForm):
    """Форма входа с русскими лейблами и Bootstrap CSS-классами."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'
        label_map = {
            'username': 'Имя пользователя',
            'password': 'Пароль',
        }
        for field_name, label in label_map.items():
            if field_name in self.fields:
                self.fields[field_name].label = label
