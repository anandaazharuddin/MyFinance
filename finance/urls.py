from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('', views.landing, name='landing'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('transactions/', views.transactions, name='transactions'),
    path('budgets/', views.budgets, name='budgets'),
    path('goals/', views.goals, name='goals'),
    path('api/transactions/', views.api_create_transaction, name='api_tx_create'),
    path('api/transactions/<int:pk>/delete/', views.api_delete_transaction, name='api_tx_delete'),
    path('api/transactions/summary/', views.api_tx_summary, name='api_tx_summary'),
    path('api/categories/', views.api_create_category, name='api_category_create'),
    path('api/budgets/', views.api_save_budget, name='api_budget_save'),
    path('api/budgets/<int:pk>/delete/', views.api_delete_budget, name='api_budget_delete'),
    path('api/goals/', views.api_create_goal, name='api_goal_create'),
    path('api/goals/<int:pk>/contribute/', views.api_goal_contribute, name='api_goal_contribute'),
    path('api/goals/<int:pk>/delete/', views.api_delete_goal, name='api_goal_delete'),
    path('api/seed/', views.api_seed, name='api_seed'),
    # Integrasi Telegram — dipanggil main.js (polling update bot)
    path('api/telegram/poll/', views.api_telegram_poll, name='api_tg_poll'),
]
