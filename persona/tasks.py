from celery import shared_task
from .models import MemorialPersona, DataUpload, ChatMessage
from data_processor.whatsapp_parser import WhatsAppParser
from voice.voice_processor import VoiceProcessor
import os

@shared_task
def process_whatsapp_data(upload_id):
    upload = DataUpload.objects.get(id=upload_id)
    parser = WhatsAppParser(upload.file.path)
    
    messages = parser.parse_chat()
    analysis = parser.analyze_persona(upload.persona.name)
    
    # Update persona with analysis
    persona = upload.persona
    persona.personality_traits = analysis['communication_patterns']
    persona.communication_style = {
        'avg_message_length': analysis['avg_message_length'],
        'total_messages': analysis['total_messages']
    }
    persona.common_phrases = list(analysis['common_words'].keys())[:20]
    persona.save()
    
    upload.processed = True
    upload.save()
    
    return "WhatsApp data processed successfully"

@shared_task
def process_voice_data(upload_id):
    upload = DataUpload.objects.get(id=upload_id)
    processor = VoiceProcessor()
    
    voice_features = processor.analyze_voice_sample(upload.file.path)
    
    if voice_features:
        persona = upload.persona
        persona.voice_characteristics = voice_features
        persona.is_trained = True
        persona.save()
    
    upload.processed = True
    upload.save()
    
    return "Voice data processed successfully"

@shared_task
def generate_voice_response(message_id):
    message = ChatMessage.objects.get(id=message_id)
    processor = VoiceProcessor()
    
    # Find a voice sample for this persona
    voice_upload = DataUpload.objects.filter(
        persona=message.persona,
        upload_type='voice',
        processed=True
    ).first()
    
    if voice_upload:
        output_path = f'media/generated_voices/response_{message_id}.wav'
        success = processor.clone_voice(
            text=message.ai_response,
            output_path=output_path,
            speaker_wav_path=voice_upload.file.path
        )
        
        if success:
            message.voice_file = output_path
            message.save()
    
    return "Voice response generated"
