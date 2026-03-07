# Документация по деплою Wine Competition на VPS

## Требования

- VPS с Ubuntu 20.04+
- Docker и Docker Compose
- Домен (опционально)

## Быстрый старт с Docker

### 1. Клонирование репозитория

```bash
git clone <repository-url> wine-competition
cd wine-competition
```

### 2. Создание Docker Compose файла

Создайте файл `docker-compose.yml`:

```yaml
version: '3.8'

services:
  web:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DEBUG=0
      - ALLOWED_HOSTS=your-domain.com
      - SECRET_KEY=your-secret-key-here
    volumes:
      - ./media:/app/media
    restart: unless-stopped
```

### 3. Запуск контейнеров

```bash
docker-compose up -d --build
```

### 4. Создание суперпользователя

```bash
docker-compose exec web python manage.py createsuperuser
```

### 5. Создание демо-данных

```bash
docker-compose exec web python manage.py create_demo
```

## Настройка с nginx

### 1. Установка nginx

```bash
sudo apt update
sudo apt install nginx
```

### 2. Настройка nginx

Создайте файл `/etc/nginx/sites-available/wine-competition`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static/ {
        alias /app/static/;
    }

    location /media/ {
        alias /app/media/;
    }
}
```

### 3. Активация сайта

```bash
sudo ln -s /etc/nginx/sites-available/wine-competition /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Настройка PostgreSQL (Production)

### 1. Установка PostgreSQL

```bash
sudo apt install postgresql postgresql-contrib
```

### 2. Создание базы данных

```bash
sudo -u postgres psql
CREATE DATABASE wine_competition;
CREATE USER wineuser WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE wine_competition TO wineuser;
\q
```

### 3. Обновление settings.py

Измените `DATABASES` в `wine_project/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'wine_competition',
        'USER': 'wineuser',
        'PASSWORD': 'your-password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### 4. Обновление requirements.txt

Добавьте:
```
psycopg2-binary>=2.9
```

### 5. Пересоздание контейнеров

```bash
docker-compose down
docker-compose up -d --build
```

## Настройка HTTPS с Let's Encrypt

### 1. Установка Certbot

```bash
sudo apt install certbot python3-certbot-nginx
```

### 2. Получение SSL-сертификата

```bash
sudo certbot --nginx -d your-domain.com
```

### 3. Автоматическое обновление

```bash
sudo certbot renew --dry-run
```

## Мониторинг и логи

### Просмотр логов

```bash
docker-compose logs -f web
```

### Проверка статуса

```bash
docker-compose ps
```

## Резервное копирование

### База данных

```bash
docker-compose exec -T db pg_dump -U wineuser wine_competition > backup.sql
```

### Медиа-файлы

```bash
tar -czf media-backup.tar.gz ./media/
```

## Обновление приложения

```bash
git pull
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput
```

## Первоначальная настройка после деплоя

1. Создайте суперпользователя
2. Зайдите в админ-панель `/admin`
3. Создайте соревнование
4. Добавьте вина
5. Запустите соревнование
6. Поделитесь ссылкой на голосование
