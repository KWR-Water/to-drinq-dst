# The `urlpatterns` list routes URLs to views. For more information please see:
# https://docs.djangoproject.com/en/5.0/topics/http/urls/
# Examples:
# Function views
#     1. Add an import:  from my_app import views
#     2. Add a URL to urlpatterns:  path('', views.home, name='home')
# Class-based views
#     1. Add an import:  from other_app.views import Home
#     2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
# Including another URLconf
#     1. Import the include() function: from django.urls import include, path
#     2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
import debug_toolbar
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib import admin
import django.contrib.auth.views as auth_views
from drinq import views


urlpatterns = [
    path("", views.index, name='drinq'),
    path('db_stats/', views.db_stats, name='db_stats'),
    path('form/', views.dst_form, name='drinq_form'),
    path('form_result/', RedirectView.as_view(), name='drinq_result'),
    path('form_redirect/', RedirectView.as_view(), name='drinq_redirect'),
    # path('dst_redirect/', views.dst_redirect, name='dst_redirect'),
    path('compound/<cid>/', views.compound_detail, name='drinq'),
    path('admin/', admin.site.urls),
    path('', views.Welcome.as_view(), name='index'),
    path('', views.Register.as_view(), name='register'),
    path('register/', views.Register.as_view(), name='register'),
    path('login/', RedirectView.as_view(
        pattern_name='rest_framework:login', permanent=False), name='login'),
    path('logout/', RedirectView.as_view(
        pattern_name='rest_framework:logout', permanent=False), name='logout'),
    path(
        'change-password/',
        auth_views.PasswordChangeView.as_view(),
        name='change-password'),
    path(
        'change-password/done',
        views.PasswordChangeOk.as_view(),
        name='change-password-done'),
    path(
        'api-auth/',
        include('rest_framework.urls', namespace='rest_framework'),
    ),
    path('__debug__/', include(debug_toolbar.urls)),
    # path('compound/<int:cid>/', views.compound_detail, name='drinq'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
