from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from users.models import CustomUser


class CustomUserAdmin(UserAdmin):
    model = CustomUser
    search_fields = ["email"]
    ordering = ['email']

admin.site.register(CustomUser, CustomUserAdmin)
