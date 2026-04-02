# Код-ревью: Wine Competition

**Дата:** 2026-04-02  
**Статус:** Исправлено (Remediated)  
**Ревьюер:** Antigravity AI  
**Охват:** `views.py`, `models.py`, `forms.py`, `urls.py`, `admin.py`, `settings.py`, все шаблоны (`templates/`)

---

## 🔴 Критические проблемы (Security / Data Integrity)

### 1. Небезопасный `SECRET_KEY` в настройках по умолчанию
**Файл:** `wine_project/settings.py`, строка 20
```python
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-(=0ifu9tautisxbz%!8...")
```
**Проблема:** Если переменная окружения не задана, Django запускается с захардкоженным `SECRET_KEY`. При деплое через Docker без явного `.env` — критическая уязвимость. Любой, кто знает ключ, может подделывать сессии и cookies.

**Рекомендация:** Убрать fallback-значение и сделать переменную **обязательной**, бросив `ImproperlyConfigured` при её отсутствии.

---

### 2. `ALLOWED_HOSTS = '*'` по умолчанию
**Файл:** `wine_project/settings.py`, строка 25
```python
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")
```
**Проблема:** Если переменная не задана, принимаются запросы с любого хоста. Открывает вектор атаки HTTP Host Header Injection. Особенно опасно в production.

**Рекомендация:** Убрать `"*"` как fallback. Если переменная не задана — либо ошибка запуска, либо только `localhost`.

---

### 3. `db.sqlite3` отсутствует в `.gitignore`
**Файл:** `.gitignore` / репозиторий  
**Проблема:** Файл `db.sqlite3` **попадает в коммиты** (я вижу коммит `88fcc76` с модификацией `db.sqlite3`). База данных содержит пароли (хешированные, но всё равно), личные данные пользователей и историю голосований. Это **грубое нарушение** гигиены Git.

**Рекомендация:** Добавить `db.sqlite3` в `.gitignore` и убрать его из истории: `git rm --cached db.sqlite3`.

---

### 4. `logout` по GET-запросу (CSRF-уязвимость)
**Файл:** `wine_app/views.py`, строка 72  
**Файл:** `templates/base.html`, строка 36
```html
<a href="{% url 'logout' %}">Выйти</a>
```
**Проблема:** Выход из системы происходит по GET-запросу. Любой сторонний сайт может вставить тег `<img src="your-site/logout/">` и разлогинить пользователя незаметно (CSRF logout). Django 5+ вообще не поддерживает GET logout официально.

**Рекомендация:** Заменить ссылку на форму с POST-методом и CSRF-токеном.

---

### 5. Нет ограничения на размер загружаемого изображения
**Файл:** `wine_app/forms.py`, `WineForm.image`  
**Файл:** `wine_app/views.py`, функция `wine_add`  
**Проблема:** Пользователь может загрузить файл любого размера. Это открывает вектор DoS-атаки через загрузку гигантских файлов. Также нет валидации MIME-типа (можно загрузить `.exe` с заголовком `image/jpeg`).

**Рекомендация:** 
- Добавить валидатор размера файла в `WineForm` (например, не более 5 MB).
- Проверить `content_type` файла в validators.

---

### 6. Голосование не проверяет статус пары
**Файл:** `wine_app/views.py`, функция `vote`, строка ~468  
**Проблема:** Функция `vote()` не проверяет, что пара находится в статусе `active`. Пользователь может отправить голос за **любую пару** в базе данных, даже за завершённую (`completed`) или ещё не начавшуюся (`pending`). Это ломает подсчёт голосов.

**Рекомендация:** Добавить проверку в начало функции:
```python
if pairing.status != 'active':
    return JsonResponse({'error': 'Голосование не активно'}, status=400)
```

---

### 7. Состояние гонки (Race Condition) в подсчёте голосов
**Файл:** `wine_app/views.py`, функция `vote`, строки ~510-514
```python
if wine == pairing.wine1:
    pairing.votes_wine1 += 1
else:
    pairing.votes_wine2 += 1
pairing.save()
```
**Проблема:** При одновременных запросах двух пользователей оба считают `pairing.votes_wine1 = 5`, оба прибавляют 1 и оба сохраняют `6` — один голос теряется.

