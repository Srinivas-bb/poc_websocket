"""
ASGI config for poc_backend project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.1/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from .urls import websocket_patterns

os.environ['DJANGO_SETTINGS_MODULE'] = 'poc_backend.settings'


django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': URLRouter(websocket_patterns)
})
