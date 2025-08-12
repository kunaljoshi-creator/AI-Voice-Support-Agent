let sessionId = null;
let isRecording = false;
let recognition = null;

// Initialize the conversation when the page loads
document.addEventListener('DOMContentLoaded', async () => {
  try {
    const response = await fetch("http://127.0.0.1:5000/start-conversation", {
      method: "POST",
      headers: { "Content-Type": "application/json" }
    });
    
    const data = await response.json();
    sessionId = data.session_id;
    console.log("Session started with ID:", sessionId);
  } catch (error) {
    console.error("Error starting conversation:", error);
    updateStatus("Error connecting to server", true);
  }
});

// Set up event listeners
document.getElementById("recordButton").addEventListener("click", toggleRecording);
document.getElementById("sendButton").addEventListener("click", sendTextMessage);
document.getElementById("textInput").addEventListener("keypress", (e) => {
  if (e.key === "Enter") sendTextMessage();
});

// Toggle recording state
function toggleRecording() {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
}

// Start voice recording
// Modify the startRecording function to include better error handling
// Modify the startRecording function to use the selected language
function startRecording() {
  if (!sessionId) {
    updateStatus("Session not initialized. Please refresh the page.", true);
    return;
  }

  try {
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    
    // Get the selected language from the dropdown
    const langSelect = document.getElementById("languageSelect");
    const selectedLang = langSelect ? langSelect.value : 'en-US';
    
    recognition.lang = selectedLang;
    recognition.interimResults = false;
    recognition.continuous = false;
    
    recognition.onstart = () => {
      isRecording = true;
      updateRecordButton(true);
      updateStatus("Listening...");
      console.log("Speech recognition started"); // Add logging
    };
    
    recognition.onresult = (event) => {
      const text = event.results[0][0].transcript;
      console.log("Recognized text:", text); // Add logging
      addMessageToChat("user", text);
      sendToAI(text);
    };
    
    recognition.onerror = (event) => {
      console.error("Speech recognition error", event.error);
      updateStatus(`Error: ${event.error}. Try again or type your message.`, true);
      stopRecording();
    };
    
    recognition.onend = () => {
      console.log("Speech recognition ended"); // Add logging
      stopRecording();
    };
    
    recognition.start();
  } catch (error) {
    console.error("Error starting speech recognition:", error);
    updateStatus("Could not access microphone. Please ensure you've granted permission.", true);
  }
}

// Stop voice recording
function stopRecording() {
  if (recognition) {
    recognition.stop();
  }
  isRecording = false;
  updateRecordButton(false);
  updateStatus("Ready to assist");
}

// Send text message from input field
function sendTextMessage() {
  const textInput = document.getElementById("textInput");
  const text = textInput.value.trim();
  
  if (text) {
    addMessageToChat("user", text);
    sendToAI(text);
    textInput.value = "";
  }
}

// Send message to AI backend
// Update the sendToAI function to display the detected language
async function sendToAI(text) {
  if (!sessionId) {
    updateStatus("Session not initialized. Please refresh the page.", true);
    return;
  }

  updateStatus("Processing...");
  
  try {
    const response = await fetch("http://127.0.0.1:5000/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, session_id: sessionId })
    });
    
    if (!response.ok) {
      throw new Error(`Server responded with status: ${response.status}`);
    }
    
    const data = await response.json();
    
    if (data.error) {
      throw new Error(data.error);
    }
    
    // Add AI response to chat
    addMessageToChat("assistant", data.reply);
    
    // Update language indicator if detected
    if (data.detected_language) {
      const langMap = {
        "hi": "Hindi",
        "mr": "Marathi",
        "en": "English"
      };
      const detectedLang = langMap[data.detected_language] || "Unknown";
      updateStatus(`Responding in ${detectedLang}`);
    }
    
    // Play audio response
    const audio = document.getElementById("player");
    audio.src = `http://127.0.0.1:5000/get-audio/${sessionId}?t=${new Date().getTime()}`;
    audio.oncanplaythrough = () => {
      audio.play();
      updateStatus("Ready to assist");
    };
    audio.onerror = () => {
      console.error("Error playing audio");
      updateStatus("Ready to assist");
    };
  } catch (error) {
    console.error("Error communicating with AI:", error);
    updateStatus(`Error: ${error.message}`, true);
  }
}

// Add a message to the chat display
function addMessageToChat(role, text) {
  const chatMessages = document.getElementById("chat-messages");
  const messageDiv = document.createElement("div");
  messageDiv.className = `message ${role}`;
  
  const contentDiv = document.createElement("div");
  contentDiv.className = "message-content";
  
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  
  contentDiv.appendChild(paragraph);
  messageDiv.appendChild(contentDiv);
  chatMessages.appendChild(messageDiv);
  
  // Auto-scroll to the bottom
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Update the record button appearance
function updateRecordButton(isRecording) {
  const button = document.getElementById("recordButton");
  const buttonText = document.getElementById("recordButtonText");
  
  if (isRecording) {
    button.classList.add("recording");
    buttonText.textContent = "Listening...";
  } else {
    button.classList.remove("recording");
    buttonText.textContent = "Speak";
  }
}

// Update status message
function updateStatus(message, isError = false) {
  const statusText = document.getElementById("status-text");
  statusText.textContent = message;
  
  if (isError) {
    statusText.classList.add("error");
  } else {
    statusText.classList.remove("error");
  }
}

// Add this at the beginning of your script.js file
document.addEventListener('DOMContentLoaded', () => {
  // Check if SpeechRecognition is supported
  if (!('SpeechRecognition' in window) && !('webkitSpeechRecognition' in window)) {
    alert("Sorry, your browser doesn't support speech recognition. Please try Chrome or Edge.");
    document.getElementById("recordButton").disabled = true;
    updateStatus("Speech recognition not supported", true);
  }
});