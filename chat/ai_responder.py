import requests
import json
import random
import time
from django.conf import settings

class AIResponder:
    def __init__(self, persona_data):
        self.persona_data = persona_data
        self.personality_traits = persona_data.get('personality_traits', {})
        self.communication_style = persona_data.get('communication_style', {})
        self.common_phrases = persona_data.get('common_phrases', [])
        self.voice_characteristics = persona_data.get('voice_characteristics', {})
        
        # Groq API configuration
        self.api_key = settings.GROQ_API_KEY
        self.model_name = settings.GROQ_MODEL_NAME
        self.api_url = settings.GROQ_API_URL
        
        # Build persona context
        self.persona_context = self._build_persona_context()
    
    def _build_persona_context(self):
        """Build detailed context string from persona data for natural responses"""
        name = self.persona_data.get('name', 'a loved one')
        context = f"You are {name}, speaking as yourself in a natural, personal way. "
        
        # Add detailed personality traits
        personality = self.persona_data.get('personality_traits', {})
        if personality:
            context += "Your personality: "
            if personality.get('caring_nature', 0) > 50:
                context += "You are deeply caring and always show concern for others. "
            if personality.get('enthusiasm', 0) > 50:
                context += "You express enthusiasm and excitement naturally. "
            if personality.get('humor', 0) > 50:
                context += "You have a good sense of humor and like to make people smile. "
            if personality.get('positivity', 0) > 50:
                context += "You maintain a positive outlook and encourage others. "
            if personality.get('curiosity', 0) > 50:
                context += "You ask questions and show genuine interest in others' lives. "
        
        # Add communication style preferences
        comm_style = self.persona_data.get('communication_style', {})
        if comm_style:
            preferred_length = comm_style.get('preferred_length', 'medium')
            if preferred_length == 'short':
                context += "Keep your responses brief and to the point, like you naturally do. "
            elif preferred_length == 'long':
                context += "You can elaborate and share detailed thoughts when appropriate. "
            else:
                context += "Use a natural mix of short and medium-length responses. "
                
            if comm_style.get('casual_tone', 0) > 50:
                context += "Use casual, relaxed language. "
            if comm_style.get('supportive', 0) > 50:
                context += "Always be supportive and encouraging. "
        
        # Add specific phrases and expressions
        phrases = self.persona_data.get('common_phrases', {})
        if isinstance(phrases, dict):
            context += "Your typical expressions: "
            if phrases.get('greetings'):
                context += f"Greet with phrases like '{random.choice(phrases['greetings'])}'. "
            if phrases.get('affection'):
                context += f"Show affection with phrases like '{random.choice(phrases['affection'])}'. "
            if phrases.get('support'):
                context += f"Offer support with phrases like '{random.choice(phrases['support'])}'. "
            if phrases.get('casual'):
                context += f"Use casual expressions like '{random.choice(phrases['casual'])}'. "
        
        # Core behavioral guidelines
        context += f"""
        
IMPORTANT RESPONSE GUIDELINES:
- Respond exactly as {name} would, using their natural speaking style
- Keep responses short and conversational (1-3 sentences max)
- Use the same tone and expressions they typically use
- Be warm, personal, and authentic
- Don't be overly formal or robotic
- React naturally to what the person is saying
- Show genuine care and interest
- Use their typical phrases and expressions when appropriate
- Respond as if you're having a real conversation with someone you care about
        """
        
        return context
    
    def generate_response(self, user_message, conversation_history=[]):
        """Generate AI response using Groq API"""
        try:
            # Build conversation messages
            messages = [
                {
                    "role": "system",
                    "content": self.persona_context
                }
            ]
            
            # Add conversation history (last 5 messages for context)
            recent_history = conversation_history[-5:] if len(conversation_history) > 5 else conversation_history
            for msg in recent_history:
                messages.extend([
                    {"role": "user", "content": msg.get('user_message', '')},
                    {"role": "assistant", "content": msg.get('ai_response', '')}
                ])
            
            # Add current user message
            messages.append({"role": "user", "content": user_message})
            
            # Call Groq API
            response = self._call_groq_api(messages)
            
            if response:
                # Apply persona styling
                styled_response = self._apply_persona_style(response)
                return styled_response
            else:
                return self._generate_fallback_response(user_message)
                
        except Exception as e:
            print(f"Error generating response: {e}")
            return self._generate_fallback_response(user_message)
    
    def _call_groq_api(self, messages):
        """Make API call to Groq"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": self.model_name,
                "messages": messages,
                "temperature": 0.8,  # More creative and natural responses
                "max_tokens": 150,   # Keep responses concise and natural
                "top_p": 0.9,       # Focused but varied responses
                "stop": None
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                data = response.json()
                return data['choices'][0]['message']['content'].strip()
            else:
                print(f"Groq API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None
    
    def _apply_persona_style(self, response):
        """Apply persona-specific styling to make response more natural"""
        if not response:
            return response
            
        # Get persona data for styling
        phrases = self.persona_data.get('common_phrases', {})
        personality = self.persona_data.get('personality_traits', {})
        comm_style = self.persona_data.get('communication_style', {})
        
        # Apply natural phrase integration (less forced)
        if isinstance(phrases, dict) and random.random() < 0.25:
            # Choose appropriate phrase type based on response content
            response_lower = response.lower()
            
            if any(word in response_lower for word in ['hi', 'hello', 'hey']) and phrases.get('greetings'):
                # Don't add greeting if already present
                pass
            elif any(word in response_lower for word in ['love', 'care', 'miss']) and phrases.get('affection'):
                if random.random() < 0.3:
                    affection_phrase = random.choice(phrases['affection'])
                    response = f"{response} {affection_phrase.capitalize()}."
            elif any(word in response_lower for word in ['you can', 'believe', 'support']) and phrases.get('support'):
                if random.random() < 0.3:
                    support_phrase = random.choice(phrases['support'])
                    response = f"{support_phrase.capitalize()}. {response}"
            elif phrases.get('casual') and random.random() < 0.2:
                casual_phrase = random.choice(phrases['casual'])
                response = f"{response} {casual_phrase.capitalize()}."
        
        # Apply personality-based modifications
        if personality.get('enthusiasm', 0) > 60 and random.random() < 0.3:
            if not response.endswith('!') and not response.endswith('?') and len(response) < 100:
                response += "!"
        
        # Add natural follow-up questions based on personality
        if personality.get('curiosity', 0) > 50 and random.random() < 0.25:
            natural_questions = [
                "How are you doing?", "What's going on with you?", 
                "How was your day?", "Everything okay?"
            ]
            if not response.endswith('?'):
                response += f" {random.choice(natural_questions)}"
        
        # Ensure response length matches communication style
        preferred_length = comm_style.get('preferred_length', 'medium')
        if preferred_length == 'short' and len(response) > 100:
            # Keep it shorter - take first sentence
            sentences = response.split('. ')
            response = sentences[0] + ('.' if not sentences[0].endswith(('.', '!', '?')) else '')
        
        return response
    
    def _generate_fallback_response(self, user_message):
        """Generate natural fallback response when API fails"""
        name = self.persona_data.get('name', 'I')
        
        # Get persona-specific phrases for fallback
        phrases = self.persona_data.get('common_phrases', {})
        personality = self.persona_data.get('personality_traits', {})
        
        # Contextual responses based on user message
        user_lower = user_message.lower()
        
        if any(word in user_lower for word in ['hi', 'hello', 'hey']):
            greetings = [
                "Hey there!", "Hi!", "Hello!", "Hey!"
            ]
            if phrases.get('greetings'):
                greetings.extend(phrases['greetings'])
            return random.choice(greetings)
            
        elif any(word in user_lower for word in ['sad', 'miss', 'lonely', 'hurt']):
            comfort_responses = [
                "I hear you, and I want you to know I'm always with you.",
                "I'm here with you in spirit.",
                "You're not alone in this."
            ]
            if phrases.get('support'):
                comfort_responses.extend([f"{phrase}." for phrase in phrases['support']])
            return random.choice(comfort_responses)
            
        elif any(word in user_lower for word in ['happy', 'good', 'great', 'excited']):
            happy_responses = [
                "That makes me so happy!",
                "I'm so glad to hear that!",
                "That's wonderful!"
            ]
            if personality.get('enthusiasm', 0) > 50:
                happy_responses = [resp + "!" if not resp.endswith('!') else resp for resp in happy_responses]
            return random.choice(happy_responses)
            
        elif any(word in user_lower for word in ['love', 'care']):
            love_responses = [
                "I love you too.",
                "You mean everything to me.",
                "Love you so much."
            ]
            if phrases.get('affection'):
                love_responses.extend(phrases['affection'])
            return random.choice(love_responses)
        
        # General fallback responses
        general_responses = [
            "I'm here with you.",
            "Always thinking of you.",
            "You know I care about you.",
            "Take care of yourself.",
            "I believe in you."
        ]
        
        # Add persona-specific general responses
        if phrases.get('casual'):
            general_responses.extend(phrases['casual'])
        
        return random.choice(general_responses)

    def get_conversation_summary(self, messages):
        """Generate a summary of the conversation using Groq API"""
        if not messages:
            return "No conversation yet."
            
        try:
            conversation_text = "\n".join([
                f"User: {msg.user_message}\n{self.persona_data.get('name', 'AI')}: {msg.ai_response}"
                for msg in messages
            ])
            
            summary_prompt = [
                {
                    "role": "system",
                    "content": "Summarize this conversation between a person and their deceased loved one's AI representation. Focus on the emotional themes and key topics discussed."
                },
                {
                    "role": "user",
                    "content": f"Conversation to summarize:\n{conversation_text}"
                }
            ]
            
            summary = self._call_groq_api(summary_prompt)
            return summary or "Unable to generate summary at this time."
            
        except Exception as e:
            print(f"Error generating summary: {e}")
            return "Unable to generate summary at this time."