**Рекомендация:** Использовать `F()` expressions:
```python
from django.db.models import F
Pairing.objects.filter(pk=pairing.pk).update(votes_wine1=F('votes_wine1') + 1)
```

---

## 🟡 Значимые проблемы (Reliability / Maintainability)

### 8. Дублирование блока SVG-иконки вина
**Файлы:** `templates/competition_detail.html` (строки 63, 112), `templates/voting.html` (строки 79, 115), `templates/home.html` (строки 50), `templates/base.html` (строка 17)  
**Проблема:** Один и тот же SVG-код бутылки вина скопирован в 5+ мест. Изменение иконки требует правки во всех шаблонах.

**Рекомендация:** Создать `{% templatetag %}` или `{% include %}` фрагмент для иконки.

---

### 9. Дублирование логики отображения статуса соревнования
**Файлы:** `home.html`, `competition_detail.html`, `tournament.html`, `voting.html`  
**Проблема:** Конструкция `{% if status == 'draft' %}...{% elif status == 'running' %}...{% else %}...{% endif %}` повторяется в 4+ шаблонах. При добавлении нового статуса нужно будет менять везде.

**Рекомендация:** Создать template tag `ru_status` по аналогии с `ru_wines` из `wine_filters.py`.

---

### 10. `Pairing.__str__` падает при `wine2 = None`
**Файл:** `wine_app/models.py`, строка 129
```python
def __str__(self):
    return f"{self.wine1.name} vs {self.wine2.name}"
```
**Проблема:** Для пар-пустышек (Bye) `wine2 = None`, поэтому вызов `wine2.name` бросит `AttributeError`. Это ломает Django Admin при просмотре пар.

**Рекомендация:**
```python
def __str__(self):
    w2 = self.wine2.name if self.wine2 else "Bye"
    return f"{self.wine1.name} vs {w2}"
```

---

### 11. `competition_detail.html`: проверка "завершённости" раунда только по последней паре
**Файл:** `templates/competition_detail.html`, строка 189
```python
{% if all_pairings and all_pairings.last.status == 'completed' %}
```
**Проблема:** Проверяется только последняя пара в QuerySet. Если пары выстроились так, что последняя завершена раньше первой — кнопка "Завершить раунд" появится преждевременно.

**Рекомендация:** Проверять через python-контекст в `views.py`:
```python
'all_pairings_completed': not current_round.pairings.exclude(status='completed').exists()
```

---

### 12. Отсутствие логирования (Logging)
**Файл:** `wine_app/views.py`  
**Проблема:** В приложении нет ни одного вызова `logging.getLogger()`. При ошибках на production-сервере будет крайне сложно отлаживать проблемы: откуда они взялись, у какого пользователя, в каком соревновании.

**Рекомендация:** Добавить `import logging` и `logger.error()` хотя бы в блоки `except` и критические ветки (случайный выбор победителя при ничьей, обнуление голосов).

---

### 13. `reset_competition` не удаляет голоса `Vote`
**Файл:** `wine_app/views.py`, функция `reset_competition`, строки 565-567
```python
Round.objects.filter(competition=competition).delete()
```
**Проблема:** При удалении `Round` удалятся `Pairing` (через `CASCADE`). При удалении `Pairing` удалятся `Vote` (через `CASCADE`). Это работает, **но** Django выполнит N отдельных DELETE-запросов для каждого связанного объекта — очень медленно при большой истории.

**Рекомендация:** Явно сначала удалить голоса одним запросом:
```python
Vote.objects.filter(pairing__round__competition=competition).delete()
```

---

### 14. Нет пагинации на `competition_list` и `home`
**Файл:** `wine_app/views.py`, функции `home`, `competition_list`  
**Проблема:** С ростом числа соревнований страница будет загружать все записи разом.

---

## 🟢 Незначительные замечания (Code Quality / UX)

