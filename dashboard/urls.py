from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/image-upload/', views.image_upload, name="image_upload"),
    path('profile/edit/', views.edit_user, name="edit_user"),
    path('profile/', views.profile, name='profile'),
    path('team/', views.team, name='team'),
    path('team/new/', views.add_employee, name='add_employee'),
    path('team/<int:pk>/', views.team_member, name='team_member'),
    path('equipments/', views.equipments, name='equipments'),
    path('equipments/<int:pk>/', views.equipment, name='equipment'),
    path('equipments/new/', views.add_equipment, name='add_equipment'),
    path('allocations/', views.allocations, name='allocations'),
    path('categories/new/', views.add_category, name='add_category'),
]
