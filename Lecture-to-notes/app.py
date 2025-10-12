import os
from dotenv import load_dotenv

# --- API Key Setup: Reads Key from .env File ---
load_dotenv() # Load variables from .env file into os.environ
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    # Display error message on the screen if the key is missing from the environment
    st.error("❌ Gemini API key not found. Please set GEMINI_API_KEY in your local *.env* file and ensure the python-dotenv library is installed.")
    # Exit early since we cannot proceed without the AI model
    st.stop()
# The key is now loaded into os.environ for backend_core to access.

import streamlit as st
import backend_core as core
import tempfile
import json
import time
from datetime import datetime


# --- CUSTOM UI STYLING ---
def load_css():
    st.markdown("""
        <style>
        /* Main page styling */
        .stApp {
            background-color: #1a1a2e;
            color: #ffffff;
        }
        /* Header and Title */
        h1 {
            color: #ffcc00; /* Gold */
            text-shadow: 2px 2px 4px #000000;
        }
        h2, h3 {
            color: #90a0ff; /* Light Blue/Purple */
        }
        /* Primary Button Style (Red/Orange Tone for Action) */
        .stButton>button {
            background-color: #ff4b4b; /* Streamlit Red */
            color: white;
            border-radius: 8px;
            font-weight: bold;
            padding: 10px 20px;
            transition: 0.3s;
        }
        .stButton>button:hover {
            background-color: #ff6e6e;
            box-shadow: 0 4px 8px rgba(0, 0, 0, 0.4);
        }
        /* Sidebar/History Style */
        .sidebar .sidebar-content {
            background-color: #2a2a4a;
        }
        /* Expander/Info Box Styling */
        .streamlit-expanderHeader {
            background-color: #3b3b6b;
            color: #fff;
            border-radius: 5px;
            padding: 10px;
        }
        </style>
    """, unsafe_allow_html=True)

load_css()
# --- END CUSTOM UI STYLING ---


# --- SESSION STATE---
if 'history' not in st.session_state:
    st.session_state.history = core.load_history()
if 'current_transcript' not in st.session_state:
    st.session_state.current_transcript = None
if 'current_audio_name' not in st.session_state:
    st.session_state.current_audio_name = None
if 'saved_notes' not in st.session_state:
    st.session_state.saved_notes = None
if 'saved_quiz' not in st.session_state:
    st.session_state.saved_quiz = None
if 'saved_flashcards' not in st.session_state:
    st.session_state.saved_flashcards = None
if 'output_type' not in st.session_state:
    st.session_state.output_type = "Notes"
if 'notes_generated' not in st.session_state:
    st.session_state.notes_generated = False


# --- SHARE FUNCTION ---
def share_content(notes, audio_name):
    shareable_notes = json.dumps(notes, indent=2) if isinstance(notes, (list, dict)) else notes
    share_text = f"📝 Check out my notes for the lecture '{audio_name}'!\n\n---\n\n{shareable_notes}"
    st.code(share_text, language='text')
    st.success("Notes copied above — in production this would be shareable via a link!")


# --- NEW: Helper function to format structured JSON data into readable text ---

def format_structured_output(data, output_type):
    """Converts quiz/flashcard JSON data into a clean, human-readable string for downloads."""
    text = f"--- {output_type.upper()} OUTPUT ---\n"
    
    if output_type == "Quiz" and isinstance(data, list):
        for i, q in enumerate(data):
            text += f"\nQ{i+1}: {q.get('question', 'Question Missing')}\n"
            options = q.get('options', {})
            for key, val in options.items():
                text += f"  {key}. {val}\n"
            text += f"Correct Answer: {q.get('correct', 'N/A')}\n"
            text += "-" * 20 + "\n"
    
    elif output_type == "Flashcards" and isinstance(data, list):
        for f in data:
            term = f.get('term', 'Term Missing')
            definition = f.get('definition', 'Definition Missing')
            text += f"TERM: {term}\nDEFINITION: {definition}\n"
            text += "-" * 20 + "\n"
    
    else:
        # Fallback for Notes (which are already strings) or poorly formatted data
        text = str(data)

    return text


# --- MAIN UI ---
st.title("🗣 Lecture Voice-to-Notes Generator")
st.markdown("---")

