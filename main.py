"""
AI Chatbot with Voice, Authentication, and Multiple AI Providers
Improved version with environment variables and better error handling
"""

import os
import json
import asyncio
import streamlit as st
import speech_recognition as sr
import pyttsx3
from datetime import datetime
import uuid
from typing import Optional, Dict, Any
from openai import AuthenticationError, RateLimitError
import threading
import queue
import time
import logging


from core.config_manager import ConfigManager

config = ConfigManager()


# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import openai
from openai import OpenAI
import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

from google_cse import GoogleCustomSearch

# Database imports
from supabase import create_client, Client
import hashlib
import bcrypt

# Audio processing
import pygame
from io import BytesIO
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ConfigManager:
    """Manages application configuration and environment variables"""
    
    def __init__(self):
        self.config = {
            # OpenAI
            'OPENAI_API_KEY': os.getenv('OPENAI_API_KEY','@YOUR_OPENAI_API_KEY'),
            
            # Supabase
            'SUPABASE_URL': os.getenv('SUPABASE_URL','@YOUR_SUPABASE_URL'),
            'SUPABASE_KEY': os.getenv('SUPABASE_KEY','@YOUR_SUPABASE_KEY'),
            
            # Google OAuth
            'GOOGLE_CLIENT_ID': os.getenv('GOOGLE_CLIENT_ID','@YOUR_GOOGLE_CLIENT_ID'),
            'GOOGLE_CLIENT_SECRET': os.getenv('GOOGLE_CLIENT_SECRET','@YOUR_GOOGLE_CLIENT_SECRET'),
            
            # Ollama
            'OLLAMA_URL': os.getenv('OLLAMA_URL', 'http://localhost:11434'),
            
            # App settings
            'STREAMLIT_SERVER_PORT': int(os.getenv('STREAMLIT_SERVER_PORT', 8501)),
            'DEFAULT_VOICE_GENDER': os.getenv('DEFAULT_VOICE_GENDER', 'female'),
            'DEFAULT_VOICE_SPEED': int(os.getenv('DEFAULT_VOICE_SPEED', 150)),
            'DEFAULT_EMOTION_LEVEL': int(os.getenv('DEFAULT_EMOTION_LEVEL', 5)),
            'DEBUG': os.getenv('DEBUG', 'False').lower() == 'true'
        }
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def validate_config(self) -> Dict[str, bool]:
        """Validate configuration and return status"""
        validation = {
            'openai_configured': bool(self.config['OPENAI_API_KEY']),
            'supabase_configured': bool(self.config['SUPABASE_URL'] and self.config['SUPABASE_KEY']),
            'google_oauth_configured': bool(self.config['GOOGLE_CLIENT_ID'] and self.config['GOOGLE_CLIENT_SECRET']),
            'ollama_available': self._check_ollama_connection()
        }
        return validation
    
    def _check_ollama_connection(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = requests.get(f"{self.config['OLLAMA_URL']}/api/version", timeout=5)
            return response.status_code == 200
        except:
            return False

class DatabaseManager:
    """Handles all database operations with Supabase"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        
        if not config.get('SUPABASE_URL') or not config.get('SUPABASE_KEY'):
            st.error("❌ Supabase configuration missing! Please set SUPABASE_URL and SUPABASE_KEY in your .env file.")
            st.stop()
        
        try:
            self.client: Client = create_client(
                config.get('SUPABASE_URL'), 
                config.get('SUPABASE_KEY')
            )
            logger.info("Database connection established")
        except Exception as e:
            st.error(f"❌ Database connection failed: {e}")
            st.stop()
    
    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            # Try to query the users table
            result = self.client.table('users').select('id').limit(1).execute()
            return True
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def register_user(self, email: str, username: str, password: str, google_id: str = None) -> Dict[str, Any]:
        """Register a new user"""
        try:
            # Hash password
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
            
            # Insert user
            result = self.client.table('users').insert({
                'email': email,
                'username': username,
                'password_hash': password_hash,
                'google_id': google_id
            }).execute()
            
            if result.data:
                user_id = result.data[0]['id']
                # Create default preferences
                self.client.table('user_preferences').insert({
                    'user_id': user_id,
                    'voice_gender': self.config.get('DEFAULT_VOICE_GENDER'),
                    'voice_speed': self.config.get('DEFAULT_VOICE_SPEED'),
                    'emotion_level': self.config.get('DEFAULT_EMOTION_LEVEL')
                }).execute()
                
                logger.info(f"User registered successfully: {username}")
                return {'success': True, 'user_id': user_id, 'message': 'User registered successfully!'}
            
        except Exception as e:
            logger.error(f"User registration failed: {e}")
            return {'success': False, 'message': f'Registration failed: {str(e)}'}
    
    def authenticate_user(self, username: str, password: str) -> Dict[str, Any]:
        """Authenticate user with username/password"""
        try:
            result = self.client.table('users').select('*').eq('username', username).execute()
            
            if result.data:
                user = result.data[0]
                if bcrypt.checkpw(password.encode('utf-8'), user['password_hash'].encode('utf-8')):
                    # Update last login
                    self.client.table('users').update({
                        'last_login': datetime.now().isoformat()
                    }).eq('id', user['id']).execute()
                    
                    logger.info(f"User authenticated successfully: {username}")
                    return {'success': True, 'user': user}
                
            return {'success': False, 'message': 'Invalid credentials'}
            
        except Exception as e:
            logger.error(f"Authentication failed: {e}")
            return {'success': False, 'message': f'Authentication failed: {str(e)}'}
    
    def save_chat_history(self, user_id: str, message: str, response: str, ai_provider: str):
        """Save chat interaction to database"""
        try:
            self.client.table('chat_history').insert({
                'user_id': user_id,
                'message': message,
                'response': response,
                'ai_provider': ai_provider
            }).execute()
            logger.info("Chat history saved successfully")
        except Exception as e:
            logger.error(f"Failed to save chat history: {e}")
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences"""
        try:
            result = self.client.table('user_preferences').select('*').eq('user_id', user_id).execute()
            if result.data:
                return result.data[0]
            return {}
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
            return {}
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]):
        """Update user preferences"""
        try:
            self.client.table('user_preferences').update(preferences).eq('user_id', user_id).execute()
            logger.info("User preferences updated successfully")
        except Exception as e:
            logger.error(f"Failed to update preferences: {e}")

