import os
from elevenlabs import ElevenLabs
from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS
import json
import requests
import time
from flask_limiter import Limiter
import google.generativeai as genai

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}}, 
     methods=["GET", "POST", "OPTIONS"],
     allow_headers=["Content-Type", "Authorization"],
     supports_credentials=True)

# Create audio directory if it doesn't exist
os.makedirs('audio', exist_ok=True)

# Initialize ElevenLabs client with API key
client = ElevenLabs(
    api_key=os.getenv('ELEVENLABS_API_KEY')
)

# Initialize Gemini
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

# Add this near the top of your file
VOICE_IDS = {
    'stevejobs': "cjVigY5qzO86Huf0OWal",  # Professional male voice
    'markzuckerberg': "SOYHLrjzK2X1ezoPC6cr",  # Young male voice
    'elonmusk': "JBFqnCBsd6RMkjVDRZzb"  # Default male voice
}

limiter = Limiter(
    key_func=lambda: request.remote_addr,
    app=app
)

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_file(os.path.join('images', filename))

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_file(os.path.join('videos', filename))

def text_to_speech(text, character_id):
    voice_id = VOICE_IDS.get(character_id, "JBFqnCBsd6RMkjVDRZzb")  # Default if not found
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    
    headers = {
        "xi-api-key": os.getenv('ELEVENLABS_API_KEY'),
        "Content-Type": "application/json"
    }
    
    data = {
        "text": text,
        "model_id": "eleven_multilingual_v2"
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        return response.content
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

@app.route('/chat', methods=['POST'])
@limiter.limit("20 per day")  # Adjust as needed
def chat():
    print("\n" + "="*50)
    print("NEW CHAT REQUEST RECEIVED")
    print("="*50)
    data = request.json
    prompt = data.get('prompt', '')
    question = data.get('question', '')
    character_id = data.get('character_id', 'stevejobs')
    print(f"\nPROMPT: {prompt[:100]}...")
    print(f"QUESTION: {question}")
    print("="*50)

    def generate():
        try:
            # Use Gemini API
            model = genai.GenerativeModel('gemini-pro')
            
            try:
                # Simplified prompt structure with safety settings
                response = model.generate_content(
                    f"You are {prompt}. Answer this question briefly in 1-2 sentences: {question}",
                    generation_config={
                        "temperature": 0.7,
                        "max_output_tokens": 100,
                    }
                )
                
                answer = response.text.strip()
                print(f"Response: {answer}")
            except Exception as e:
                print(f"Gemini API error: {str(e)}")
                answer = "Sorry, I couldn't process your request at this time."
            
            # Send the answer in chunks to simulate streaming
            for i in range(0, len(answer), 3):
                chunk = answer[i:i+3]
                yield f"data: {json.dumps({'chunk': chunk})}\n\n"
                time.sleep(0.05)  # Small delay to simulate streaming
            
            # Generate audio with ElevenLabs
            try:
                voice_id = VOICE_IDS.get(character_id, "JBFqnCBsd6RMkjVDRZzb")
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                
                headers = {
                    "xi-api-key": os.getenv('ELEVENLABS_API_KEY'),
                    "Content-Type": "application/json"
                }
                
                data = {
                    "text": answer,
                    "model_id": "eleven_multilingual_v2"
                }
                
                print("Making request to ElevenLabs...")
                audio_response = requests.post(url, json=data, headers=headers)
                audio_response.raise_for_status()
                
                audio_data = audio_response.content
                timestamp = int(time.time() * 1000)
                audio_path = f"audio_chunk_{timestamp}.mp3"
                audio_full_path = os.path.join('audio', audio_path)
                
                with open(audio_full_path, 'wb') as f:
                    f.write(audio_data)
                print("✓ Audio file saved successfully")
                
                yield f"data: {json.dumps({'audio': audio_path})}\n\n"
            except Exception as e:
                print(f"Audio generation error: {str(e)}")
            
            yield f"data: {json.dumps({'done': True})}\n\n"
            
        except Exception as e:
            print(f"\n❌ API Error: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return Response(stream_with_context(generate()), mimetype='text/event-stream')

@app.route('/audio/<path:filename>')
def serve_audio(filename):
    return send_file(os.path.join('audio', filename))

@app.route('/test-audio', methods=['GET'])
def test_audio():
    print("\n=== Testing ElevenLabs Audio ===")
    test_text = "This is a test of the ElevenLabs text to speech system."
    
    try:
        url = "https://api.elevenlabs.io/v1/text-to-speech/JBFqnCBsd6RMkjVDRZzb"
        headers = {
            "xi-api-key": os.getenv('ELEVENLABS_API_KEY'),
            "Content-Type": "application/json"
        }
        data = {
            "text": test_text,
            "model_id": "eleven_multilingual_v2"
        }
        
        print(f"Using API Key: {os.getenv('ELEVENLABS_API_KEY')[:10]}...")
        print("Making request to ElevenLabs...")
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            print(f"Error from ElevenLabs: {response.text}")
            return jsonify({"error": response.text}), 500
            
        audio_data = response.content
        print(f"Audio data received: {len(audio_data)} bytes")
        
        audio_path = os.path.join('audio', 'test_audio.mp3')
        with open(audio_path, 'wb') as f:
            f.write(audio_data)
        print("✓ Test audio saved successfully")
        
        return send_file(audio_path, mimetype='audio/mpeg')
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5001, debug=True)