with st.container(border=True):
    st.subheader("⚙ Lecture Processor")
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        st.caption("Step 1: Upload & Select Language")
        uploaded_file = st.file_uploader(
            "Upload Audio File",
            type=["mp3", "wav", "m4a", "ogg"],
            key="file_uploader"
        )

        languages = {
            "English": "en",
            "Tamil": "ta",
            "Telugu": "te",
            "Hindi": "hi",
            "Malayalam": "ml",
            "Kannada": "kn",
            "Bengali": "bn",
            "Marathi": "mr",
            "Gujarati": "gu",
            "Spanish": "es",
            "French": "fr",
            "German": "de",
        }
        lang_name = st.selectbox("Language", list(languages.keys()), key="lang_select")
        lang_code = languages[lang_name]

        # Output type radio
        st.session_state.next_output_type = st.radio(
            "Select Output Type for Step 3:",
            ("Quiz", "Flashcards"),
            horizontal=True,
            index=None,
            key="type_selector"
        )

    with col2:
        st.caption("Step 2: Get Base Notes")
        st.markdown("Generate transcript and base notes.")
        if st.button("🎤 Transcribe & Save Notes", type="primary", use_container_width=True):
            if uploaded_file:
                # --- CLEAR QUIZ/FLASHCARD DATA ON NEW NOTES GENERATION ---
                st.session_state.saved_quiz = None
                st.session_state.saved_flashcards = None
                
                with st.spinner("Step 1/2: Transcribing audio..."):
                    audio_path = core.save_uploaded_file(uploaded_file)
                    try:
                        transcript = core.transcribe_audio(audio_path, None)
                        st.session_state.current_transcript = transcript
                        st.session_state.current_audio_name = uploaded_file.name

                        with st.spinner(f"Step 2/2: Translating & Generating Notes in {lang_name}..."):
                            generated_notes = core.generate_content(transcript, "Notes", lang_code)

                        st.session_state.saved_notes = generated_notes
                        st.session_state.output_type = "Notes"
                        st.session_state.notes_generated = True

                        history_entry = core.format_history_entry(uploaded_file.name, "Notes", generated_notes)
                        st.session_state.history = core.save_history(history_entry)

                        st.success("✅ Notes Generated! Now generate Quizzes/Flashcards.")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                    finally:
                        os.unlink(audio_path)
            else:
                st.warning("Please upload an audio file first.")

    with col3:
        st.caption("Step 3: Generate Study Tools")
        st.markdown(f"Generate {st.session_state.next_output_type or 'Quiz/Flashcards'} from Notes.")

        if st.session_state.notes_generated and st.session_state.current_transcript:
            output_to_generate = st.session_state.next_output_type
            if output_to_generate:
                if st.button(f"Generate {output_to_generate}", use_container_width=True, type="secondary"):
                    with st.spinner(f"Generating {output_to_generate}..."):
                        gen_content = core.generate_content(
                            st.session_state.current_transcript,
                            output_to_generate,
                            lang_code
                        )
                        st.session_state.output_type = output_to_generate
                        
                        if output_to_generate == "Quiz":
                            st.session_state.saved_quiz = gen_content
                        elif output_to_generate == "Flashcards":
                            st.session_state.saved_flashcards = gen_content

                        history_entry = core.format_history_entry(
                            st.session_state.current_audio_name, output_to_generate, gen_content
                        )
                        st.session_state.history = core.save_history(history_entry)

                        st.success(f"{output_to_generate} Generated!")
                        st.rerun()
            else:
                st.info("Select an output type (Quiz/Flashcards) first.")
        else:
            st.info("Generate notes before proceeding.")

st.markdown("---")

# --- OUTPUT DISPLAY SECTION ---
st.header("✨ Generated Output & Actions")

if not st.session_state.saved_notes:
    st.info("Upload an audio file and click 'Transcribe & Save Notes' to begin.")
