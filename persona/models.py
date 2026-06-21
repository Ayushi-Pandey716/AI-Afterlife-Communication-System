from django.db import models
from django.contrib.auth.models import User
import json

class MemorialPersona(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    is_trained = models.BooleanField(default=False)
    
    # Training progress tracking
    training_status = models.CharField(max_length=20, choices=[
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='not_started')
    training_progress = models.IntegerField(default=0)  # 0-100 percentage
    training_step_message = models.CharField(max_length=200, default='', blank=True)  # current step text
    training_accuracy = models.JSONField(default=dict)  # final accuracy breakdown after training
    training_data = models.JSONField(default=list)
    
    # Persona characteristics
    personality_traits = models.JSONField(default=dict)
    communication_style = models.JSONField(default=dict)
    common_phrases = models.JSONField(default=list)
    voice_characteristics = models.JSONField(default=dict)
    
    def __str__(self):
        return f"{self.name} - {self.user.username}"

class DataUpload(models.Model):
    persona = models.ForeignKey(MemorialPersona, on_delete=models.CASCADE)
    upload_type = models.CharField(max_length=20, choices=[
        ('whatsapp', 'WhatsApp Chat'),
        ('voice', 'Voice Recording')
    ])
    file = models.FileField(upload_to='uploads/')
    processed = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=[
        ('pending', 'Pending'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed')
    ], default='pending')
    error_message = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

class ChatMessage(models.Model):
    persona = models.ForeignKey(MemorialPersona, on_delete=models.CASCADE)
    user_message = models.TextField()
    ai_response = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    response_type = models.CharField(max_length=10, choices=[
        ('text', 'Text'),
        ('voice', 'Voice')
    ], default='text')
    voice_file = models.FileField(upload_to='generated_voices/', null=True, blank=True)
