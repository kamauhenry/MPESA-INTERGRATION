from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='payment'),
    path('callback/', views.callback, name='callback'),
    path('stk-status/', views.stk_status_view, name='stk_status'),

] 