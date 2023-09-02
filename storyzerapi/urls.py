from django.contrib import admin
from django.urls import path

from . import views

urlpatterns = [
    # User
    path('users/', views.UserViewSet.as_view({'post': 'create'}), name='user-create'),
    path('users/detail', views.UserDetailView.as_view(), name='user-detail'),
    path('email/verify/', views.EmailVerifyView.as_view(), name='email-verify'),
    path('email/verify/<str:token>/<str:uid>/', views.EmailVerifyTokenView.as_view(), name='email-verify-token'),
    path('password/reset/', views.PasswordResetView.as_view(), name='password-reset'),
    path('password/reset/confirm/', views.PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    
    path('chatgpt/translate/', views.ChatGPTTranslateView.as_view(), name='chatgpt-translate'),
    # path('chatgpt/analyze/', views.ChatGPTAnalyzesView.as_view(), name='chatgpt-analyzes', ),
    path('chatgpt/', views.ChatGPTView.as_view(), name='chatgpt'),
    
    # 영화 분석
    path('movie/prediction', views.MoviePredictionView.as_view(), name='movie-prediction'),
    
    # 결과 저장
    # path('result/save', views.ResultSaveView.as_view(), name='result-save'),
    path('result/list', views.ResultListView.as_view(), name='result-list'),
]