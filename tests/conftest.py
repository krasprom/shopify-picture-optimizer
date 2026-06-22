"""Тестовое окружение: задаём кэш-папку до импорта app, чтобы mkdir не лез в /var/cache."""

import os
import tempfile

# Должно выполниться ДО первого `import app` в тестовых модулях.
os.environ.setdefault(
    "OPTIMIZER_CACHE_DIR",
    os.path.join(tempfile.gettempdir(), "shopify-optimizer-tests"),
)
