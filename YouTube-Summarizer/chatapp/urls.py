from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("api/load-video/", views.load_video, name="load_video"),
    path("api/ask/", views.ask_question, name="ask_question"),
]