class AIProvider:
    """Handles different AI providers (OpenAI, Ollama, etc.)"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.openai_client = openai  # store reference for easier access
        
        # Initialize OpenAI
        if config.get('OPENAI_API_KEY'):
            openai.api_key = config.get('OPENAI_API_KEY')
            logger.info("OpenAI configured successfully")
        else:
            logger.warning("OpenAI API key not configured")

        # Initialize Google Custom Search
        self.google_cse = None
        if config.get('GOOGLE_API_KEY') and config.get('GOOGLE_CSE_ID'):
            from google_cse import GoogleCustomSearch
            self.google_cse = GoogleCustomSearch(
                api_key=config.get('GOOGLE_API_KEY'),
                cse_id=config.get('GOOGLE_CSE_ID')
            )
    
    async def get_openai_response(self, message: str, emotion_level: int = 5) -> str:
        """Get response from OpenAI GPT"""
        if not self.config.get('OPENAI_API_KEY'):
            return "❌ OpenAI API key not configured. Please set OPENAI_API_KEY in your .env file."
        
        try:
            # Adjust personality based on emotion level
            emotion_prompt = self._get_emotion_prompt(emotion_level)
            client = OpenAI(api_key=self.config.get('OPENAI_API_KEY'))

            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": f"You are a helpful AI assistant. {emotion_prompt}"},
                    {"role": "user", "content": message}
                ],
                max_tokens=1000,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except AuthenticationError:
            return "❌ OpenAI authentication failed. Please check your API key."
        except RateLimitError:
            return "❌ OpenAI rate limit exceeded. Please try again later."
        except Exception as e:
            logger.error(f"OpenAI error: {e}")
            return f"❌ OpenAI Error: {str(e)}"
    
    async def get_ollama_response(self, message: str, model: str = "llama3") -> str:
        """Get response from Ollama (local AI) with streaming"""
        import requests
        try:
            payload = {
                "model": model,
                "prompt": message,
                "stream": True
            }
            
            response = requests.post(f"{self.config.get('OLLAMA_URL')}/api/generate", json=payload, stream=True, timeout=30)
            
            if response.status_code == 200:
                full_response = ""
                for chunk in response.iter_lines():
                    if chunk:
                        decoded = chunk.decode('utf-8')
                        full_response += decoded
                return full_response
            else:
                return f"❌ Ollama Error: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return "❌ Ollama connection failed. Please ensure Ollama is running."
        except requests.exceptions.Timeout:
            return "❌ Ollama request timed out. Please try again."
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return f"❌ Ollama Error: {str(e)}"
    
    def _get_emotion_prompt(self, emotion_level: int) -> str:
        """Generate emotion-based prompt"""
        emotion_prompts = {
            1: "Respond in a very calm and neutral manner.",
            2: "Respond with slight warmth and friendliness.",
            3: "Respond with moderate enthusiasm and helpfulness.",
            4: "Respond with good energy and engagement.",
            5: "Respond with high enthusiasm, warmth, and emotional connection.",
            6: "Respond with very high energy, excitement, and emotional expressiveness.",
            7: "Respond with maximum enthusiasm, joy, and emotional warmth."
        }
        return emotion_prompts.get(emotion_level, emotion_prompts[5])

class VoiceManager:
    """Handles text-to-speech and speech-to-text"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        
        # Initialize text-to-speech engine
        try:
            self.tts_engine = pyttsx3.init()
            self.setup_voice_properties()
            logger.info("TTS engine initialized successfully")
        except Exception as e:
            logger.error(f"TTS initialization failed: {e}")
            self.tts_engine = None
        
        # Initialize speech recognition
        try:
            self.recognizer = sr.Recognizer()
            self.microphone = sr.Microphone()
            logger.info("Speech recognition initialized successfully")
        except Exception as e:
            logger.error(f"Speech recognition initialization failed: {e}")
            self.recognizer = None
            self.microphone = None
        
        # Voice queue for threading
        self.voice_queue = queue.Queue()
        self.is_speaking = False
    
    def setup_voice_properties(self, gender: str = None, speed: int = None):
        """Setup voice properties"""
        if not self.tts_engine:
            return
        
        gender = gender or self.config.get('DEFAULT_VOICE_GENDER')
        speed = speed or self.config.get('DEFAULT_VOICE_SPEED')
        
        try:
            voices = self.tts_engine.getProperty('voices')
            
            # Set voice based on gender preference
            for voice in voices:
                if gender.lower() in voice.name.lower():
                    self.tts_engine.setProperty('voice', voice.id)
                    break
            
            # Set speech rate
            self.tts_engine.setProperty('rate', speed)
            
            # Set volume
            self.tts_engine.setProperty('volume', 0.8)
            
        except Exception as e:
            logger.error(f"Voice setup failed: {e}")
    
    def speak_text(self, text: str, emotion_level: int = 5):
        """Convert text to speech with emotion"""
        if not self.tts_engine:
            st.warning("🔇 Text-to-speech not available")
            return
        
        try:
            # Add emotional inflections based on level
            processed_text = self._add_emotional_inflections(text, emotion_level)
            
            # Speak in a separate thread to avoid blocking
            def speak():
                self.is_speaking = True
                self.tts_engine.say(processed_text)
                self.tts_engine.runAndWait()
                self.is_speaking = False
            
            thread = threading.Thread(target=speak)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Speech error: {e}")
    
    def _add_emotional_inflections(self, text: str, emotion_level: int) -> str:
        """Add emotional inflections to text"""
        if emotion_level >= 6:
            # Add excitement markers
            text = text.replace('.', '!')
            text = text.replace('?', '?!')
        elif emotion_level >= 4:
            # Add mild enthusiasm
            text = text.replace('.', '. ')
        
        return text
    
    def listen_for_speech(self, timeout: int = 5) -> str:
        """Convert speech to text"""
        if not self.recognizer or not self.microphone:
            return "❌ Speech recognition not available"
        
        try:
            with self.microphone as source:
                # Adjust for ambient noise
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                
                # Listen for audio
                audio = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=10)
                
                # Convert to text
                text = self.recognizer.recognize_google(audio)
                return text
                
        except sr.WaitTimeoutError:
            return "⏱️ Timeout: No speech detected"
        except sr.UnknownValueError:
            return "❓ Could not understand the speech"
        except sr.RequestError as e:
            return f"❌ Speech recognition error: {e}"
        except Exception as e:
            logger.error(f"Speech recognition error: {e}")
            return f"❌ Speech error: {e}"

