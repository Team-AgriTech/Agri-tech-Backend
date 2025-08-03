import os
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
import json

load_dotenv()
client = MongoClient(os.getenv("MONGO_CONNECTION_STRING"))

db = client.Unnchai
data_collection = db.Data
chats_collection = db.Chat

# Custom JSON encoder to handle ObjectId
class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

## SENSOR DATA AND PREDICTION
def save_data(data):
    result = data_collection.insert_one(data)
    return result.acknowledged


def get_all_data():
    result = data_collection.find({}).sort("_id", -1)
    documents = list(result)
    # Convert ObjectId to string for JSON serialization
    for doc in documents:
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
    return documents


def get_current_data():
    print("=== DEBUGGING get_current_data ===")
    
    # Get all documents and show their _id and timestamp
    all_docs = list(data_collection.find({}, {"_id": 1, "timestamp": 1, "device_id": 1}).sort("_id", -1).limit(5))
    print("Top 5 documents sorted by _id (newest first):")
    for i, doc in enumerate(all_docs):
        print(f"  {i+1}. _id: {doc['_id']} | timestamp: {doc.get('timestamp')} | device: {doc.get('device_id')}")
    
    # Also try sorting by timestamp
    all_docs_by_time = list(data_collection.find({}, {"_id": 1, "timestamp": 1, "device_id": 1}).sort("timestamp", -1).limit(5))
    print("\nTop 5 documents sorted by timestamp (newest first):")
    for i, doc in enumerate(all_docs_by_time):
        print(f"  {i+1}. _id: {doc['_id']} | timestamp: {doc.get('timestamp')} | device: {doc.get('device_id')}")
    
    # Get what we're actually returning
    latest_record = data_collection.find().sort("_id", -1).limit(1)
    documents = list(latest_record)
    
    print(f"\n=== RETURNING ===")
    if documents:
        print(f"Returning document:")
        print(f"  _id: {documents[0]['_id']}")
        print(f"  timestamp: {documents[0].get('timestamp')}")
        print(f"  device_id: {documents[0].get('device_id')}")
    else:
        print("No documents found!")
    
    # Convert ObjectId to string for JSON serialization
    for doc in documents:
        if '_id' in doc:
            doc['_id'] = str(doc['_id'])
    
    return documents



## CHATS
def get_chat(_id):
    document = list(chats_collection.find({"_id": _id}))
    if document:
        # Convert ObjectId to string for JSON serialization
        for doc in document:
            if '_id' in doc:
                doc['_id'] = str(doc['_id'])
        return document
    else:
        return False


def update_chat(_id, new_chat):

    if not chats_collection.find_one({"_id" : _id}):
        chats_collection.insert_one({"_id" : _id, "conversation": [
                    {
                        "role": "system",
                        "content": "You are a knowledgeable AI assistant specializing in agriculture, particularly in the context of Nepal. Your role is to provide concise and relevant answers to user queries related to farming practices, crop cultivation, agricultural policies, and challenges faced by farmers in Nepal. Ensure that your responses are tailored to the unique agricultural landscape of Nepal, considering local practices, climate, and economic factors. DONOT answer anything beside Agriculture",
                    }
                ]})

    result = chats_collection.update_one(
        {"_id": _id},
        {"$push": {"conversation": new_chat}}
    )

    return result.acknowledged
