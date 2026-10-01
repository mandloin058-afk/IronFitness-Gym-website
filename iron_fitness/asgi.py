import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "iron_fitness.settings")
application = get_asgi_application()