class GoogleAuthManager:
    """Handles Google OAuth authentication"""
    
    def __init__(self, config: ConfigManager):
        self.config = config
        self.redirect_uri = f"http://localhost:{config.get('STREAMLIT_SERVER_PORT')}"
        self.scopes = [
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile'
        ]
    
    def is_configured(self) -> bool:
        """Check if Google OAuth is configured"""
        return bool(self.config.get('GOOGLE_CLIENT_ID') and self.config.get('GOOGLE_CLIENT_SECRET'))
    
    def get_google_auth_url(self) -> str:
        """Generate Google OAuth URL"""
        if not self.is_configured():
            return ""
        
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.config.get('GOOGLE_CLIENT_ID'),
                        "client_secret": self.config.get('GOOGLE_CLIENT_SECRET'),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            flow.redirect_uri = self.redirect_uri
            
            auth_url, state = flow.authorization_url(prompt='consent')
            st.session_state['oauth_state'] = state
            
            return auth_url
            
        except Exception as e:
            logger.error(f"Google Auth URL error: {e}")
            return ""
    
    def handle_google_callback(self, code: str) -> Dict[str, Any]:
        """Handle Google OAuth callback"""
        if not self.is_configured():
            return {'success': False, 'message': 'Google OAuth not configured'}
        
        try:
            flow = Flow.from_client_config(
                {
                    "web": {
                        "client_id": self.config.get('GOOGLE_CLIENT_ID'),
                        "client_secret": self.config.get('GOOGLE_CLIENT_SECRET'),
                        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                        "token_uri": "https://oauth2.googleapis.com/token",
                        "redirect_uris": [self.redirect_uri]
                    }
                },
                scopes=self.scopes
            )
            flow.redirect_uri = self.redirect_uri
            
            # Exchange code for token
            flow.fetch_token(code=code)
            
            # Get user info
            credentials = flow.credentials
            service = build('oauth2', 'v2', credentials=credentials)
            user_info = service.userinfo().get().execute()
            
            return {
                'success': True,
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'google_id': user_info.get('id'),
                'picture': user_info.get('picture')
            }
            
        except Exception as e:
            logger.error(f"Google OAuth callback error: {e}")
            return {'success': False, 'message': f'OAuth callback failed: {str(e)}'}

