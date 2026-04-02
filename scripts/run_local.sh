#!/usr/bin/env bash

set -euo pipefail

# Определяем корень проекта (директория на уровень выше scripts)
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

# Имя виртуального окружения по умолчанию
VENV_DIR="${VENV_DIR:-.venv_run}"

echo "Проект: $PROJECT_DIR"
echo "Виртуальное окружение: $VENV_DIR"

if [ ! -d "$VENV_DIR" ]; then
  echo "Виртуальное окружение не найдено, создаю..."
  python3 -m venv "$VENV_DIR"
fi

echo "Активирую виртуальное окружение..."
source "$VENV_DIR/bin/activate"

echo "Обновляю pip и устанавливаю зависимости..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Применяю миграции..."
python manage.py migrate

echo "Пробую создать суперпользователя admin..."
if python manage.py createsuperuser --noinput --username admin --email admin@example.com 2>/dev/null; then
  echo "Суперпользователь admin создан."
else
  echo "Суперпользователь admin уже существует или не может быть создан без ввода пароля – пропускаю."
fi

echo "Создаю демо-данные (если их ещё нет)..."
python manage.py create_demo || true

echo "Запускаю сервер разработки на http://127.0.0.1:8000/ ..."
python manage.py runserver 0.0.0.0:8000

