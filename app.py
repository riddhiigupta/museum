from flask import Flask, request, jsonify, send_file, Response
from flask_cors import CORS
import os
import subprocess
import time
import json

app = Flask(__name__)
CORS(app)

def init_ollama():
    """Initialize Ollama chat process"""
    try:
        print("Starting Ollama...")
        # Start Ollama service
        subprocess.Popen(['ollama', 'serve'])
        time.sleep(2)  # Wait for service to start
        
        # Start Ollama chat in interactive mode
        process = subprocess.Popen(
            ['ollama', 'run', 'mistral'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        print("Ollama is ready!")
        return process
    except Exception as e:
        print(f"Error starting Ollama: {e}")
        return None

# Initialize Ollama when server starts
ollama_process = init_ollama()

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
    global ollama_process
    try:
        # Restart Ollama if needed
        if not ollama_process or ollama_process.poll() is not None:
            ollama_process = init_ollama()
            if not ollama_process:
                return jsonify({"response": "Failed to connect to Ollama. Please try again."})

        data = request.json
        prompt = data.get('prompt', '')  # Keep the character context
        question = data.get('question', '')
        
        # Format the full prompt with character context
        full_prompt = f"""You are this character: {prompt}
        Question: {question}
        Answer in character and be specific."""
        
        def generate():
            try:
                # Send prompt to Ollama
                ollama_process.stdin.write(full_prompt + '\n')
                ollama_process.stdin.flush()
                
                # Stream response
                response = ""
                while True:
                    char = ollama_process.stdout.read(1)
                    if not char or char == '\n':
                        if response:
                            yield f"data: {json.dumps({'chunk': response})}\n\n"
                            response = ""
                        if not char:
                            break
                    else:
                        response += char
                        if len(response) >= 10:  # Send chunks of ~10 characters
                            yield f"data: {json.dumps({'chunk': response})}\n\n"
                            response = ""
                
                yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                print(f"Error in generate: {e}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(generate(), mimetype='text/event-stream')
        
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": "I encountered an error. Please try again."})

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=5000) 