import logging
from flask import Flask, request, jsonify
import db
from datetime import datetime, timezone
import ai
import os

app = Flask(__name__)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Root route
@app.route("/")
def hello_world():
    return "<p>Agro-tech Backend is running!</p>"

# Health check route
@app.route("/health")
def health_check():
    return jsonify({"status": "healthy", "message": "API is running"})

## Route to get all sensor data
@app.route("/get_all_data")
def get_all_data():
    """
    This is get_all_data route which response JSON array with all the sensor data.
    Response JSON Format: [
        {
            "_id": "document_id",
            "timestamp": "ISO timestamp",
            "humidity": float,
            "temperature": float,
            "soil_moisture": float,
            "prediction": int
        }
    ]
    """
    try:
        result = db.get_all_data()
        return jsonify(result)
    except Exception as e:
        logging.error(f'Error in get_all_data: {e}')
        return jsonify({'error': 'Internal server error'}), 500

## Route to get current sensor data
@app.route("/get_current_data")
def get_current_data():
    """
    This is get_current_data route which response JSON array with current sensor data (latest entry).
    Response JSON Format: [
        {
            "_id": "document_id", 
            "timestamp": "ISO timestamp",
            "humidity": float,
            "temperature": float,
            "soil_moisture": float,
            "prediction": int
        }
    ]
    """
    try:
        result = db.get_current_data()
        return jsonify(result)
    except Exception as e:
        logging.error(f'Error in get_current_data: {e}')
        return jsonify({'error': 'Internal server error'}), 500

## Route to store sensor data
@app.route("/save_data", methods=["POST"])
def save_data():
    """
    This is save_data route which takes a json in body and store sensor data.
    Expected Json body: {
    humidity : float
    temperature : float
    soil_moisture : float
    }
    Response : {
    status : string
    }
    """
    try:
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['humidity', 'temperature', 'soil_moisture']
        for field in required_fields:
            if field not in data:
                return jsonify({'status': 'failed', 'error': f'Missing field: {field}'}), 400
        
        # Add timestamp and prediction
        data['timestamp'] = datetime.now(timezone.utc).isoformat()
        data['prediction'] = ai.predict_flammability(data)
        
        if db.save_data(data):
            return jsonify({'status': 'success'})
        else:
            return jsonify({'status': 'failed'}), 500
            
    except Exception as e:
        logging.error(f'Error in save_data: {e}')
        return jsonify({'status': 'failed', 'error': 'Internal server error'}), 500

## Chat route
@app.route("/chat", methods=["POST"])
def chat():
    """
    This is chat route which takes a json in body and response markdown text in text/plain content-type.
    Expected Json body: {
    _id : (IMEI number maybe)
    message : Chat
    }
    """
    try:
        data = request.get_json()
        message = data.get("message")
        _id = data.get("_id")
        
        if not message or not _id:
            return jsonify({'status': 'failed', 'error': 'Missing _id or message'}), 400
        
        # Add user message to conversation
        if not db.update_chat(_id, {'role': 'user', 'content': message}):
            return jsonify({'status': 'failed'}), 500
        
        # Get AI response
        response = ai.get_explanation(_id)
        
        # Check if AI response was successful
        if not response or response.startswith("Error:"):
            logging.error(f'AI response failed: {response}')
            return jsonify({'status': 'failed', 'error': response}), 500
        
        # Add AI response to conversation
        if not db.update_chat(_id, {'role': 'assistant', 'content': response}):
            return jsonify({'status': 'failed'}), 500
        
        return response, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        logging.error(f'Error in chat: {e}')
        return jsonify({'status': 'failed', 'error': 'Internal server error'}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)