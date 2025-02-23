import os
from elevenlabs import ElevenLabs
from flask import Flask, request, jsonify, send_file, Response, stream_with_context
from flask_cors import CORS
import json
import requests
import time

app = Flask(__name__)
CORS(app)

# Create audio directory if it doesn't exist
os.makedirs('audio', exist_ok=True)

# Initialize ElevenLabs client with API key
client = ElevenLabs(
    api_key=os.getenv('ELEVENLABS_API_KEY')
)

# Add this near the top of your file
VOICE_IDS = {
    'stevejobs': "cjVigY5qzO86Huf0OWal",  # Professional male voice
    'markzuckerberg': "SOYHLrjzK2X1ezoPC6cr",  # Young male voice
    'elonmusk': "JBFqnCBsd6RMkjVDRZzb"  # Default male voice
}

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
def chat():
    print("\n" + "="*50)
    print("NEW CHAT REQUEST RECEIVED")
    print("="*50)
    data = request.json
    prompt = data.get('prompt', '')
    question = data.get('question', '')
    print(f"\nPROMPT: {prompt[:100]}...")
    print(f"QUESTION: {question}")
    print("="*50)

    def generate():
        try:
            # Modified prompt to prevent self-conversation
            full_prompt = f"""<<SYS>>
You are {prompt}
IMPORTANT: Give ONE direct answer to the user's question. Keep it under 2 sentences.
DO NOT ask questions back. DO NOT continue the conversation.
<</SYS>>

Question: {question}
Answer (2 sentences max):"""

            print("\nSending request to Ollama...")
            
            response = requests.post(
                'http://localhost:11434/api/generate',
                json={
                    'model': 'mistral',
                    'prompt': full_prompt,
                    'stream': True,
                    'options': {
                        'temperature': 0.7,
                        'top_p': 0.9,
                        'max_tokens': 50,
                        'stop': ["\n", ".", "!", "?"]
                    }
                },
                stream=True,
                timeout=30
            )
            
            print("Connected to Ollama successfully")
            current_sentence = ""
            
            for line in response.iter_lines():
                if line:
                    try:
                        json_response = json.loads(line)
                        if 'response' in json_response:
                            chunk = json_response['response']
                            current_sentence += chunk
                            print(f"\rCollecting response: {current_sentence}", end="", flush=True)
                            yield f"data: {json.dumps({'chunk': chunk})}\n\n"

                        if json_response.get('done'):
                            print("\n\n" + "="*50)
                            print("GENERATING AUDIO")
                            print("="*50)
                            print(f"Text to convert: '{current_sentence}'")
                            
                            try:
                                api_key = os.getenv('ELEVENLABS_API_KEY')
                                print(f"\nUsing API key: {api_key[:10]}...")
                                print("Making request to ElevenLabs...")
                                
                                audio_data = client.text_to_speech.convert(
                                    text=current_sentence,
                                    voice_id="JBFqnCBsd6RMkjVDRZzb",
                                    model_id="eleven_multilingual_v2",
                                    output_format="mp3_44100_128"
                                )
                                
                                print(f"\nAudio data received: {type(audio_data)}")
                                print(f"Audio data length: {len(audio_data) if audio_data else 'None'}")
                                
                                if audio_data:
                                    timestamp = int(time.time() * 1000)
                                    audio_path = f"audio_chunk_{timestamp}.mp3"
                                    audio_full_path = os.path.join('audio', audio_path)
                                    print(f"\nSaving audio to: {audio_full_path}")
                                    
                                    with open(audio_full_path, 'wb') as f:
                                        f.write(audio_data)
                                    print("✓ Audio file saved successfully")
                                    print("="*50)
                                    
                                    yield f"data: {json.dumps({'audio': audio_path})}\n\n"
                                else:
                                    print("\n❌ ERROR: No audio data received from ElevenLabs")
                                    print("="*50)
                            except Exception as e:
                                print("\n❌ SPEECH GENERATION ERROR")
                                print(f"Error type: {type(e)}")
                                print(f"Error message: {str(e)}")
                                print("\nFull traceback:")
                                import traceback
                                print(traceback.format_exc())
                                print("="*50)

                            yield f"data: {json.dumps({'done': True})}\n\n"
                            
                    except Exception as e:
                        print(f"\n❌ Parse error: {e}")
                        yield f"data: {json.dumps({'error': 'Parse error'})}\n\n"

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

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5001, debug=True)