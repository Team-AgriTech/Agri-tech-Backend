import logging
import traceback
from flask import Flask, request, jsonify
import db
from datetime import datetime, timezone
import ai
import os
import sys
from werkzeug.exceptions import BadRequest, InternalServerError, NotFound, MethodNotAllowed

app = Flask(__name__)

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Global error handlers
@app.errorhandler(400)
def bad_request(error):
    logger.warning(f"Bad request: {error}")
    return jsonify({
        'status': 'failed',
        'error': 'Bad request',
        'message': 'Invalid request format or missing required fields'
    }), 400

@app.errorhandler(404)
def not_found(error):
    logger.warning(f"Route not found: {request.url}")
    return jsonify({
        'status': 'failed',
        'error': 'Route not found',
        'message': f'The requested URL {request.url} was not found on this server'
    }), 404

@app.errorhandler(405)
def method_not_allowed(error):
    logger.warning(f"Method not allowed: {request.method} {request.url}")
    return jsonify({
        'status': 'failed',
        'error': 'Method not allowed',
        'message': f'Method {request.method} is not allowed for this endpoint'
    }), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'status': 'failed',
        'error': 'Internal server error',
        'message': 'An unexpected error occurred'
    }), 500

# Handle SSL/TLS connection attempts to HTTP server
@app.before_request
def handle_ssl_requests():
    """Handle SSL/TLS connection attempts to HTTP server"""
    try:
        # Check if this looks like an SSL/TLS handshake
        if request.environ.get('REQUEST_METHOD') == 'POST' and not request.content_type:
            raw_data = request.get_data()
            if raw_data and len(raw_data) > 0:
                # Check for TLS handshake signature (starts with \x16\x03)
                if raw_data[:2] == b'\x16\x03':
                    logger.warning("SSL/TLS connection attempt detected on HTTP endpoint")
                    return jsonify({
                        'status': 'failed',
                        'error': 'SSL/TLS not supported',
                        'message': 'This server only accepts HTTP requests. Use http:// instead of https://'
                    }), 400
    except Exception as e:
        logger.warning(f"Error checking for SSL attempt: {e}")
        pass

# Root route
@app.route("/")
def hello_world():
    try:
        logger.info("Root endpoint accessed")
        return jsonify({
            "status": "success",
            "message": "Agro-tech Backend is running!",
            "endpoints": [
                "GET /health",
                "GET /get_all_data", 
                "GET /get_current_data",
                "POST /save_data",
                "POST /chat"
            ]
        })
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        return jsonify({'status': 'failed', 'error': str(e)}), 500

