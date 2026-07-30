from django.urls import path, include

urlpatterns = [
    path("", include("chatapp.urls")),
]
