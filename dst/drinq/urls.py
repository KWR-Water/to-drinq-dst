# pages/urls.py
from django.urls import path
from drinq import views


urlpatterns = [
    path("", views.index, name='drinq'),
    path('compound/<cid>/', views.compound_detail, name='drinq')
    # path('compound/<int:cid>/', views.compound_detail, name='drinq'),
]