# Health check route
@app.route("/health")
def health_check():
    try:
        logger.info("Health check accessed")
        
        # Test database connection
        db_status = "connected"
        try:
            db.get_current_data()
        except Exception as db_error:
            db_status = f"error: {str(db_error)}"
            logger.error(f"Database health check failed: {db_error}")
        
        # Test ML models
        ml_status = "loaded" if ai.xgb_model is not None and ai.ohe_encoder is not None else "not loaded"
        
        return jsonify({
            "status": "healthy", 
            "message": "API is running",
            "database": db_status,
            "ml_models": ml_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        return jsonify({'status': 'failed', 'error': str(e)}), 500

## Route to get all sensor data
@app.route("/get_all_data")
def get_all_data():
    """
    This is get_all_data route which response JSON array with all the sensor data.
    Response JSON Format: [
        {
            "_id": "document_id",
            "timestamp": "ISO timestamp",
            "device_id": "string",
            "data": {...},
            "prediction": int
        }
    ]
    """
    try:
        logger.info("get_all_data endpoint accessed")
        
        result = db.get_all_data()
        
        if result is None:
            logger.warning("No data found in database")
            return jsonify([])
        
        logger.info(f"Retrieved {len(result) if isinstance(result, list) else 1} records")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f'Error in get_all_data: {e}')
        logger.error(f'Stack trace: {traceback.format_exc()}')
        return jsonify({
            'status': 'failed',
            'error': 'Failed to retrieve data',
            'message': str(e)
        }), 500

## Route to get current sensor data
@app.route("/get_current_data")
def get_current_data():
    """
    This is get_current_data route which response JSON array with current sensor data (latest entry).
    Response JSON Format: [
        {
            "_id": "document_id", 
            "timestamp": "ISO timestamp",
            "device_id": "string",
            "data": {...},
            "prediction": int
        }
    ]
    """
    try:
        logger.info("get_current_data endpoint accessed")
        
        result = db.get_current_data()
        
        if result is None:
            logger.warning("No current data found in database")
            return jsonify([])
        
        logger.info("Retrieved current data successfully")
        return jsonify(result)
        
    except Exception as e:
        logger.error(f'Error in get_current_data: {e}')
        logger.error(f'Stack trace: {traceback.format_exc()}')
        return jsonify({
            'status': 'failed',
            'error': 'Failed to retrieve current data',
            'message': str(e)
        }), 500

## Route to store sensor data
@app.route("/save_data", methods=["POST"])
def save_data():
    """
    This is save_data route which takes a json in body and store sensor data.
    Expected Json body: {
        "device_id": "string",
        "data": {
            "humidity": float,
            "temperature": float,
            "soil_moisture": float,
            "gas_level": float,
            "ph_value": float,
            "soil_temperature": float,
            "light_intensity": float
        }
    }
    Response: {
        "status": "string"
    }
    """
    try:
        logger.info("save_data endpoint accessed")
        
        # Validate content type
        if not request.is_json:
            logger.warning(f"Invalid content type: {request.content_type}")
            return jsonify({
                'status': 'failed',
                'error': 'Invalid content type',
                'message': 'Request must be JSON'
            }), 400
        
        # Get JSON data safely
        try:
            request_data = request.get_json()
        except Exception as json_error:
            logger.error(f"JSON parsing error: {json_error}")
            return jsonify({
                'status': 'failed',
                'error': 'Invalid JSON',
                'message': 'Could not parse JSON data'
            }), 400
        
        if not request_data:
            logger.warning("Empty request body")
            return jsonify({
                'status': 'failed',
                'error': 'Empty request',
                'message': 'Request body cannot be empty'
            }), 400
        
        # Extract and validate device_id
        device_id = request_data.get('device_id')
        if not device_id:
            logger.warning("Missing device_id in request")
            return jsonify({
                'status': 'failed',
                'error': 'Missing device_id',
                'message': 'device_id is required'
            }), 400
        
        # Extract and validate sensor data
        sensor_data = request_data.get('data', {})
        if not sensor_data or not isinstance(sensor_data, dict):
            logger.warning("Missing or invalid sensor data")
            return jsonify({
                'status': 'failed',
                'error': 'Invalid data',
                'message': 'data field must be a non-empty object'
            }), 400
        
        # Validate required sensor fields
        required_fields = ['humidity', 'temperature', 'soil_moisture']
        missing_fields = []
        invalid_fields = []
        
        for field in required_fields:
            if field not in sensor_data:
                missing_fields.append(field)
            else:
                try:
                    float(sensor_data[field])
                except (ValueError, TypeError):
                    invalid_fields.append(field)
        
        if missing_fields:
            logger.warning(f"Missing required fields: {missing_fields}")
            return jsonify({
                'status': 'failed',
                'error': 'Missing required fields',
                'message': f'Missing fields: {", ".join(missing_fields)}'
            }), 400
        
        if invalid_fields:
            logger.warning(f"Invalid field values: {invalid_fields}")
            return jsonify({
                'status': 'failed',
                'error': 'Invalid field values',
                'message': f'Fields must be numeric: {", ".join(invalid_fields)}'
            }), 400
        
        # Get AI prediction safely
        try:
            prediction = ai.predict_flammability(sensor_data)
            logger.info(f"AI prediction completed: {prediction}")
        except Exception as ai_error:
            logger.error(f"AI prediction error: {ai_error}")
            logger.error(f'AI Stack trace: {traceback.format_exc()}')
            prediction = 0  # Default to no fire risk
            logger.warning("Using default prediction due to AI error")
        
        # Create the document to save
        document = {
            'device_id': str(device_id),
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'data': sensor_data,
            'prediction': int(prediction)
        }
        
        # Save to database
        try:
            save_result = db.save_data(document)
            if save_result:
                logger.info(f"Data saved successfully for device: {device_id}")
                return jsonify({'status': 'success'})
            else:
                logger.error("Database save operation returned False")
                return jsonify({
                    'status': 'failed',
                    'error': 'Database save failed',
                    'message': 'Could not save data to database'
                }), 500
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            logger.error(f'DB Stack trace: {traceback.format_exc()}')
            return jsonify({
                'status': 'failed',
                'error': 'Database error',
                'message': str(db_error)
            }), 500
            
    except Exception as e:
        logger.error(f'Unexpected error in save_data: {e}')
        logger.error(f'Stack trace: {traceback.format_exc()}')
        return jsonify({
            'status': 'failed',
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500

## Chat route
@app.route("/chat", methods=["POST"])
def chat():
    """
    This is chat route which takes a json in body and response markdown text in text/plain content-type.
    Expected Json body: {
        "_id": "(IMEI number maybe)",
        "message": "Chat message"
    }
    """
    try:
        logger.info("chat endpoint accessed")
        
        # Validate content type
        if not request.is_json:
            logger.warning(f"Invalid content type for chat: {request.content_type}")
            return jsonify({
                'status': 'failed',
                'error': 'Invalid content type',
                'message': 'Request must be JSON'
            }), 400
        
        # Get JSON data safely
        try:
            data = request.get_json()
        except Exception as json_error:
            logger.error(f"JSON parsing error in chat: {json_error}")
            return jsonify({
                'status': 'failed',
                'error': 'Invalid JSON',
                'message': 'Could not parse JSON data'
            }), 400
        
        if not data:
            return jsonify({
                'status': 'failed',
                'error': 'Empty request',
                'message': 'Request body cannot be empty'
            }), 400
        
        # Extract and validate required fields
        message = data.get("message")
        _id = data.get("_id")
        
        if not message:
            logger.warning("Missing message in chat request")
            return jsonify({
                'status': 'failed',
                'error': 'Missing message',
                'message': 'message field is required'
            }), 400
        
        if not _id:
            logger.warning("Missing _id in chat request")
            return jsonify({
                'status': 'failed',
                'error': 'Missing _id',
                'message': '_id field is required'
            }), 400
        
        # Validate message length
        if len(str(message).strip()) == 0:
            return jsonify({
                'status': 'failed',
                'error': 'Empty message',
                'message': 'Message cannot be empty'
            }), 400
        
        if len(str(message)) > 2000:  # Reasonable limit
            return jsonify({
                'status': 'failed',
                'error': 'Message too long',
                'message': 'Message must be less than 2000 characters'
            }), 400
        
        logger.info(f"Processing chat for user: {_id}")
        
        # Add user message to conversation
        try:
            user_msg_result = db.update_chat(_id, {'role': 'user', 'content': str(message)})
            if not user_msg_result:
                logger.error("Failed to save user message to database")
                return jsonify({
                    'status': 'failed',
                    'error': 'Database error',
                    'message': 'Could not save user message'
                }), 500
        except Exception as db_error:
            logger.error(f"Database error saving user message: {db_error}")
            return jsonify({
                'status': 'failed',
                'error': 'Database error',
                'message': str(db_error)
            }), 500
        
        # Get AI response
        try:
            response = ai.get_explanation(_id)
            logger.info(f"AI response generated for user: {_id}")
        except Exception as ai_error:
            logger.error(f"AI response error: {ai_error}")
            logger.error(f'AI Stack trace: {traceback.format_exc()}')
            response = "Sorry, I'm currently experiencing technical difficulties. Please try again later."
        
        # Check if AI response was successful
        if not response or response.startswith("Error:"):
            logger.error(f'AI response failed: {response}')
            return jsonify({
                'status': 'failed',
                'error': 'AI service error',
                'message': response or 'AI service unavailable'
            }), 500
        
        # Add AI response to conversation
        try:
            ai_msg_result = db.update_chat(_id, {'role': 'assistant', 'content': str(response)})
            if not ai_msg_result:
                logger.warning("Failed to save AI response to database")
                # Don't fail the request, just log the warning
        except Exception as db_error:
            logger.error(f"Database error saving AI response: {db_error}")
            # Don't fail the request, just log the error
        
        return response, 200, {'Content-Type': 'text/plain'}
        
    except Exception as e:
        logger.error(f'Unexpected error in chat: {e}')
        logger.error(f'Stack trace: {traceback.format_exc()}')
        return jsonify({
            'status': 'failed',
            'error': 'Internal server error',
            'message': 'An unexpected error occurred'
        }), 500

if __name__ == '__main__':
    try:
        port = int(os.environ.get('PORT', 5000))
        logger.info(f"Starting server on port {port}")
        logger.info("Server is HTTP only - use http:// not https://")
        app.run(host='0.0.0.0', port=port, debug=False)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        sys.exit(1)