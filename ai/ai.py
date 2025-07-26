from openai import OpenAI
import openai
import os
from dotenv import load_dotenv
import db

load_dotenv()

## AI CHAT
model = os.getenv('MODEL')
api = os.getenv('GROQ_API_KEY')
client = OpenAI(base_url=os.getenv("BASE_URL_GROQ"), api_key=api)


def get_explanation(_id):
    document = db.get_chat(_id)
    
    # Handle case where no conversation exists yet
    if not document or document == False:
        print(f"No conversation found for ID: {_id}")
        return "Error: No conversation found. Please try again."
    
    conversation = document[0]['conversation']
    
    # Clean up the conversation - ensure all content fields are strings
    cleaned_conversation = []
    for msg in conversation:
        if 'content' in msg and msg['content'] is not None:
            cleaned_conversation.append({
                'role': msg['role'],
                'content': str(msg['content'])
            })
    
    print(f"Using model: {model}")
    print(f"API endpoint: {os.getenv('BASE_URL_GROQ')}")
    print(f"Cleaned conversation: {cleaned_conversation}")
    
    try:
        response = client.chat.completions.create(
            model=model, 
            temperature=0.3, 
            messages=cleaned_conversation
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error details: {e}")
        return f"Error: {str(e)}"


## Dummy Prediction function
def predict_flammability(data):
    return 33

