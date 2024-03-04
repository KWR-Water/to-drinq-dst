import re
from django.shortcuts import render
from django.utils.timezone import datetime
from django.http import HttpResponse


# Create your views here.
def home(request):
    context = {
        'message': 'Hello, Django!',
    }
    return render(request, "pages/home.html", context=context)
