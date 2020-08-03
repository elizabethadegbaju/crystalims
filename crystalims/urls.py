"""crystalims URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from dashboard import views

urlpatterns = [
                  path('admin/', admin.site.urls),
                  path('activate/<slug:uidb64>/<slug:token>/', views.activate,
                       name="activate"),
                  path('register/', views.signup, name="register"),
                  path('register-company/', views.create,
                       name="register_company"),
                  path('register-social/', views.social_signup,
                       name="register_social"),
                  path('password/', views.change_password,
                       name="change_password"),
                  path('oauth/', include('social_django.urls')),
                  path('', include('django.contrib.auth.urls')),
                  path('', include('dashboard.urls')),
              ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
handler404 = 'dashboard.views.error_404_view'
