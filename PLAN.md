# План реализации Wine Competition

## Технический стек
- **Backend:** Django 5.x (Python)
- **Frontend:** Bootstrap 5 + custom CSS
- **Database:** SQLite (dev) / PostgreSQL (prod)
- **Virtual Environment:** venv
- **Deployment:** Docker + Gunicorn + nginx

## Структура проекта
```
wine-competition/
├── docs/                  # Документация
│   └── DEPLOY.md         # Инструкция деплоя
├── wine_app/             # Django приложение
│   ├── migrations/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   └── admin.py
├── templates/            # HTML шаблоны
│   ├── base.html
│   ├── home.html
│   ├── competition_list.html
│   ├── competition_detail.html
│   ├── competition_create.html
│   ├── wine_form.html
│   ├── voting.html
│   ├── tournament.html
│   └── statistics.html
├── static/               # CSS, JS
│   └── css/
│       └── style.css
├── wine_project/        # Django проект
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── venv/                # Виртуальное окружение
├── manage.py
├── requirements.txt
└── Dockerfile
```

## Модели данных

### Competition
- title (CharField) - название
- date (DateField) - дата
- organizer (ForeignKey -> User) - организатор
- status (CharField) - draft/running/finished
- created_at (DateTimeField)

### Wine
- competition (ForeignKey -> Competition)
- name (CharField) - название вина
- country (CharField) - страна происхождения
- image (ImageField) - картинка (опционально)
- order (IntegerField) - порядковый номер

### Round
- competition (ForeignKey -> Competition)
- round_number (IntegerField) - номер раунда
- status (CharField) - pending/active/completed
- pairing_order (JSON) - порядок пар

### Pairing
- round (ForeignKey -> Round)
- wine1 (ForeignKey -> Wine)
- wine2 (ForeignKey -> Wine)
- winner (ForeignKey -> Wine, nullable)
- votes_wine1 (IntegerField)
- votes_wine2 (IntegerField)

### Vote
- pairing (ForeignKey -> Pairing)
- wine (ForeignKey -> Wine)
- cookie_id (CharField) - идентификатор cookie
- created_at (DateTimeField)

## Реализация (этапы)

### Этап 1: Настройка проекта
1. Создать виртуальное окружение
2. Установить Django и зависимости
3. Создать Django проект
4. Настроить settings.py
5. Создать Django приложение

### Этап 2: Модели и админка
1. Определить модели в models.py
2. Создать миграции
3. Настроить admin.py
4. Создать суперпользователя

### Этап 3: Представления и формы
1. Создать формы (CompetitionForm, WineForm)
2. Реализовать представления (views.py)
3. Настроить URL (urls.py)

### Этап 4: Шаблоны
1. Создать базовый шаблон (base.html)
2. Создать все страницы
3. Добавить статические файлы

### Этап 5: Логика голосования
1. Жеребьёвка - случайное формирование пар
2. Голосование с использованием cookies
3. Подсчёт голосов
4. Переход к следующему раунду

### Этап 6: Демо-данные
1. Создать соревнование с 8 винами
2. Заполнить тестовыми данными

### Этап 7: Документация деплоя
1. Создать Dockerfile
2. Написать DEPLOY.md

## Демо-данные (8 вин)
1. Château Margaux 2015 - Франция
2. Opus One 2018 - США
3. Penfolds Grange 2017 - Австралия
4. Sassicaia 2016 - Италия
5. Vega Sicilia Único 2011 - Испания
6. Château d'Yquem 2014 - Франция
7. Sassicaia 2019 - Италия
8. Penfolds Grange 2019 - Австралия
