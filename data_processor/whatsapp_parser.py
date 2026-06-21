import re
import pandas as pd
from datetime import datetime
from collections import defaultdict

class WhatsAppParser:
    def __init__(self, file_path):
        self.file_path = file_path
        self.messages = []
        
    # Ordered list of patterns covering the most common WhatsApp export formats.
    # Each pattern captures (date, time, sender, message).
    _PATTERNS = [
        # Android – AM/PM with optional seconds:  1/1/23, 10:30 AM - Sender: msg
        r'(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*[AaPp][Mm])\s*[-\u2013]\s*([^:]+):\s*(.+)',
        # Android – 24-hour with optional seconds: 1/1/23, 10:30 - Sender: msg
        r'(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?)\s*[-\u2013]\s*([^:]+):\s*(.+)',
        # iOS – brackets, AM/PM, optional seconds: [1/1/23, 10:30:00 AM] Sender: msg
        r'\[(\d{1,2}/\d{1,2}/\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?\s*[AaPp][Mm]?)\]\s*([^:]+):\s*(.+)',
        # ISO date: 2023-01-01, 10:30 - Sender: msg
        r'(\d{4}-\d{2}-\d{2}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\s*[-\u2013]\s*([^:]+):\s*(.+)',
        # Dot-separated (European): 01.01.2023, 10:30 - Sender: msg
        r'(\d{1,2}\.\d{1,2}\.\d{2,4}),\s*(\d{1,2}:\d{2}(?::\d{2})?(?:\s*[AaPp][Mm])?)\s*[-\u2013]\s*([^:]+):\s*(.+)',
    ]

    def parse_chat(self):
        """Parse WhatsApp chat export file.

        Tries several patterns to handle the many date/time formats that
        WhatsApp uses across platforms and locales.  Also strips Unicode
        direction/width markers that WhatsApp embeds in exported files.
        """
        try:
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(self.file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

        # Remove invisible Unicode markers WhatsApp injects
        for char in ('\u200e', '\u200f', '\u202a', '\u202c', '\u200b', '\ufeff'):
            content = content.replace(char, '')
        # Narrow no-break space (U+202F) → regular space so patterns match
        content = content.replace('\u202f', ' ')

        # Try each pattern; use the first one that yields results
        for pattern in self._PATTERNS:
            matches = re.findall(pattern, content)
            if matches:
                self.messages = []
                for date, time, sender, message in matches:
                    self.messages.append({
                        'date':    date.strip(),
                        'time':    time.strip(),
                        'sender':  sender.strip(),
                        'message': message.strip(),
                    })
                print(f"WhatsApp parser matched {len(self.messages)} messages "
                      f"with pattern: {pattern[:60]}")
                return self.messages

        print("WhatsApp parser: no pattern matched — check export format")
        return self.messages
    
    def analyze_persona(self, target_person):
        """Analyze communication patterns of target person"""
        persona_messages = [msg for msg in self.messages if msg['sender'] == target_person]
        
        analysis = {
            'total_messages': len(persona_messages),
            'avg_message_length': sum(len(msg['message']) for msg in persona_messages) / len(persona_messages) if persona_messages else 0,
            'common_words': self._get_common_words(persona_messages),
            'communication_patterns': self._analyze_patterns(persona_messages),
            'emotional_tone': self._analyze_tone(persona_messages)
        }
        
        return analysis
    
    def _get_common_words(self, messages):
        """Extract common words and phrases"""
        all_text = ' '.join([msg['message'] for msg in messages]).lower()
        words = re.findall(r'\b\w+\b', all_text)
        
        word_freq = defaultdict(int)
        for word in words:
            if len(word) > 2:  # Skip short words
                word_freq[word] += 1
        
        return dict(sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[:50])
    
    def _analyze_patterns(self, messages):
        """Analyze communication patterns"""
        patterns = {
            'question_frequency': sum(1 for msg in messages if '?' in msg['message']) / len(messages) if messages else 0,
            'exclamation_frequency': sum(1 for msg in messages if '!' in msg['message']) / len(messages) if messages else 0,
            'emoji_usage': sum(1 for msg in messages if any(ord(char) > 127 for char in msg['message'])) / len(messages) if messages else 0
        }
        return patterns
    
    def _analyze_tone(self, messages):
        """Basic sentiment analysis"""
        positive_words = ['good', 'great', 'happy', 'love', 'excellent', 'wonderful', 'amazing']
        negative_words = ['bad', 'sad', 'angry', 'hate', 'terrible', 'awful', 'horrible']
        
        positive_count = 0
        negative_count = 0
        
        for msg in messages:
            text = msg['message'].lower()
            positive_count += sum(1 for word in positive_words if word in text)
            negative_count += sum(1 for word in negative_words if word in text)
        
        total_sentiment = positive_count + negative_count
        if total_sentiment > 0:
            return {
                'positive_ratio': positive_count / total_sentiment,
                'negative_ratio': negative_count / total_sentiment
            }
        return {'positive_ratio': 0.5, 'negative_ratio': 0.5}