else:
    tabs = st.tabs(["Notes", "Quiz", "Flashcards"])

    # --- HELPER: Function to create download buttons in tabs (Defined outside but logic used here) ---
    def create_download_buttons(content_data, content_type):
        if content_data:
            # 1. Format content for download (as required)
            if isinstance(content_data, (list, dict)):
                downloadable_content = format_structured_output(content_data, content_type)
            else:
                downloadable_content = content_data
            
            d_col1, d_col2, d_col3 = st.columns(3)

            with d_col1:
                st.download_button(
                    label="Text (.txt)", data=downloadable_content,
                    file_name=f"{st.session_state.current_audio_name}_{content_type}_output.txt",
                    mime="text/plain", use_container_width=True
                )
            with d_col2:
                pdf_title = f"{st.session_state.current_audio_name} - {content_type}"
                pdf_bytes = core.create_pdf(pdf_title, downloadable_content) 
                st.download_button(
                    label="PDF (.pdf)", data=pdf_bytes,
                    file_name=f"{st.session_state.current_audio_name}_{content_type}_output.pdf",
                    mime="application/pdf", use_container_width=True
                )
            with d_col3:
                if st.button("🔗 Share", key=f"share_{content_type}_btn", use_container_width=True):
                    share_content(downloadable_content, st.session_state.current_audio_name)
        else:
            st.info(f"No {content_type} generated yet.")

    # NOTES TAB
    with tabs[0]:
        st.subheader("📚 Study Notes")
        if st.session_state.saved_notes:
            st.markdown(st.session_state.saved_notes)
            with st.expander("View Transcript", expanded=False):
                st.code(st.session_state.current_transcript or "Transcript not available.", language='text')
            
            st.markdown("---")
            st.subheader("⬇ Download & Share")
            create_download_buttons(st.session_state.saved_notes, "Notes")
        else:
            st.info("No Notes available yet.")

    # QUIZ TAB
    with tabs[1]:
        st.subheader("📝 Interactive Quiz")
        quiz_data = st.session_state.saved_quiz
        if quiz_data:
            if isinstance(quiz_data, list) and all('options' in q for q in quiz_data):
                for i, q in enumerate(quiz_data):
                    st.markdown(f"*Q{i+1}: {q['question']}*")
                    user_answer = st.radio(
                        f"Your answer for Q{i+1}",
                        list(q['options'].keys()),
                        format_func=lambda k: f"{k}: {q['options'][k]}",
                        index=None,
                        key=f"quiz_{i}"
                    )
                    if st.button(f"Check Q{i+1}", key=f"check_{i}", type="secondary"):
                        if user_answer == q["correct"]:
                            st.success("✅ Correct!")
                        else:
                            st.error(f"❌ Incorrect! Correct answer: {q['correct']}")
                    st.markdown("---")
            else:
                st.error("⚠ Quiz Parsing Failed.")
                st.info("The AI model failed to return structured JSON. Displaying raw output for debug:")
                with st.expander("Raw AI Output (Debug)", expanded=False):
                    st.code(str(quiz_data), language='text')
            
            st.markdown("---")
            st.subheader("⬇ Download & Share")
            create_download_buttons(st.session_state.saved_quiz, "Quiz")
        else:
            st.info("Generate a quiz to view content.")

    # FLASHCARDS TAB
    with tabs[2]:
        st.subheader("🃏 AI Flashcards")
        flashcards = st.session_state.saved_flashcards
        if flashcards:
            if isinstance(flashcards, list):
                for f in flashcards:
                    with st.expander(f"💡 {f.get('term', 'Term')}"):
                        st.write(f"*Definition:* {f.get('definition', 'No definition')}")
            else:
                st.error("⚠ Flashcard Parsing Failed.")
                st.info("The AI model failed to return structured JSON. Displaying raw output for debug:")
                with st.expander("Raw AI Output (Debug)", expanded=False):
                    st.code(str(flashcards), language='text')
            
            st.markdown("---")
            st.subheader("⬇ Download & Share")
            create_download_buttons(st.session_state.saved_flashcards, "Flashcards")
        else:
            st.info("Generate flashcards to view content.")

    st.markdown("---")

    # FEEDBACK SECTION (Moved to its own container)
    with st.container(border=True):
        st.subheader("⭐ User Feedback")
        # --- Feedback Form ---
        with st.form("feedback_form", clear_on_submit=True):
            rating = st.select_slider("Rate Output Quality:", [1, 2, 3, 4, 5], value=5)
            comments = st.text_area("Comments:")
            submit = st.form_submit_button("Submit Feedback")
            if submit:
                feedback_data = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "audio": st.session_state.get('current_audio_name', 'N/A'),
                    "output_type": st.session_state.get('output_type', 'N/A'),
                    "rating": rating,
                    "comments": comments
                }
                core.save_feedback(feedback_data)
                st.success("✅ Thank you for your valuable feedback! 🚀")

# --- SIDEBAR HISTORY ---
st.sidebar.header("⏳ History")
st.sidebar.markdown("---")

if st.session_state.history:
    for i, entry in enumerate(st.session_state.history):
        if st.sidebar.button(f"{entry['audio_name']} ({entry['content_type']})", key=f"load_{i}"):
            st.session_state.current_audio_name = entry['audio_name']
            st.session_state.output_type = entry['content_type']
            
            # Restore saved data into the correct slots based on type
            if entry['content_type'] == "Notes":
                st.session_state.saved_notes = entry['notes']
            elif entry['content_type'] == "Quiz":
                st.session_state.saved_quiz = entry['notes']
            elif entry['content_type'] == "Flashcards":
                st.session_state.saved_flashcards = entry['notes']
            
            st.rerun()
    st.sidebar.markdown("---")
    if st.sidebar.button("🗑 Clear History"):
        if os.path.exists(core.HISTORY_FILE):
            os.remove(core.HISTORY_FILE)
        # Reset all core state variables
        st.session_state.history = []
        st.session_state.saved_notes = None
        st.session_state.saved_quiz = None
        st.session_state.saved_flashcards = None
        st.rerun()
else:
    st.sidebar.info("No previous history.")
