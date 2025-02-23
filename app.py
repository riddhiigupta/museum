from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import os
import requests

app = Flask(__name__)
CORS(app)

# Use Ollama's API endpoint instead of local process
OLLAMA_API = "https://api.ollama.ai/v1/chat/completions"  # You'll need to get an API key

@app.route('/')
def home():
    return send_file('index.html')

@app.route('/images/<path:filename>')
def serve_image(filename):
    return send_file(os.path.join('images', filename))

@app.route('/videos/<path:filename>')
def serve_video(filename):
    return send_file(os.path.join('videos', filename))

@app.route('/chat', methods=['POST'])
def chat():
    try:
        data = request.json
        question = data.get('question', '')
        
        # Call Ollama API
        response = requests.post(OLLAMA_API, 
            json={
                "model": "mistral",
                "messages": [{"role": "user", "content": question}]
            },
            headers={
                "Authorization": f"Bearer {os.environ['OLLAMA_API_KEY']}"
            }
        )
        
        if response.ok:
            return jsonify({"response": response.json()['choices'][0]['message']['content']})
        else:
            return jsonify({"response": "I encountered an error. Please try again."})
            
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"response": "I encountered an error. Please try again."})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8080) 