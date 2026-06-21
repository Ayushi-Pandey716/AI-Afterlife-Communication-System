from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('create/', views.create_persona, name='create_persona'),
    path('upload/<int:persona_id>/', views.upload_data, name='upload_data'),
    path('chat/<int:persona_id>/', views.chat_interface, name='chat_interface'),
    path('chat/<int:persona_id>/send/', views.send_message, name='send_message'),
    path('chat/<int:persona_id>/summary/', views.get_conversation_summary, name='conversation_summary'),
    path('train/<int:persona_id>/', views.start_training, name='start_training'),
    path('training-progress/<int:persona_id>/', views.training_progress, name='training_progress'),
]
