from openai import OpenAI
import openai
import os
from dotenv import load_dotenv
import db
import joblib
import pandas as pd
import numpy as np
import logging
import traceback

load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

## AI CHAT
model = os.getenv('MODEL')
api = os.getenv('GROQ_API_KEY')
client = OpenAI(base_url=os.getenv("BASE_URL_GROQ"), api_key=api)

# Load the trained model and encoder once when module is imported
xgb_model = None
ohe_encoder = None

try:
    xgb_model = joblib.load('ai/Models/xgboost_model.pkl')
    ohe_encoder = joblib.load('ai/Models/onehot_encoder.pkl')
    logger.info("✅ ML models loaded successfully")
    print("✅ ML models loaded successfully")
except FileNotFoundError as e:
    logger.error(f"⚠️  ML model files not found: {e}")
    print(f"⚠️  Warning: ML model files not found - {e}")
except Exception as e:
    logger.error(f"⚠️  Could not load ML models: {e}")
    print(f"⚠️  Warning: Could not load ML models - {e}")

def get_explanation(_id):
    """Get AI explanation for user query with comprehensive error handling"""
    try:
        # Validate input
        if not _id:
            logger.error("No _id provided to get_explanation")
            return "Error: Invalid user ID"
        
        # Get conversation from database
        try:
            document = db.get_chat(_id)
        except Exception as db_error:
            logger.error(f"Database error in get_explanation: {db_error}")
            return "Error: Could not retrieve conversation history"
        
        # Handle case where no conversation exists yet
        if not document or document == False:
            logger.warning(f"No conversation found for ID: {_id}")
            return "Error: No conversation found. Please try again."
        
        if not isinstance(document, list) or len(document) == 0:
            logger.error(f"Invalid document format from database: {type(document)}")
            return "Error: Invalid conversation data"
        
        # Extract conversation
        try:
            conversation = document[0].get('conversation', [])
            if not conversation:
                logger.warning(f"Empty conversation for ID: {_id}")
                return "Error: No conversation messages found"
        except (KeyError, IndexError, AttributeError) as e:
            logger.error(f"Error extracting conversation: {e}")
            return "Error: Invalid conversation format"
        
        # Clean up the conversation - ensure all content fields are strings
        cleaned_conversation = []
        try:
            for i, msg in enumerate(conversation):
                if not isinstance(msg, dict):
                    logger.warning(f"Invalid message format at index {i}: {type(msg)}")
                    continue
                
                if 'content' in msg and msg['content'] is not None and 'role' in msg:
                    cleaned_conversation.append({
                        'role': str(msg['role']),
                        'content': str(msg['content'])
                    })
                else:
                    logger.warning(f"Message missing content/role at index {i}: {msg}")
        except Exception as e:
            logger.error(f"Error cleaning conversation: {e}")
            return "Error: Could not process conversation"
        
        if not cleaned_conversation:
            logger.warning("No valid messages in conversation")
            return "Error: No valid messages in conversation"
        
        logger.info(f"Processing {len(cleaned_conversation)} messages for user {_id}")
        
        # Validate API configuration
        if not model or not api or not client:
            logger.error("AI API configuration missing")
            return "Error: AI service not configured"
        
        logger.info(f"Using model: {model}")
        logger.info(f"API endpoint: {os.getenv('BASE_URL_GROQ')}")
        
        # Make API call with timeout and retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model, 
                    temperature=0.3, 
                    messages=cleaned_conversation,
                    timeout=30  # 30 second timeout
                )
                
                if response and response.choices and len(response.choices) > 0:
                    ai_response = response.choices[0].message.content
                    if ai_response:
                        logger.info(f"AI response generated successfully for user {_id}")
                        return ai_response
                    else:
                        logger.error("Empty AI response")
                        return "Error: AI returned empty response"
                else:
                    logger.error("Invalid AI response structure")
                    return "Error: Invalid AI response"
                    
            except openai.APITimeoutError as e:
                logger.warning(f"AI API timeout on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return "Error: AI service timeout. Please try again."
            except openai.APIError as e:
                logger.error(f"AI API error on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    return f"Error: AI service error - {str(e)}"
            except Exception as e:
                logger.error(f"Unexpected AI error on attempt {attempt + 1}: {e}")
                logger.error(f'AI Stack trace: {traceback.format_exc()}')
                if attempt == max_retries - 1:
                    return f"Error: AI service unavailable - {str(e)}"
        
        return "Error: AI service failed after multiple attempts"

    except Exception as e:
        logger.error(f"Unexpected error in get_explanation: {e}")
        logger.error(f'Stack trace: {traceback.format_exc()}')
        return f"Error: {str(e)}"

## Fire Flammability Prediction Function
def predict_flammability(data):
    """
    Predict fire flammability using trained XGBoost model with comprehensive error handling
    
    Args:
        data (dict): Dictionary containing sensor data
        Expected keys: temperature, humidity, soil_moisture, gas_level, ph_value, soil_temperature, light_intensity
    
    Returns:
        int: Fire risk level (0-4)
        0 = No Risk (0-20% probability)
        1 = Low Risk (20-40% probability)  
        2 = Moderate Risk (40-60% probability)
        3 = High Risk (60-80% probability)
        4 = Extreme Risk (80-100% probability)
    """
    try:
        # Validate input data
        if not data or not isinstance(data, dict):
            logger.error(f"Invalid input data: {type(data)}")
            return 0
        
        # Check if models are loaded
        if xgb_model is None or ohe_encoder is None:
            logger.warning("ML models not loaded, returning default prediction: 0")
            return 0
        
        # Hardcoded values for Kathmandu, Nepal
        KATHMANDU_DEFAULTS = {
            'ELEVATION': 1400.0,  # Kathmandu valley elevation ~1400m
            'SLOPE': 8.5,         # Gentle slopes in Kathmandu valley
            'LANDCOVER': 'Others', # Mixed urban/agricultural land
            'WS2M': 2.1           # Average wind speed in Kathmandu
        }
        
        # Safely extract and validate sensor data
        try:
            temperature = float(data.get('temperature', 25.0))
            humidity = float(data.get('humidity', 50.0))
            soil_moisture_raw = float(data.get('soil_moisture', 15.0))
            
            # Validate ranges
            if not -50 <= temperature <= 60:
                logger.warning(f"Temperature out of range: {temperature}°C, using default")
                temperature = 25.0
            
            if not 0 <= humidity <= 100:
                logger.warning(f"Humidity out of range: {humidity}%, using default")
                humidity = 50.0
            
            if not 0 <= soil_moisture_raw <= 100:
                logger.warning(f"Soil moisture out of range: {soil_moisture_raw}%, using default")
                soil_moisture_raw = 15.0
                
        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing sensor data: {e}")
            logger.error(f"Sensor data received: {data}")
            return 0
        
        # Map sensor data to model features
        model_input = {
            'ELEVATION': KATHMANDU_DEFAULTS['ELEVATION'],
            'SLOPE': KATHMANDU_DEFAULTS['SLOPE'], 
            'LANDCOVER': KATHMANDU_DEFAULTS['LANDCOVER'],
            'T2M': temperature,
            'RH2M': humidity,
            'WS2M': KATHMANDU_DEFAULTS['WS2M'],
            'ssm': soil_moisture_raw / 100.0  # Convert to m³/m³ (0-1 range)
        }
        
        logger.info(f"🔥 Predicting flammability for Kathmandu:")
        logger.info(f"   🌡️  Temperature: {model_input['T2M']}°C")
        logger.info(f"   💧 Humidity: {model_input['RH2M']}%")
        logger.info(f"   🌱 Soil Moisture: {model_input['ssm']:.3f}")
        logger.info(f"   📍 Location: {model_input['ELEVATION']}m elevation, {model_input['SLOPE']}° slope")
        logger.info(f"   🌿 Land Cover: {model_input['LANDCOVER']}")
        
        # Create DataFrame from input data
        try:
            input_data = pd.DataFrame({
                'ELEVATION': [model_input['ELEVATION']],
                'SLOPE': [model_input['SLOPE']],
                'LANDCOVER': [model_input['LANDCOVER']],
                'T2M': [model_input['T2M']],
                'RH2M': [model_input['RH2M']],
                'WS2M': [model_input['WS2M']],
                'ssm(m³/m³)': [model_input['ssm']]
            })
        except Exception as e:
            logger.error(f"Error creating input DataFrame: {e}")
            return 0
        
        # Preprocess the data: One-hot encode 'LANDCOVER'
        try:
            landcover_data = input_data[['LANDCOVER']]
            landcover_encoded = ohe_encoder.transform(landcover_data)
            
            # Create DataFrame from encoded features
            feature_names = ohe_encoder.get_feature_names_out(['LANDCOVER'])
            landcover_encoded_df = pd.DataFrame(
                landcover_encoded, 
                columns=feature_names, 
                index=input_data.index
            )
            
            # Combine processed data
            processed_data = input_data.drop('LANDCOVER', axis=1).reset_index(drop=True)
            processed_data = pd.concat([processed_data, landcover_encoded_df], axis=1)
            
        except Exception as e:
            logger.error(f"Error preprocessing data: {e}")
            return 0
        
        # Make prediction
        try:
            prediction = xgb_model.predict(processed_data)[0]
            prediction_proba = xgb_model.predict_proba(processed_data)[0]
            
            # Get probability of fire (class 1)
            fire_probability = prediction_proba[1] if len(prediction_proba) > 1 else prediction_proba[0]
            
            # Convert probability to risk level (0-4)
            if fire_probability >= 0.8:
                risk_level = 4  # Extreme Risk
                risk_emoji = "🔴"
                risk_text = "Extreme Risk"
            elif fire_probability >= 0.6:
                risk_level = 3  # High Risk
                risk_emoji = "🟠"
                risk_text = "High Risk"
            elif fire_probability >= 0.4:
                risk_level = 2  # Moderate Risk
                risk_emoji = "🟡"
                risk_text = "Moderate Risk"
            elif fire_probability >= 0.2:
                risk_level = 1  # Low Risk
                risk_emoji = "🟢"
                risk_text = "Low Risk"
            else:
                risk_level = 0  # No Risk
                risk_emoji = "🔵"
                risk_text = "No Risk"
            
            # Log prediction results
            logger.info(f"   🎯 Prediction: {risk_emoji} {risk_text} (Level {risk_level})")
            logger.info(f"   📊 Fire Probability: {fire_probability:.2%}")
            
            return risk_level
            
        except Exception as e:
            logger.error(f"Error making prediction: {e}")
            logger.error(f'Prediction Stack trace: {traceback.format_exc()}')
            return 0
        
    except Exception as e:
        logger.error(f"❌ Unexpected error in fire prediction: {e}")
        logger.error(f"   📊 Sensor data received: {data}")
        logger.error(f'Stack trace: {traceback.format_exc()}')
        return 0  # Default to no fire risk on error