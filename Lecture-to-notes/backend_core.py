import os
import io
import tempfile
import json
import logging
from fpdf import FPDF
from datetime import datetime

# --- Gemini API Setup (Generative AI + Transcription) ---
# NOTE: Requires 'google-genai' package and GEMINI_API_KEY environment variable.
try:
    from google import genai
    from google.genai.errors import APIError
    from google.genai import types
    
    client = genai.Client()
    GEMINI_LOADED = True
    GEMINI_MODEL = 'gemini-2.5-flash'
except ImportError:
    logging.error("google-genai not installed. Generative functions disabled.")
    GEMINI_LOADED = False
except Exception as e:
    logging.error(f"Gemini Client failed to load. Ensure GEMINI_API_KEY is set. Error: {e}")
    GEMINI_LOADED = False

# Gemini speech-to-text
def transcribe_audio(audio_file_path, language_code):
    """Transcribes audio using Gemini's speech-to-text API (ffmpeg-free for Streamlit Cloud)."""
    if not GEMINI_LOADED:
        return "Transcription Failed: Gemini API not loaded."

    try:
        import mimetypes
        mime_type, _ = mimetypes.guess_type(audio_file_path)
        if mime_type is None:
            mime_type = "audio/mpeg" 

        # --- Read audio bytes ---
        with open(audio_file_path, "rb") as f:
            audio_bytes = f.read()

        # --- Create audio part ---
        audio_part = types.Part.from_bytes(data=audio_bytes, mime_type=mime_type)

        # --- Generate content using Gemini ---
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                audio_part,
                "Transcribe the provided audio into text accurately."
            ]
        )

        # --- Return clean transcript ---
        if hasattr(response, "text") and response.text.strip():
            return response.text.strip()
        else:
            return "Transcription Failed: No text returned from Gemini."

    except APIError as e:
        return f"Gemini API Error: {e}"
    except Exception as e:
        return f"Error during Gemini transcription: {e}"


# --- Content Generation ---
def generate_content(transcript, content_type, target_lang_code=None): 
    """Generates notes, quizzes, or flashcards in the user's selected language using Gemini."""
    if not GEMINI_LOADED:
        return f"Generative AI Failed: Gemini API not initialized. Please set the GEMINI_API_KEY."

    # Map lang code back to human-readable name for the prompt
    language_names = {
        "en": "English", "ta": "Tamil", "te": "Telugu", "hi": "Hindi",
        "ml": "Malayalam", "kn": "Kannada", "bn": "Bengali", "mr": "Marathi",
        "gu": "Gujarati", "es": "Spanish", "fr": "French", "de": "German"
    }
    target_language = language_names.get(target_lang_code, "English")
    
    schema = None
    
    # --- PROMPT TEMPLATES ---
    if content_type == "Notes":
        prompt = f"""
        You are a note-generation assistant.
        Translate the following transcript into *{target_language}*. Then, summarize the translated text into study notes.
        The *ENTIRE final output, including **all headings, subheadings, and bullet points, must be generated ONLY in **{target_language}*. Do not leave any English words or formatting terms untranslated.
        Use markdown with bold headings (##) and bullet points (-).

        TRANSCRIPT: {transcript}
        """
    
    elif content_type == "Quiz":
        prompt = f"""
        Based on the lecture transcript, translate the content and generate 5 multiple-choice quiz questions.
        The entire output (questions, options, and correct answers) must be in *{target_language}*.
        
        TRANSCRIPT:\n\n{transcript}
        """
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "options": {
                        "type": "object",
                        "properties": {
                            "A": {"type": "string"},
                            "B": {"type": "string"},
                            "C": {"type": "string"}
                        },
                        "required": ["A", "B", "C"]
                    },
                    "correct": {"type": "string", "enum": ["A", "B", "C"]}
                },
                "required": ["question", "options", "correct"]
            }
        }
    
    elif content_type == "Flashcards":
        prompt = f"""
        Translate the lecture transcript into *{target_language}*. Then, extract 10 key terms and their precise definitions.
        The terms and definitions must be entirely in *{target_language}*.
        
        TRANSCRIPT:\n\n{transcript}
        """
        schema = {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "term": {"type": "string"},
                    "definition": {"type": "string"}
                }
            }
        }
    else:
        return "Invalid content type selected."
    
    try:
        config = types.GenerateContentConfig()
        if schema:
            config.response_mime_type = "application/json"
            config.response_schema = schema
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=config
        )
        
        if schema:
            json_text = response.text.strip().replace("``json", "").strip("") 
            return json.loads(json_text)
        
        return response.text
    
    except APIError as e:
        return f"Gemini API Error: Please check your API key and network connection. Error: {e}"
    except json.JSONDecodeError as e:
        return f"JSON Parsing Failed. The AI did not output valid JSON. Raw output: {response.text[:200]}..."
    except Exception as e:
        return f"Error during generation: {e}"


# --- Utility Functions ---
def create_pdf(title, content):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, title, 0, 1, "C")
    pdf.ln(5)
    pdf.set_font("Arial", size=11)
    if not isinstance(content, str):
        content = json.dumps(content, indent=4) 
    pdf.multi_cell(0, 5, content.encode('latin-1', 'replace').decode('latin-1'))
    return pdf.output(dest='S').encode('latin-1')


def save_uploaded_file(uploaded_file):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=uploaded_file.name) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        logging.error(f"Error saving file: {e}")
        return None


# --- HISTORY & FEEDBACK ---
HISTORY_FILE = "lecture_history.json"
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_history(entry):
    history = load_history()
    history.insert(0, entry)
    history = history[:20]
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=4)
    return history

def format_history_entry(audio_name, content_type, notes_content):
    return {
        "audio_name": audio_name,
        "content_type": content_type,
        "notes": notes_content,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

FEEDBACK_FILE = "user_feedback.json"
def save_feedback(data):
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, 'r') as f:
                feedback_list = json.load(f)
        except json.JSONDecodeError:
            feedback_list = []
    else:
        feedback_list = []
        
    feedback_list.append(data)
    with open(FEEDBACK_FILE, 'w') as f:
        json.dump(feedback_list, f, indent=4)
