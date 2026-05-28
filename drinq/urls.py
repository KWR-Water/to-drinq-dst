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
# import debug_toolbar
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView, TemplateView
from django.contrib import admin
import django.contrib.auth.views as auth_views
from drinq import views
from drinq.forms import CustomUserAuthForm
from drinq.api_views import DigestDesignParametersAPI
from accounts.views import UserAPI
from accounts.api import UserViewSet

urlpatterns = [
    path("", views.index, name='drinq'),
    path('db_stats/', views.db_stats, name='db_stats'),
    # path('form/', views.dst_form_surfacewater, name='drinq_form'),
    # path('multi_form/', views.MultiStepQuestionnaire.as_view(
    #     [
    #         CustomUserAuthForm,
    #         Step2Form,
    #         ], template_name='drinq/form_multi.html',
    #     ), name='drinq_form'),
    path('session_select/',  views.SessionSelectView.as_view(),
         name='session_select'),
    path(
        'configuration_manage/',
        views.ConfigurationManagementView.as_view(),
        name='configuration_manage',
    ),
    path(
        'configuration_manage/<int:pk>/edit/',
        views.ConfigurationUpdateView.as_view(),
        name='configuration_edit',
    ),
    path('form-name/', views.FormNameView.as_view(), name='form_name'),
    path(
        'form-designtree/', views.FormWaterSourceView.as_view(),
        name='form_watersource'),
    path('multi_form/<int:decidingfactor_id>/',
         views.MultiStepQuestionView.as_view(),
         name='form_multistep'),
    path('form_complete/<slug:session_key>/',
         views.QuestionsCompleteView.as_view(),
         name='form_complete'),
    path('treatmentdesign_details/<slug:slug>',
         views.TreatmentDesignDetailView.as_view(),
         name='design_detail'),
    path('treatmentdesign/name/',
         views.NamedDesignCreateView.as_view(),
         name='name_treatmentdesign'),
    path('treatmentdesign_details/<slug:slug>/edit/',
         views.NamedDesignUpdateView.as_view(),
         name='edit_treatmentdesign'),
    # path('form/', views.my_multi_step_view, name='drinq_form'),
    path('success/', TemplateView.as_view(template_name="success.html"),
         name='success'),
    path('form_result/', RedirectView.as_view(), name='form_result'),
    # Treatment plant design parameter input and results
    path(
        'treatmentplant/<int:plant_id>/parameters/',
        views.DesignParameterInputView.as_view(),
        name='design_parameter_input'
    ),
    path(
        'treatmentplant/<int:plant_id>/results/',
        views.DesignParameterResultsView.as_view(),
        name='design_parameter_results'
    ),
    path(
        'treatmentplant/<int:plant_id>/results/export/csv/',
        views.DesignParameterResultsExportCsvView.as_view(),
        name='design_parameter_results_export_csv',
    ),
    path(
        'treatmentplant/compare/',
        views.TreatmentPlantComparisonView.as_view(),
        name='treatmentplant_compare',
    ),
    path(
        'treatmentplant/<int:plant_id>/adaptability/',
        views.AdaptabilityDetailView.as_view(),
        name='adaptability_details',
    ),
    path(
        'treatmentplant/<int:plant_id>/technology/',
        views.TechnologyPropertiesView.as_view(),
        name='technology_properties',
    ),
    path('api/process_parameters/',
         DigestDesignParametersAPI.as_view(),
         name='api_process_parameters'),
    path('compound/<cid>/', views.compound_detail, name='drinq'),
    # path('config/', views.ConfigWizard.as_view(), name='config_wizard'),
    path('admin/', admin.site.urls),
    path('', views.Welcome.as_view(), name='index'),
    path('accounts/profile/', views.Welcome.as_view(), name='index'),
    # path('accounts/profile/', user_detail),  # doesn't work
    path('login/',
         RedirectView.as_view(
             pattern_name='rest_framework:login', permanent=False),
         name='login'),
    path('logout/',
         RedirectView.as_view(
             pattern_name='rest_framework:logout', permanent=False),
         name='logout'),
    path('register/',
         RedirectView.as_view(
             pattern_name='rest_framework:register', permanent=False),
         name='register'),
    path('accounts/', include('accounts.urls')),  # Include the app's URLs
    path('accounts/users', UserViewSet.as_view, name='users'),
    path('accounts/users/<user_id>/', UserAPI.as_view()),
    # path('api/users/<user_id>/profile/', ProfileAPI.as_view()),
    path(
        'change-password/',
        auth_views.PasswordChangeView.as_view(),
        name='change-password'),
    path(
        'change-password/done',
        views.PasswordChangeOk.as_view(),
        name='change-password-done'),
    path(
        'accounts-auth/',
        include('rest_framework.urls', namespace='rest_framework'),
    ),
    # path('__debug__/', include(debug_toolbar.urls)),
    # path('compound/<int:cid>/', views.compound_detail, name='drinq'),
] + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