class ChatApplication:
    """Main chat application class"""
    
    def __init__(self):
        self.config = ConfigManager()
        self.db = DatabaseManager(self.config)
        self.ai_provider = AIProvider(self.config)
        self.voice_manager = VoiceManager(self.config)
        self.google_auth = GoogleAuthManager(self.config)
        
        # Initialize session state
        self.init_session_state()
    
    def init_session_state(self):
        """Initialize Streamlit session state"""
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user' not in st.session_state:
            st.session_state.user = None
        if 'chat_history' not in st.session_state:
            st.session_state.chat_history = []
        if 'voice_enabled' not in st.session_state:
            st.session_state.voice_enabled = False
    
    def run(self):
        """Main application runner"""
        st.set_page_config(
            page_title="AI Voice Chatbot",
            page_icon="🤖",
            layout="wide",
            initial_sidebar_state="expanded"
        )
        
        # Show configuration status
        self.show_config_status()
        
        # Handle authentication
        if not st.session_state.authenticated:
            self.show_auth_interface()
        else:
            self.show_chat_interface()
    
    def show_config_status(self):
        """Show configuration status"""
        config_status = self.config.validate_config()
        
        with st.sidebar:
            st.subheader("🔧 Configuration Status")
            
            status_indicators = {
                'openai_configured': '🤖 OpenAI',
                'supabase_configured': '🗄️ Supabase',
                'google_oauth_configured': '🔐 Google OAuth',
                'ollama_available': '🦙 Ollama'
            }
            
            for key, label in status_indicators.items():
                if config_status.get(key):
                    st.success(f"{label} ✅")
                else:
                    st.error(f"{label} ❌")
    
    def show_auth_interface(self):
        """Show authentication interface"""
        st.title("🤖 AI Voice Chatbot")
        st.markdown("### Welcome! Please sign in to continue.")
        
        # Authentication tabs
        auth_tab1, auth_tab2, auth_tab3 = st.tabs(["Sign In", "Sign Up", "Google OAuth"])
        
        with auth_tab1:
            self.show_login_form()
        
        with auth_tab2:
            self.show_register_form()
        
        with auth_tab3:
            self.show_google_auth()
    
    def show_login_form(self):
        """Show login form"""
        st.subheader("🔐 Sign In")
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Sign In")
            
            if submit and username and password:
                result = self.db.authenticate_user(username, password)
                
                if result['success']:
                    st.session_state.authenticated = True
                    st.session_state.user = result['user']
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error(f"❌ {result['message']}")
    
    def show_register_form(self):
        """Show registration form"""
        st.subheader("📝 Create Account")
        
        with st.form("register_form"):
            email = st.text_input("Email")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            submit = st.form_submit_button("Create Account")
            
            if submit:
                if not all([email, username, password, confirm_password]):
                    st.error("❌ Please fill in all fields")
                elif password != confirm_password:
                    st.error("❌ Passwords do not match")
                else:
                    result = self.db.register_user(email, username, password)
                    
                    if result['success']:
                        st.success("✅ Account created successfully! Please sign in.")
                    else:
                        st.error(f"❌ {result['message']}")
    
    def show_google_auth(self):
        """Show Google OAuth"""
        st.subheader("🔐 Google OAuth")
        
        if not self.google_auth.is_configured():
            st.warning("⚠️ Google OAuth is not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file.")
            return
        
        # Handle OAuth callback
        query_params = st.experimental_get_query_params()
        if 'code' in query_params:
            code = query_params['code'][0]
            result = self.google_auth.handle_google_callback(code)
            
            if result['success']:
                # Try to find existing user or create new one
                user_result = self.db.authenticate_user(result['email'], '')
                
                if not user_result['success']:
                    # Create new user
                    register_result = self.db.register_user(
                        result['email'], 
                        result['email'], 
                        str(uuid.uuid4()),  # Random password for OAuth users
                        result['google_id']
                    )
                    
                    if register_result['success']:
                        st.session_state.authenticated = True
                        st.session_state.user = {
                            'id': register_result['user_id'],
                            'email': result['email'],
                            'username': result['email']
                        }
                        st.success("✅ Account created and logged in successfully!")
                    else:
                        st.error(f"❌ {register_result['message']}")
                else:
                    st.session_state.authenticated = True
                    st.session_state.user = user_result['user']
                    st.success("✅ Logged in successfully!")
                
                # Clear query params
                st.experimental_set_query_params()
                st.rerun()
            else:
                st.error(f"❌ {result['message']}")
        
        # Show Google OAuth button
        auth_url = self.google_auth.get_google_auth_url()
        if auth_url:
            st.markdown(f"[🔐 Sign in with Google]({auth_url})")
    
    def show_chat_interface(self):
        """Show main chat interface"""
        st.title("🤖 AI Voice Chatbot")
        
        # Sidebar with user info and settings
        with st.sidebar:
            self.show_user_sidebar()
        
        # Main chat area
        self.show_chat_area()
    
    def show_user_sidebar(self):
        """Show user sidebar with settings"""
        st.subheader(f"👋 Welcome, {st.session_state.user['username']}")
        
        # Logout button
        if st.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.user = None
            st.session_state.chat_history = []
            st.rerun()
        
        st.divider()
        
        # Voice settings
        st.subheader("🎙️ Voice Settings")
        
        voice_enabled = st.checkbox("Enable Voice", value=st.session_state.voice_enabled)
        st.session_state.voice_enabled = voice_enabled
        
        if voice_enabled:
            # Get user preferences
            prefs = self.db.get_user_preferences(st.session_state.user['id'])
            
            voice_gender = st.selectbox(
                "Voice Gender",
                ["female", "male"],
                index=0 if prefs.get('voice_gender', 'female') == 'female' else 1
            )
            
            voice_speed = st.slider(
                "Speech Speed",
                min_value=50,
                max_value=300,
                value=prefs.get('voice_speed', 150)
            )
            
            emotion_level = st.slider(
                "Emotion Level",
                min_value=1,
                max_value=7,
                value=prefs.get('emotion_level', 5)
            )
            
            # Update voice settings
            self.voice_manager.setup_voice_properties(voice_gender, voice_speed)
            
            # Save preferences button
            if st.button("💾 Save Voice Settings"):
                self.db.update_user_preferences(st.session_state.user['id'], {
                    'voice_gender': voice_gender,
                    'voice_speed': voice_speed,
                    'emotion_level': emotion_level
                })
                st.success("✅ Settings saved!")
        
        st.divider()
        
        # AI Provider selection
        st.subheader("🤖 AI Provider")
        
        available_providers = []
        if self.config.get('OPENAI_API_KEY'):
            available_providers.append("OpenAI GPT")
        if self.config.validate_config()['ollama_available']:
            available_providers.append("Ollama")
        
        if available_providers:
            ai_provider = st.selectbox("Select AI Provider", available_providers)
            st.session_state.selected_ai_provider = ai_provider
        else:
            st.error("❌ No AI providers configured!")
        
        st.divider()
        
        # Clear chat history
        if st.button("🗑️ Clear Chat History"):
            st.session_state.chat_history = []
            st.success("✅ Chat history cleared!")
    
    def show_chat_area(self):
        """Show main chat area"""
        # Display chat history
        chat_container = st.container()
        
        with chat_container:
            for i, (user_msg, ai_msg, timestamp) in enumerate(st.session_state.chat_history):
                # User message
                st.markdown(f"""
                <div style="text-align: right; margin: 10px 0;">
                    <div style="background-color: #007ACC; color: white; padding: 10px; border-radius: 10px; display: inline-block; max-width: 70%;">
                        {user_msg}
                    </div>
                    <div style="font-size: 0.8em; color: #666; margin-top: 5px;">
                        {timestamp}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # AI message
                st.markdown(f"""
                <div style="text-align: left; margin: 10px 0;">
                    <div style="background-color: #f0f0f0; color: black; padding: 10px; border-radius: 10px; display: inline-block; max-width: 70%;">
                        {ai_msg}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Input area
        st.divider()
        
        # Voice input section
        if st.session_state.voice_enabled:
            col1, col2 = st.columns([1, 4])
            
            with col1:
                if st.button("🎤 Record"):
                    with st.spinner("🎙️ Listening..."):
                        voice_input = self.voice_manager.listen_for_speech()
                        if not voice_input.startswith("❌") and not voice_input.startswith("⏱️") and not voice_input.startswith("❓"):
                            st.session_state.current_input = voice_input
                            st.success(f"🎤 Recorded: {voice_input}")
                        else:
                            st.error(voice_input)
            
            with col2:
                user_input = st.text_input(
                    "Type your message or use voice input:",
                    value=st.session_state.get('current_input', ''),
                    key="chat_input"
                )
        else:
            user_input = st.text_input("Type your message:", key="chat_input")
        
        # Send button
        col1, col2, col3 = st.columns([1, 1, 3])
        
        with col1:
            send_clicked = st.button("📤 Send", type="primary")
        
        with col2:
            if st.session_state.voice_enabled:
                speak_response = st.checkbox("🔊 Speak Response", value=True)
            else:
                speak_response = False
        
        # Process message
        if send_clicked and user_input.strip():
            self.process_message(user_input.strip(), speak_response)
            # Clear input
            st.session_state.current_input = ""
            st.rerun()
    
    def process_message(self, message: str, speak_response: bool = False):
        """Process user message and get AI response"""
        try:
            # Get user preferences for emotion level
            prefs = self.db.get_user_preferences(st.session_state.user['id'])
            emotion_level = prefs.get('emotion_level', 5)
            
            # Use only OpenAI provider without fallback testing
            response = None
            provider_used = None
            
            with st.spinner("🤔 OpenAI GPT is thinking..."):
                try:
                    response = asyncio.run(self.ai_provider.get_openai_response(message, emotion_level))
                    if response and not response.startswith("❌"):
                        provider_used = "OpenAI GPT"
                except Exception as e:
                    logger.error(f"OpenAI error: {e}")
                    response = "❌ OpenAI error occurred."
            
            # Add to chat history
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            st.session_state.chat_history.append((message, response, timestamp))
            
            # Save to database
            self.db.save_chat_history(
                st.session_state.user['id'],
                message,
                response,
                provider_used or "Unknown"
            )
            
            # Speak response if enabled
            if speak_response and st.session_state.voice_enabled:
                self.voice_manager.speak_text(response, emotion_level)
            
            # Show success message
            st.success("✅ Message sent!")
            
        except Exception as e:
            logger.error(f"Message processing error: {e}")
            st.error(f"❌ Error processing message: {str(e)}")

def create_database_schema():
    """Create database schema for Supabase"""
    schema_sql = """
    -- Users table
    CREATE TABLE IF NOT EXISTS users (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        email VARCHAR(255) UNIQUE NOT NULL,
        username VARCHAR(100) UNIQUE NOT NULL,
        password_hash VARCHAR(255),
        google_id VARCHAR(255),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_login TIMESTAMP WITH TIME ZONE,
        is_active BOOLEAN DEFAULT TRUE
    );

    -- User preferences table
    CREATE TABLE IF NOT EXISTS user_preferences (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id UUID REFERENCES users(id) ON DELETE CASCADE,
        voice_gender VARCHAR(10) DEFAULT 'female',
        voice_speed INTEGER DEFAULT 150,
        emotion_level INTEGER DEFAULT 5,
        theme VARCHAR(20) DEFAULT 'light',
        language VARCHAR(10) DEFAULT 'en',
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
    );

    -- Chat history table
    CREATE TABLE IF NOT EXISTS chat_history (
        id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
        user_id UUID REFERENCES users(id) ON DELETE CASCADE,
        message TEXT NOT NULL,
        response TEXT NOT NULL,
        ai_provider VARCHAR(50) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        metadata JSONB
    );

    -- Indexes for better performance
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
    CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);
    CREATE INDEX IF NOT EXISTS idx_chat_history_user_id ON chat_history(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);
    """
    
    return schema_sql

def create_env_template():
    """Create environment template file"""
    env_template = """
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Supabase Database Configuration
SUPABASE_URL=your_supabase_url_here
SUPABASE_KEY=your_supabase_anon_key_here

# Google OAuth Configuration (Optional)
GOOGLE_CLIENT_ID=your_google_client_id_here
GOOGLE_CLIENT_SECRET=your_google_client_secret_here

# Ollama Configuration (Optional - for local AI)
OLLAMA_URL=http://localhost:11434

# Application Settings
STREAMLIT_SERVER_PORT=8501
DEFAULT_VOICE_GENDER=female
DEFAULT_VOICE_SPEED=150
DEFAULT_EMOTION_LEVEL=5
DEBUG=False
"""
    
    return env_template

def main():
    """Main function to run the application"""
    try:
        # Initialize and run the chat application
        app = ChatApplication()
        app.run()
        
    except Exception as e:
        st.error(f"❌ Application Error: {str(e)}")
        logger.error(f"Application error: {e}")
        
        # Show setup instructions
        st.markdown("""
        ## 🔧 Setup Instructions
        
        1. **Install Dependencies**:
        ```bash
        pip install streamlit openai python-dotenv supabase bcrypt
        pip install speechrecognition pyttsx3 pygame google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client
        ```
        
        2. **Create `.env` file** with your configuration:
        ```
        OPENAI_API_KEY=your_openai_api_key
        SUPABASE_URL=your_supabase_url
        SUPABASE_KEY=your_supabase_key
        ```
        
        3. **Set up Supabase Database** with the provided schema.
        
        4. **Run the application**:
        ```bash
        streamlit run app.py
        ```
        """)

if __name__ == "__main__":
    main()


