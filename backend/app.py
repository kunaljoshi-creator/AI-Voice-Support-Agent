from flask import Flask, request, jsonify, send_file
import google.generativeai as genai
from gtts import gTTS
import os
from dotenv import load_dotenv
from flask_cors import CORS
import tempfile
import json
from datetime import datetime

# Load environment variable
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Create conversation history file if it doesn't exist
if not os.path.exists("conversation_history.json"):
    with open("conversation_history.json", "w") as f:
        json.dump([], f)

# Ensure audio directory exists
os.makedirs("audio", exist_ok=True)

# Initialize the model with a more conversational prompt
model = genai.GenerativeModel("gemini-2.0-flash")

# System prompt to make the AI behave like a support agent
SYSTEM_PROMPT = """
You are a helpful and friendly customer support agent. Your name is Alex.
Your goal is to assist customers with their queries in a natural, conversational manner.
Be empathetic, patient, and thorough in your responses.
Keep your answers concise but complete.
If you don't know something, be honest about it.
Use a friendly, conversational tone throughout the interaction.
Avoid using markdown formatting in your responses.
Your responses should be in a conversational tone, and you should use a friendly, empathetic tone throughout the interaction.
"""

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Store conversation history
conversation_history = {}

@app.route("/start-conversation", methods=["POST"])
def start_conversation():
    # Generate a unique session ID
    session_id = datetime.now().strftime("%Y%m%d%H%M%S")
    conversation_history[session_id] = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    return jsonify({"session_id": session_id})

# Add this import at the top with other imports
from langdetect import detect, LangDetectException

# Modify the ask_ai function to detect language and set appropriate TTS language
@app.route("/ask", methods=["POST"])
def ask_ai():
    data = request.json
    user_text = data.get("text")
    session_id = data.get("session_id")

    print(f"Received request with text: {user_text}, session_id: {session_id}") # Add logging

    if not user_text:
        return jsonify({"error": "No input text provided"}), 400
    
    if not session_id or session_id not in conversation_history:
        return jsonify({"error": "Invalid session ID"}), 400

    # Detect language of user input
    try:
        detected_lang = detect(user_text)
        print(f"Detected language: {detected_lang}") # Add logging
    except LangDetectException:
        detected_lang = "en"  # Default to English if detection fails
        print("Language detection failed, defaulting to English")

    # Map detected language code to language for the AI response
    lang_map = {
        "hi": "Hindi",
        "mr": "Marathi",
        "en": "English"
    }
    
    # Default to English if not Hindi or Marathi
    response_language = lang_map.get(detected_lang, "English")
    
    # Add user message to history
    conversation_history[session_id].append({"role": "user", "content": user_text})
    
    try:
        # Create conversation for Gemini
        history = conversation_history[session_id].copy()  # Use the original history format
        system_message = next((msg for msg in history if msg["role"] == "system"), None)
        
        print("Preparing to call Gemini API") # Add logging
        
        # Generate response using conversation history
        if system_message:
            # Format the conversation history as text
            conversation_text = "\n".join([f"{msg['role']}: {msg['content']}" 
                                    for msg in history 
                                    if msg['role'] != "system"])
            
            # Create the prompt with system message, history, language instruction and new user query
            prompt = (system_message["content"] + 
                     f"\n\nRespond in {response_language}." +
                     "\n\nConversation history:\n" + 
                     conversation_text + 
                     "\n\nUser: " + user_text)
            
            response = model.generate_content(prompt)
        else:
            # Otherwise just use the history directly with language instruction
            response = model.generate_content(f"Respond in {response_language}. User query: {user_text}")
            
        reply = response.text
        print(f"Got response from Gemini: {reply[:50]}...") # Add logging

        # Add AI response to history
        conversation_history[session_id].append({"role": "assistant", "content": reply})
        
        # Save conversation to file (for persistence)
        save_conversation_to_file(session_id)

        # Process the reply to remove markdown formatting for speech
        speech_text = reply
        # Remove markdown formatting like *text* or **text**
        import re
        speech_text = re.sub(r'\*\*(.+?)\*\*', r'\1', speech_text)  # Remove bold formatting
        speech_text = re.sub(r'\*(.+?)\*', r'\1', speech_text)      # Remove italic formatting
        
        # Set TTS language based on detected language
        tts_lang_map = {
            "hi": "hi",  # Hindi
            "mr": "mr",  # Marathi
            "en": "en"   # English
        }
        tts_lang = tts_lang_map.get(detected_lang, "en")
        
        # Convert to speech with appropriate language settings
        print(f"Converting to speech in {tts_lang}") # Add logging
        tts = gTTS(speech_text, lang=tts_lang, tld='com', slow=False)
        audio_path = os.path.join("audio", f"response_{session_id}.mp3")
        tts.save(audio_path)
        print(f"Saved audio to {audio_path}") # Add logging

        return jsonify({"reply": reply, "session_id": session_id, "detected_language": detected_lang})
    
    except Exception as e:
        print(f"Error in ask_ai: {str(e)}") # Add detailed error logging
        import traceback
        traceback.print_exc() # Print full stack trace
        return jsonify({"error": str(e)}), 500

@app.route("/get-audio/<session_id>", methods=["GET"])
def get_audio(session_id):
    try:
        return send_file(f"audio/response_{session_id}.mp3", mimetype="audio/mpeg")
    except Exception as e:
        return jsonify({"error": str(e)}), 404

@app.route("/get-history/<session_id>", methods=["GET"])
def get_history(session_id):
    if session_id not in conversation_history:
        return jsonify({"error": "Session not found"}), 404
    
    # Return only user and assistant messages (not system)
    messages = [msg for msg in conversation_history[session_id] if msg["role"] != "system"]
    return jsonify({"history": messages})

def save_conversation_to_file(session_id):
    try:
        with open("conversation_history.json", "r") as f:
            all_conversations = json.load(f)
        
        # Find if session already exists in file
        session_exists = False
        for i, conv in enumerate(all_conversations):
            if conv.get("session_id") == session_id:
                all_conversations[i] = {
                    "session_id": session_id,
                    "timestamp": datetime.now().isoformat(),
                    "messages": conversation_history[session_id]
                }
                session_exists = True
                break
        
        if not session_exists:
            all_conversations.append({
                "session_id": session_id,
                "timestamp": datetime.now().isoformat(),
                "messages": conversation_history[session_id]
            })
        
        with open("conversation_history.json", "w") as f:
            json.dump(all_conversations, f, indent=2)
    
    except Exception as e:
        print(f"Error saving conversation: {e}")

if __name__ == "__main__":
    app.run(debug=True)
