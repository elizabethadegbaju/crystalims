from django.urls import path

from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('home/', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/image-upload/', views.image_upload, name="image_upload"),
    path('profile/edit/', views.edit_user, name="edit_user"),
    path('profile/', views.profile, name='profile'),
    path('messages/list/', views.messages, name='messages'),
    path('messages/<int:pk>/', views.message, name='message'),
    path('messages/send/', views.send_message, name='send'),
    path('team/list/', views.team, name='team'),
    path('team/new/', views.add_employee, name='add_employee'),
    path('team/<int:pk>/', views.team_member, name='team_member'),
    path('equipments/list/', views.equipments, name='equipments'),
    path('equipments/new/', views.add_equipment, name='add_equipment'),
    path('equipments/<slug:pk>/', views.equipment, name='equipment'),
    path('allocations/list/', views.allocations, name='allocations'),
    path('categories/new/', views.add_category, name='add_category'),
    path('locations/new/', views.add_location, name='add_location'),
    path('dashboard/export/', views.pdf, name='export_pdf'),
    path('user-not-found/', views.error, name='page_not_found'),
    path('place-order/', views.place_order, name='place_order'),
    path('verify/<int:pk>/', views.verify, name='verify'),
]
