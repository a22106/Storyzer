from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('users/', views.UserViewSet.as_view({'post': 'create'}), name='user-create'),
    path('email/verify/', views.EmailVerifyView.as_view(), name='email-verify'),
    path('email/verify/<str:token>/<str:uid>/', views.EmailVerifyTokenView.as_view(), name='email-verify-token'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password-reset'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('users/<int:id>/roles/', views.UserRoleView.as_view(), name='user-roles'),
]