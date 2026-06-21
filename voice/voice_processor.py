import librosa
import numpy as np
import torch
import soundfile as sf
from pydub import AudioSegment
import os
import tempfile
from django.conf import settings

# Import different TTS engines
try:
    from TTS.api import TTS
    COQUI_AVAILABLE = True
except ImportError:
    COQUI_AVAILABLE = False

try:
    import bark
    from bark import SAMPLE_RATE, generate_audio, preload_models
    BARK_AVAILABLE = True
except ImportError:
    BARK_AVAILABLE = False

class VoiceProcessor:
    def __init__(self):
        self.tts_engine = settings.VOICE_CLONE_ENGINE
        self.voice_characteristics = {}
        self.reference_voice_path = None
        
        # Initialize selected TTS engine
        self._initialize_tts_engine()
    
    def _initialize_tts_engine(self):
        """Initialize the selected TTS engine"""
        try:
            if self.tts_engine == "coqui" and COQUI_AVAILABLE:
                self.tts_model = TTS(
                    model_name="tts_models/multilingual/multi-dataset/xtts_v2",
                    progress_bar=False,
                    gpu=torch.cuda.is_available()
                )
                print("Coqui TTS initialized successfully")
                
            elif self.tts_engine == "bark" and BARK_AVAILABLE:
                preload_models()
                print("Bark TTS initialized successfully")
                
            else:
                print(f"TTS engine {self.tts_engine} not available, using fallback")
                self.tts_engine = "fallback"
                
        except Exception as e:
            print(f"Error initializing TTS engine: {e}")
            self.tts_engine = "fallback"
    
    def analyze_voice_sample(self, audio_file_path):
        """Enhanced voice analysis with more features"""
        try:
            # Convert to WAV if necessary
            wav_path = self._ensure_wav_format(audio_file_path)
            
            # Load audio
            y, sr = librosa.load(wav_path, sr=22050)
            
            # Check duration (max 2 minutes)
            duration = len(y) / sr
            if duration > settings.VOICE_SAMPLE_MAX_DURATION:
                print(f"Warning: Voice sample is {duration:.1f}s, truncating to {settings.VOICE_SAMPLE_MAX_DURATION}s")
                y = y[:int(settings.VOICE_SAMPLE_MAX_DURATION * sr)]
            
            # Extract comprehensive voice features
            features = self._extract_voice_features(y, sr)
            
            # Store reference for voice cloning
            self.reference_voice_path = wav_path
            self.voice_characteristics = features
            
            return features
            
        except Exception as e:
            print(f"Error analyzing voice: {e}")
            return None
    
    def _extract_voice_features(self, y, sr):
        """Extract detailed voice characteristics"""
        try:
            # Fundamental frequency (pitch)
            f0 = librosa.yin(y, fmin=50, fmax=400)
            f0_clean = f0[f0 != librosa.yin(y, fmin=50, fmax=400).max()]  # Remove unvoiced frames
            
            # Spectral features
            spectral_centroids = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)[0]
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y)[0]
            
            # MFCCs for voice timbre
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            
            # Rhythm and tempo
            tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
            
            # Voice quality metrics
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)[0]
            rms_energy = librosa.feature.rms(y=y)[0]
            
            features = {
                # Pitch characteristics
                'pitch_mean': float(np.mean(f0_clean)) if len(f0_clean) > 0 else 150.0,
                'pitch_std': float(np.std(f0_clean)) if len(f0_clean) > 0 else 20.0,
                'pitch_range': float(np.ptp(f0_clean)) if len(f0_clean) > 0 else 100.0,
                
                # Spectral characteristics
                'spectral_centroid_mean': float(np.mean(spectral_centroids)),
                'spectral_centroid_std': float(np.std(spectral_centroids)),
                'spectral_rolloff_mean': float(np.mean(spectral_rolloff)),
                'spectral_bandwidth_mean': float(np.mean(spectral_bandwidth)),
                
                # Rhythm and energy
                'tempo': float(tempo),
                'zero_crossing_rate_mean': float(np.mean(zero_crossing_rate)),
                'rms_energy_mean': float(np.mean(rms_energy)),
                
                # Voice timbre (MFCC features)
                'mfcc_means': [float(np.mean(mfcc)) for mfcc in mfccs],
                'mfcc_stds': [float(np.std(mfcc)) for mfcc in mfccs],
                
                # Duration and quality metrics
                'duration': float(len(y) / sr),
                'sample_rate': int(sr),
                'voice_activity_ratio': float(len(f0_clean) / len(f0)) if len(f0) > 0 else 0.5
            }
            
            return features
            
        except Exception as e:
            print(f"Error extracting voice features: {e}")
            return {
                'pitch_mean': 150.0,
                'pitch_std': 20.0,
                'spectral_centroid_mean': 2000.0,
                'tempo': 120.0,
                'duration': 10.0
            }
    
    def clone_voice(self, text, output_path, speaker_wav_path=None):
        """Generate speech using selected voice cloning engine"""
        try:
            reference_path = speaker_wav_path or self.reference_voice_path
            
            if not reference_path or not os.path.exists(reference_path):
                return self._generate_fallback_audio(text, output_path)
            
            if self.tts_engine == "coqui":
                return self._coqui_voice_clone(text, output_path, reference_path)
            elif self.tts_engine == "bark":
                return self._bark_voice_clone(text, output_path, reference_path)
            else:
                return self._generate_fallback_audio(text, output_path)
                
        except Exception as e:
            print(f"Error in voice cloning: {e}")
            return self._generate_fallback_audio(text, output_path)
            
    def generate_speech(self, text, output_path, persona_id=None):
        """Generate speech for chat responses with optional persona voice"""
        try:
            from persona.models import MemorialPersona, DataUpload
            
            # If persona_id is provided, try to find a voice sample
            if persona_id:
                try:
                    # Find a voice sample for this persona
                    voice_upload = DataUpload.objects.filter(
                        persona_id=persona_id,
                        upload_type='voice',
                        status='completed'
                    ).first()
                    
                    if voice_upload and voice_upload.file:
                        return self.clone_voice(text, output_path, voice_upload.file.path)
                except Exception as e:
                    print(f"Error finding persona voice: {e}")
            
            # If no persona or no voice sample found, use fallback TTS
            return self._generate_fallback_audio(text, output_path)
                
        except Exception as e:
            print(f"Error in speech generation: {e}")
            return self._generate_fallback_audio(text, output_path)
    
    def _coqui_voice_clone(self, text, output_path, reference_path):
        """Voice cloning using Coqui TTS"""
        try:
            # Ensure reference is in correct format
            wav_reference = self._ensure_wav_format(reference_path)
            
            # Generate audio with voice cloning
            self.tts_model.tts_to_file(
                text=text,
                speaker_wav=wav_reference,
                file_path=output_path,
                language="en"  # Adjust based on your needs
            )
            
            # Post-process audio to match original characteristics
            self._post_process_audio(output_path)
            
            return True
            
        except Exception as e:
            print(f"Coqui TTS error: {e}")
            return False
    
    def _bark_voice_clone(self, text, output_path, reference_path):
        """Voice cloning using Bark (experimental)"""
        try:
            # Bark uses voice presets, so we'll use a generic one
            # In a production system, you'd need to fine-tune or use voice conversion
            
            # Generate audio
            audio_array = generate_audio(text, history_prompt="v2/en_speaker_9")
            
            # Save to file
            sf.write(output_path, audio_array, SAMPLE_RATE)
            
            return True
            
        except Exception as e:
            print(f"Bark TTS error: {e}")
            return False
    
    def _generate_fallback_audio(self, text, output_path):
        """Generate simple TTS as fallback"""
        try:
            # Create a simple beep or silence as placeholder
            # In production, you might use system TTS or a simple TTS library
            duration = len(text) * 0.1  # Rough estimate
            sample_rate = 22050
            
            # Generate silence (placeholder)
            silence = np.zeros(int(duration * sample_rate))
            sf.write(output_path, silence, sample_rate)
            
            print("Fallback audio generated (silence placeholder)")
            return True
            
        except Exception as e:
            print(f"Fallback audio error: {e}")
            return False
    
    def _ensure_wav_format(self, input_path):
        """Ensure audio file is in WAV format"""
        try:
            # Check if already WAV
            if input_path.lower().endswith('.wav'):
                return input_path
            
            # Convert to WAV
            audio = AudioSegment.from_file(input_path)
            wav_path = input_path.rsplit('.', 1)[0] + '.wav'
            audio.export(wav_path, format='wav')
            
            return wav_path
            
        except Exception as e:
            print(f"Error converting to WAV: {e}")
            return input_path
    
    def _post_process_audio(self, audio_path):
        """Post-process generated audio to match voice characteristics"""
        try:
            if not self.voice_characteristics:
                return
            
            # Load generated audio
            y, sr = librosa.load(audio_path, sr=22050)
            
            # Apply voice characteristics matching
            # This is a simplified version - in production you'd want more sophisticated processing
            
            # Adjust pitch if we have reference characteristics
            target_pitch = self.voice_characteristics.get('pitch_mean', 150)
            current_pitch = np.mean(librosa.yin(y, fmin=50, fmax=400))
            
            if current_pitch > 0 and target_pitch > 0:
                pitch_shift = np.log2(target_pitch / current_pitch) * 12  # Convert to semitones
                if abs(pitch_shift) < 12:  # Only apply reasonable shifts
                    y_shifted = librosa.effects.pitch_shift(y, sr=sr, n_steps=pitch_shift)
                    sf.write(audio_path, y_shifted, sr)
            
        except Exception as e:
            print(f"Error in post-processing: {e}")
    
    def get_voice_similarity_score(self, generated_path, reference_path):
        """Calculate similarity score between generated and reference voice"""
        try:
            # Load both audio files
            y_gen, sr = librosa.load(generated_path, sr=22050)
            y_ref, sr = librosa.load(reference_path, sr=22050)
            
            # Extract features from both
            features_gen = self._extract_voice_features(y_gen, sr)
            features_ref = self._extract_voice_features(y_ref, sr)
            
            # Calculate similarity based on key features
            pitch_similarity = 1 - abs(features_gen['pitch_mean'] - features_ref['pitch_mean']) / 200
            spectral_similarity = 1 - abs(features_gen['spectral_centroid_mean'] - features_ref['spectral_centroid_mean']) / 4000
            tempo_similarity = 1 - abs(features_gen['tempo'] - features_ref['tempo']) / 100
            
            # Weighted average
            similarity_score = (pitch_similarity * 0.4 + spectral_similarity * 0.4 + tempo_similarity * 0.2)
            
            return max(0, min(1, similarity_score))
            
        except Exception as e:
            print(f"Error calculating similarity: {e}")
            return 0.5  # Default neutral score
