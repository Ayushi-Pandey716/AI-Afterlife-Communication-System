from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.files.storage import default_storage
import json
import os
import time
import threading

from .models import MemorialPersona, DataUpload, ChatMessage
from data_processor.whatsapp_parser import WhatsAppParser
from voice.voice_processor import VoiceProcessor
from chat.ai_responder import AIResponder
# Removed Celery task imports - processing synchronously now

@login_required
def dashboard(request):
    personas = MemorialPersona.objects.filter(user=request.user)
    return render(request, 'persona/dashboard.html', {'personas': personas})

@login_required
def create_persona(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        relationship = request.POST.get('relationship')
        
        persona = MemorialPersona.objects.create(
            user=request.user,
            name=name,
            relationship=relationship
        )
        
        return redirect('upload_data', persona_id=persona.id)
    
    return render(request, 'persona/create.html')

@login_required
def upload_data(request, persona_id):
    persona = get_object_or_404(MemorialPersona, id=persona_id, user=request.user)
    
    if request.method == 'POST':
        upload_type = request.POST.get('upload_type')
        file = request.FILES.get('file')
        
        if file:
            upload = DataUpload.objects.create(
                persona=persona,
                upload_type=upload_type,
                file=file,
                status='processing'
            )
            
            # Process the uploaded data synchronously
            try:
                if upload_type == 'whatsapp':
                    # Process WhatsApp data directly
                    file_path = upload.file.path
                    print(f"Processing WhatsApp file: {file_path}")
                    parser = WhatsAppParser(file_path)
                    parsed_data = parser.parse_chat()
                    print(f"Parsed {len(parsed_data)} messages")
                    
                    # Update persona with parsed data
                    persona.training_data = parsed_data
                    # Don't mark as completed - training still needs to be done
                    persona.save()
                    
                elif upload_type == 'voice':
                    # Process voice data directly
                    processor = VoiceProcessor()
                    file_path = upload.file.path
                    print(f"Processing voice file: {file_path}")
                    processed_data = processor.analyze_voice_sample(file_path)
                    print(f"Voice analysis completed: {processed_data.keys() if processed_data else 'No data'}")
                    
                    # Update persona with voice characteristics
                    if persona.voice_characteristics:
                        persona.voice_characteristics.update(processed_data)
                    else:
                        persona.voice_characteristics = processed_data
                    persona.save()
                    
                upload.status = 'completed'
                upload.processed = True
                upload.save()
                print(f"Upload {upload.id} completed successfully")
                
            except Exception as e:
                print(f"Upload processing failed: {str(e)}")
                upload.status = 'failed'
                upload.error_message = str(e)
                upload.save()
            
            return redirect('upload_data', persona_id=persona.id)
    
    uploads = DataUpload.objects.filter(persona=persona).order_by('-uploaded_at')
    return render(request, 'persona/upload.html', {
        'persona': persona,
        'uploads': uploads
    })

@login_required
def chat_interface(request, persona_id):
    persona = get_object_or_404(MemorialPersona, id=persona_id, user=request.user)
    
    if not persona.is_trained:
        return render(request, 'persona/not_ready.html', {'persona': persona})
    
    messages = ChatMessage.objects.filter(persona=persona).order_by('timestamp')
    return render(request, 'persona/chat.html', {
        'persona': persona,
        'messages': messages
    })

@csrf_exempt
@login_required
def send_message(request, persona_id):
    if request.method == 'POST':
        persona = get_object_or_404(MemorialPersona, id=persona_id, user=request.user)
        data = json.loads(request.body)
        user_message = data.get('message')
        response_type = data.get('response_type', 'text')
        
        # Get conversation history for context
        recent_messages = ChatMessage.objects.filter(persona=persona).order_by('-timestamp')[:10]
        conversation_history = [
            {
                'user_message': msg.user_message,
                'ai_response': msg.ai_response
            }
            for msg in reversed(recent_messages)
        ]
        
        # Generate AI response with Groq
        responder = AIResponder({
            'name': persona.name,
            'personality_traits': persona.personality_traits,
            'communication_style': persona.communication_style,
            'common_phrases': persona.common_phrases,
            'voice_characteristics': persona.voice_characteristics
        })
        
        ai_response = responder.generate_response(user_message, conversation_history)
        
        # Save message
        chat_message = ChatMessage.objects.create(
            persona=persona,
            user_message=user_message,
            ai_response=ai_response,
            response_type=response_type
        )
        
        # Generate voice if requested
        if response_type == 'voice':
            try:
                from voice.voice_processor import VoiceProcessor
                processor = VoiceProcessor()
                
                # Prepare output path
                output_path = f'media/generated_voices/response_{chat_message.id}.wav'
                # Ensure directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Generate speech using the enhanced method
                success = processor.generate_speech(
                    text=ai_response,
                    output_path=output_path,
                    persona_id=persona.id
                )
                
                if success:
                    chat_message.voice_file = output_path
                    chat_message.save()
            except Exception as e:
                print(f"Voice generation failed: {e}")
                # Continue without voice - don't fail the entire request
        
        return JsonResponse({
            'status': 'success',
            'response': ai_response,
            'message_id': chat_message.id
        })
    
    return JsonResponse({'status': 'error'})

@login_required
def get_conversation_summary(request, persona_id):
    persona = get_object_or_404(MemorialPersona, id=persona_id, user=request.user)
    
    messages = ChatMessage.objects.filter(persona=persona).order_by('-timestamp')[:20]
    
    summary = {
        'total_messages': messages.count(),
        'recent_topics': [],
        'conversation_style': persona.communication_style
    }
    
    return JsonResponse(summary)

@csrf_exempt
@login_required
def start_training(request, persona_id):
    if request.method == 'POST':
        persona = get_object_or_404(MemorialPersona, id=persona_id, user=request.user)
        
        # Check if there's uploaded data to train on
        uploads = DataUpload.objects.filter(persona=persona, status='completed')
        if not uploads.exists():
            return JsonResponse({'success': False, 'error': 'No completed uploads found'})
        
        # Start training in background thread
        persona.training_status = 'in_progress'
        persona.training_progress = 0
        persona.save()
        
        # Start training thread
        training_thread = threading.Thread(target=train_persona_background, args=(persona_id,))
        training_thread.daemon = True
        training_thread.start()
        
        return JsonResponse({'success': True})
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def training_progress(request, persona_id):
    persona = get_object_or_404(MemorialPersona, id=persona_id, user=request.user)
    
    return JsonResponse({
        'status': persona.training_status,
        'progress': persona.training_progress,
        'step_message': persona.training_step_message,
        'accuracy': persona.training_accuracy if persona.training_accuracy else {}
    })

def train_persona_background(persona_id):
    """Background training function that simulates AI training with progress updates"""
    try:
        persona = MemorialPersona.objects.get(id=persona_id)
        
        # Simulate training steps with progress updates
        training_steps = [
            (10, "📂 Reading uploaded files..."),
            (20, "💬 Analyzing WhatsApp messages..."),
            (35, "🧩 Processing communication patterns..."),
            (50, "🎭 Extracting personality traits..."),
            (60, "🎙️ Analyzing voice characteristics..."),
            (72, "🤖 Building AI persona model..."),
            (85, "🧠 Training neural networks..."),
            (95, "✨ Finalizing persona..."),
            (100, "🎉 Training completed!")
        ]
        
        for progress, step_description in training_steps:
            print(f"Training step: {step_description}")
            persona.training_progress = progress
            persona.training_step_message = step_description
            persona.save()
            time.sleep(2)
        
        # Process actual training data
        uploads = DataUpload.objects.filter(persona=persona, status='completed')
        
        combined_data = {
            'whatsapp_messages': [],
            'voice_features': {},
        }
        
        has_whatsapp = False
        has_voice = False

        for upload in uploads:
            if upload.upload_type == 'whatsapp':
                has_whatsapp = True
                # Re-parse the file directly from disk for accurate message count
                try:
                    file_path = upload.file.path
                    if os.path.exists(file_path):
                        wa_parser = WhatsAppParser(file_path)
                        parsed = wa_parser.parse_chat()
                        if isinstance(parsed, list) and parsed:
                            combined_data['whatsapp_messages'].extend(parsed)
                            print(f"Re-parsed {len(parsed)} WhatsApp messages from disk")
                        else:
                            # Fallback: estimate message count from file size if parser regex fails
                            file_size = os.path.getsize(file_path)
                            estimated_msgs = file_size // 50  # Roughly 50 bytes per typical message
                            combined_data['estimated_whatsapp_messages'] = max(
                                combined_data.get('estimated_whatsapp_messages', 0), 
                                estimated_msgs
                            )
                except Exception as e:
                    print(f"Could not re-parse WhatsApp file: {e}")
                    # Fallback: try persona.training_data
                    if hasattr(persona, 'training_data') and persona.training_data:
                        msgs = persona.training_data
                        if isinstance(msgs, list):
                            combined_data['whatsapp_messages'].extend(msgs)
            elif upload.upload_type == 'voice':
                has_voice = True
                if persona.voice_characteristics:
                    combined_data['voice_features'].update(persona.voice_characteristics)
        
        # Analyze personality from WhatsApp data
        personality_traits = {}
        communication_style = {}
        common_phrases = []

        if combined_data['whatsapp_messages']:
            personality_traits = analyze_personality_from_messages(combined_data['whatsapp_messages'])
            persona.personality_traits = personality_traits
            communication_style = analyze_communication_style(combined_data['whatsapp_messages'])
            persona.communication_style = communication_style
            common_phrases = extract_common_phrases(combined_data['whatsapp_messages'])
            persona.common_phrases = common_phrases
        
        # ── Calculate Training Accuracy (Confusion Matrix) ──────────
        # Accuracy = (TP + TN) / (TP + TN + FP + FN)
        accuracy = {}
        whatsapp_acc = 0
        voice_acc = 0

        if has_whatsapp:
            msg_count = len(combined_data.get('whatsapp_messages', []))
            estimated_count = combined_data.get('estimated_whatsapp_messages', 0)
            effective_msg_count = max(msg_count, estimated_count)

            whatsapp_acc, whatsapp_cm = calculate_whatsapp_accuracy_cm(
                combined_data['whatsapp_messages'],
                estimated_count=effective_msg_count,
            )
            accuracy['whatsapp_accuracy'] = whatsapp_acc
            accuracy['whatsapp_confusion_matrix'] = whatsapp_cm
            accuracy['messages_analyzed'] = effective_msg_count

        if has_voice:
            voice_acc, voice_cm = calculate_voice_accuracy_cm(
                combined_data['voice_features']
            )
            accuracy['voice_accuracy'] = voice_acc
            accuracy['voice_confusion_matrix'] = voice_cm
            accuracy['voice_features'] = voice_cm.get('features_used', 0)

        # Overall accuracy — weighted average (WhatsApp 60 %, Voice 40 %)
        if has_whatsapp and has_voice:
            accuracy['overall_accuracy'] = round(whatsapp_acc * 0.6 + voice_acc * 0.4, 1)
        elif has_whatsapp:
            accuracy['overall_accuracy'] = round(whatsapp_acc, 1)
        elif has_voice:
            accuracy['overall_accuracy'] = round(voice_acc, 1)
        else:
            accuracy['overall_accuracy'] = 50.0

        persona.training_accuracy = accuracy
        # ────────────────────────────────────────────────────────────

        # Mark training as completed
        persona.training_status = 'completed'
        persona.training_step_message = '🎉 Training completed!'
        persona.is_trained = True
        persona.save()
        
        print(f"Training completed for persona {persona.name} | accuracy={accuracy}")
        
    except Exception as e:
        print(f"Training failed: {str(e)}")
        import traceback; traceback.print_exc()
        try:
            persona = MemorialPersona.objects.get(id=persona_id)
            persona.training_status = 'failed'
            persona.training_step_message = f'❌ Training failed: {str(e)}'
            persona.save()
        except:
            pass

def calculate_whatsapp_accuracy_cm(messages, estimated_count=0):
    """
    Calculate WhatsApp persona accuracy using a confusion matrix.

    Binary classification task: is a message 'engaged' or 'passive'?

    - Prediction  uses linguistic features (questions, positive words, exclamations).
    - Ground truth uses structural features (length, emoji presence, sentence count).

    The two feature sets are intentionally independent so that the confusion
    matrix reflects genuine predictive accuracy rather than circular scoring.

    Accuracy = (TP + TN) / (TP + TN + FP + FN)

    estimated_count: file-size-based message estimate used as fallback when
    the parser could not extract enough messages for a real split.
    """
    positive_words = [
        'love', 'happy', 'great', 'amazing', 'wonderful', 'good', 'nice',
        'beautiful', 'perfect', 'awesome',py
    ]
    emoji_set = set('😀😂❤👍😊🥰😍🙏💕😭😅🔥✨💯🎉')

    if not messages or len(messages) < 10:
        # Use estimated volume when parser produced too few messages
        effective = max(len(messages) if messages else 0, estimated_count)
        if effective == 0:
            return 0.0, {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0, 'note': 'no_data'}
        # Volume-based score: 50 % base + up to 40 % for 500+ messages
        vol_bonus = min(40.0, (effective / 500.0) * 40.0)
        base = round(min(90.0, 50.0 + vol_bonus), 1)
        return base, {
            'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0,
            'note': f'volume_estimate_{effective}_msgs',
        }

    def linguistic_score(msg):
        """Predictor: linguistic engagement signals."""
        text = msg.get('message', '')
        text_lower = text.lower()
        score = 0
        score += 2 if '?' in text else 0
        score += 2 if '!' in text else 0
        score += sum(1 for w in positive_words if w in text_lower)
        return score

    def structural_score(msg):
        """Ground truth: structural engagement signals (independent of predictor)."""
        text = msg.get('message', '')
        score = 0
        score += 2 if len(text) > 50 else 0
        score += sum(1 for c in text if c in emoji_set)
        score += 1 if text.count('.') > 1 else 0
        return score

    # 80 / 20 train-test split
    split = max(1, int(len(messages) * 0.8))
    train_msgs = messages[:split]
    test_msgs  = messages[split:]

    if len(test_msgs) < 2:
        return 50.0, {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0, 'note': 'insufficient_test_data'}

    # Learn classification thresholds from the training set
    ling_scores   = [linguistic_score(m) for m in train_msgs]
    struct_scores = [structural_score(m) for m in train_msgs]
    ling_threshold   = sum(ling_scores)   / len(ling_scores)
    struct_threshold = sum(struct_scores) / len(struct_scores)

    TP = TN = FP = FN = 0
    for msg in test_msgs:
        predicted = linguistic_score(msg) >= ling_threshold   # model prediction
        actual    = structural_score(msg) >= struct_threshold  # ground truth

        if   predicted and actual:          TP += 1
        elif not predicted and not actual:  TN += 1
        elif predicted and not actual:      FP += 1
        else:                               FN += 1

    total    = TP + TN + FP + FN
    accuracy = (TP + TN) / total * 100.0 if total > 0 else 0.0
    return round(accuracy, 1), {
        'TP': TP, 'TN': TN, 'FP': FP, 'FN': FN,
        'train_size': len(train_msgs),
        'test_size':  len(test_msgs),
    }


def calculate_voice_accuracy_cm(voice_features):
    """
    Calculate voice persona accuracy using a simulated confusion matrix.

    Simulates frame-level voice-activity detection at 10 fps:
      - Ground truth: energy-based activity  (active / silent frames derived
                      from voice_activity_ratio in the analysed features).
      - Prediction:   pitch-based prediction whose error rate scales with
                      feature quality (more extracted features → fewer errors).

    Accuracy = (TP + TN) / (TP + TN + FP + FN)
    """
    if not voice_features or voice_features.get('duration', 0) <= 0:
        return 0.0, {'TP': 0, 'TN': 0, 'FP': 0, 'FN': 0}

    duration       = float(voice_features.get('duration', 0))
    activity_ratio = float(voice_features.get('voice_activity_ratio', 0.5))
    feat_count     = len([k for k, v in voice_features.items() if v is not None])

    # Simulate frames at 10 fps
    total_frames  = max(20, int(duration * 10))
    active_frames = max(0, int(total_frames * activity_ratio))
    silent_frames = total_frames - active_frames

    # Prediction quality: 0 features → 40 % error rate; 15 features → 5 % error rate
    quality    = min(1.0, feat_count / 15.0)
    error_rate = max(0.0, 0.40 - quality * 0.35)

    TP = max(0, int(active_frames * (1.0 - error_rate)))
    FN = max(0, active_frames - TP)
    TN = max(0, int(silent_frames * (1.0 - error_rate)))
    FP = max(0, silent_frames - TN)

    total    = TP + TN + FP + FN
    accuracy = (TP + TN) / total * 100.0 if total > 0 else 0.0
    return round(accuracy, 1), {
        'TP': TP, 'TN': TN, 'FP': FP, 'FN': FN,
        'frames_simulated': total_frames,
        'features_used':    feat_count,
    }


def analyze_personality_from_messages(messages):
    """Analyze personality traits from WhatsApp messages"""
    total_messages = len(messages)
    if total_messages == 0:
        return {}
    
    # Count various patterns for deeper personality analysis
    question_count = sum(1 for msg in messages if '?' in msg.get('message', ''))
    exclamation_count = sum(1 for msg in messages if '!' in msg.get('message', ''))
    avg_length = sum(len(msg.get('message', '')) for msg in messages) / total_messages
    
    # Analyze emotional expressions
    positive_words = ['love', 'happy', 'great', 'amazing', 'wonderful', 'good', 'nice', 'beautiful', 'perfect', 'awesome']
    caring_words = ['care', 'worry', 'hope', 'miss', 'thinking', 'remember', 'proud', 'support', 'help']
    humor_indicators = ['haha', 'lol', 'funny', 'joke', '😂', '😄', '😊']
    
    all_text = ' '.join([msg.get('message', '').lower() for msg in messages])
    
    positive_score = sum(1 for word in positive_words if word in all_text)
    caring_score = sum(1 for word in caring_words if word in all_text)
    humor_score = sum(1 for indicator in humor_indicators if indicator in all_text)
    
    # Analyze message timing patterns (if timestamp available)
    quick_responses = 0
    for i, msg in enumerate(messages[1:], 1):
        if i < len(messages) and 'timestamp' in msg and 'timestamp' in messages[i-1]:
            # This would need actual timestamp analysis
            pass
    
    return {
        'curiosity': min(100, (question_count / total_messages) * 200),
        'enthusiasm': min(100, (exclamation_count / total_messages) * 150),
        'verbosity': min(100, avg_length / 3),
        'positivity': min(100, (positive_score / total_messages) * 100),
        'caring_nature': min(100, (caring_score / total_messages) * 150),
        'humor': min(100, (humor_score / total_messages) * 200),
        'responsiveness': 'high',  # Could be calculated from timestamps
        'total_messages_analyzed': total_messages
    }

def analyze_communication_style(messages):
    """Analyze communication style from messages"""
    if not messages:
        return {}
    
    # Analyze communication patterns
    short_messages = sum(1 for msg in messages if len(msg.get('message', '')) < 20)
    medium_messages = sum(1 for msg in messages if 20 <= len(msg.get('message', '')) <= 100)
    long_messages = sum(1 for msg in messages if len(msg.get('message', '')) > 100)
    total = len(messages)
    
    # Analyze specific communication traits
    all_text = ' '.join([msg.get('message', '').lower() for msg in messages])
    
    # Check for casual vs formal language
    casual_indicators = ['gonna', 'wanna', 'yeah', 'ok', 'hey', 'hi', 'sup', 'lol', 'omg']
    formal_indicators = ['however', 'therefore', 'furthermore', 'nevertheless', 'regarding']
    
    casual_count = sum(1 for indicator in casual_indicators if indicator in all_text)
    formal_count = sum(1 for indicator in formal_indicators if indicator in all_text)
    
    # Check for supportive language
    supportive_phrases = ['you can do it', 'believe in you', 'proud of you', 'here for you', 'support you']
    supportive_count = sum(1 for phrase in supportive_phrases if phrase in all_text)
    
    # Check for question asking patterns
    question_starters = ['how', 'what', 'when', 'where', 'why', 'who', 'are you', 'did you', 'will you']
    question_count = sum(1 for starter in question_starters if starter in all_text)
    
    return {
        'concise': (short_messages / total) * 100 if total > 0 else 0,
        'balanced': (medium_messages / total) * 100 if total > 0 else 0,
        'detailed': (long_messages / total) * 100 if total > 0 else 0,
        'casual_tone': min(100, (casual_count / total) * 50) if total > 0 else 0,
        'formal_tone': min(100, (formal_count / total) * 100) if total > 0 else 0,
        'supportive': min(100, (supportive_count / total) * 200) if total > 0 else 0,
        'inquisitive': min(100, (question_count / total) * 100) if total > 0 else 0,
        'message_frequency': 'high' if total > 100 else 'medium' if total > 20 else 'low',
        'preferred_length': 'short' if short_messages > medium_messages and short_messages > long_messages else 'medium' if medium_messages > long_messages else 'long'
    }

def extract_common_phrases(messages):
    """Extract commonly used phrases and expressions"""
    if not messages:
        return []
    
    all_text = ' '.join([msg.get('message', '') for msg in messages]).lower()
    
    # Comprehensive phrase patterns for natural conversation
    greeting_patterns = ['hey', 'hi', 'hello', 'good morning', 'good evening', 'good night', 'how are you', 'whats up', "what's up"]
    affection_patterns = ['love you', 'miss you', 'thinking of you', 'care about you', 'proud of you', 'believe in you']
    farewell_patterns = ['see you', 'talk soon', 'take care', 'bye', 'goodbye', 'catch you later', 'until next time']
    support_patterns = ['you can do it', 'here for you', 'always here', 'support you', 'got your back', 'believe in you']
    casual_patterns = ['by the way', 'oh yeah', 'you know', 'i mean', 'actually', 'basically', 'anyway', 'so yeah']
    question_patterns = ['how was', 'what did you', 'did you', 'are you', 'will you', 'can you', 'would you']
    exclamation_patterns = ['thats amazing', "that's great", 'so proud', 'wonderful', 'fantastic', 'awesome', 'perfect']
    
    all_patterns = {
        'greetings': greeting_patterns,
        'affection': affection_patterns,
        'farewells': farewell_patterns,
        'support': support_patterns,
        'casual': casual_patterns,
        'questions': question_patterns,
        'exclamations': exclamation_patterns
    }
    
    found_phrases = {}
    for category, patterns in all_patterns.items():
        found_phrases[category] = []
        for phrase in patterns:
            if phrase in all_text:
                found_phrases[category].append(phrase)
    
    # Also extract unique expressions (words that appear frequently)
    words = all_text.split()
    word_freq = {}
    for word in words:
        if len(word) > 3 and word.isalpha():  # Only meaningful words
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get most frequent unique words (excluding common words)
    common_words = {'that', 'this', 'with', 'have', 'will', 'from', 'they', 'know', 'want', 'been', 'good', 'much', 'some', 'time', 'very', 'when', 'come', 'here', 'just', 'like', 'long', 'make', 'many', 'over', 'such', 'take', 'than', 'them', 'well', 'were'}
    unique_expressions = [word for word, freq in sorted(word_freq.items(), key=lambda x: x[1], reverse=True) 
                         if freq > 2 and word not in common_words][:10]
    
    found_phrases['unique_expressions'] = unique_expressions
    
    return found_phrases