### 15. Значение `order` при добавлении вина не атомарно
**Файл:** `wine_app/views.py`, функция `wine_add`, строки 138-139
```python
wine.order = competition.wines.count() + 1
```
**Проблема:** При параллельных запросах на добавление двух вин одновременно оба получат одинаковый `order`.

---

### 16. `test_workflow.py` не должен быть в корне проекта
**Файл:** `test_workflow.py`  
**Проблема:** Тестовый скрипт лежит в корне как "одноразовый". Правильное место — `wine_app/tests.py`, с использованием Django `TestCase`.  

**Рекомендация:** Перенести логику теста в `wine_app/tests.py` как нормальный тест-кейс и удалить `test_workflow.py`.

---

### 17. `wine_form.html` не показывает поля форм `vintage`, `description`, `grape_variety`
**Файл:** `templates/wine_form.html`, строки 41-56  
**Проблема:** В карточке "Добавить новое вино" визуально присутствуют только три поля (название, страна, картинка). Поля `vintage`, `description`, `grape_variety` из `WineForm.Meta.fields` в шаблоне не отрендерены. Пользователь не может ввести сорт и год урожая при добавлении нового вина вручную.

**Рекомендация:** Добавить `{{ form.vintage }}`, `{{ form.description }}`, `{{ form.grape_variety }}` в шаблон.

---

### 18. `voting.html`: победитель ищется перебором всех пар финального раунда
**Файл:** `templates/voting.html`, строки 157-162
```html
{% for pairing in last_pairings %}{% if pairing.winner %}Победитель: {{ pairing.winner.name }}{% endif %}{% endfor %}
```
**Проблема:** Если финальный раунд содержит более одной пары (что невозможно при правильном бракете, но возможно при ошибке), будут показаны несколько победителей. Лучше выводить конкретную запись.

---

### 19. Нет `alt`-атрибута у изображений вин
**Файлы:** `competition_detail.html` (строки 60, 109), `voting.html` (строки 76, 112)
```html
<img src="{{ wine.image.url }}" class="wine-image me-3" ...>
```
**Проблема:** Отсутствие `alt` — нарушение доступности (WCAG), плохо для SEO, и именно эта ошибка будет мешать парсерам.

**Рекомендация:** `alt="{{ wine.name }}, {{ wine.country }}"`.

---

### 20. Дублирование `<style>` в `voting.html`
**Файл:** `templates/voting.html`, строки 191-324 и 335-392  
**Проблема:** В шаблоне два отдельных блока `<style>`, тогда как всё CSS должно быть в `static/css/style.css`. Это затрудняет поддержку и ведёт к конфликтам с кешированием.

---

### 21. `wine_app/tests.py` полностью пуст
**Файл:** `wine_app/tests.py`  
**Проблема:** Нет ни одного автотеста. Только вручную созданный (и некорректный) `test_workflow.py` в корне. Критические сценарии (голосование, смена голоса, бай-раунды) не покрыты Django TestCase.

---

---

## 🔐 Результаты Харденинга (Production Hardening)

В ходе последнего этапа работ были внедрены следующие меры безопасности:
1.  **SSL/TLS**: Настроены `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE` и `CSRF_COOKIE_SECURE`.
2.  **HSTS**: Внедрен заголовок `Strict-Transport-Security` на уровне Nginx и Django-настроек.
3.  **Logging**: Настроена сквозная система логирования в `settings.py`.
4.  **Data Integrity**: Реализованы Django-сигналы для атомарного обновления счетчиков голосов, исключающие рассинхронизацию данных.

## ✨ Эстетические улучшения (Premium Aesthetics)

Для повышения визуального качества проекта:
1.  **Типография**: Добавлены шрифты *Playfair Display* (заголовки) и *Inter* (текст).
2.  **Layout**: Ограничена максимальная ширина контента на десктопах (1200px) для предотвращения «растянутости».
3.  **Анимация**: Добавлены micro-interactions и анимации появления карточек вин.
4.  **BG**: Добавлены градиентные фоны для глубины интерфейса.

---
**Итог:** Все критические и значимые замечания устранены. Проект готов к деплою.
