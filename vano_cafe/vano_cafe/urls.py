"""
URL configuration for vano_cafe project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
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
from django.contrib import admin
from django.urls import path
from stock_management.views import custom_login, order_creation, order_queue, order_history, admin_dashboard, stock_management, user_management, UserCreateView, UserUpdateView, UserDeleteView, stock_create, stock_delete, stock_update

urlpatterns = [
    path('', custom_login, name='login'),
    path('order_creation/', order_creation, name='order_creation'),
    path('order_creation/<str:category>/', order_creation, name='order_creation'),
    path('order_queue/', order_queue, name='order_queue'),
    path('order_history/', order_history, name='order_history'),
    path('admin_dashboard/', admin_dashboard, name='admin_dashboard'),
    path('stock_management/', stock_management, name='stock_management'),
    path('stock_management/create/', stock_create, name='stock_create'),
    path('stock_management/update/<int:pk>/', stock_update, name='stock_update'),
    path('stock_management/delete/<int:pk>/', stock_delete, name='stock_delete'),
    path('user_management/', user_management, name='user_management'),
    path('user_management/create/', UserCreateView.as_view(), name='user_create'),
    path('user_management/update/<int:pk>/', UserUpdateView.as_view(), name='user_update'),
    path('user_management/delete/<int:pk>/', UserDeleteView.as_view(), name='user_delete')
]
