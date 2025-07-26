## Agriculture Sensor & Chatbot API Documentation

This Flask application provides endpoints for storing and retrieving sensor data from Arduino devices and offers a chat interface for AI-powered agricultural advice specific to Nepal.

---

### Table of Contents

1. [Overview](#overview)
2. [Prerequisites](#prerequisites)
3. [Installation & Setup](#installation--setup)
4. [Environment Variables](#environment-variables)
5. [Endpoints](#endpoints)

   * [POST `/save_data`](#post-savedata)
   * [GET `/get_all_data`](#get-get_all_data)
   * [GET `/get_current_data`](#get-get_current_data)
   * [POST `/chat`](#post-chat)
6. [Error Handling](#error-handling)
7. [Logging](#logging)
8. [Usage Examples](#usage-examples)
9. [Troubleshooting](#troubleshooting)

---

## Overview

This API serves two main purposes:

* **Data Storage & Retrieval**: Accepts periodic sensor readings from Arduino-based weather stations and stores them in a database, along with AI-predicted flammability values.
* **AI Chat Interface**: Provides a chat endpoint that logs user messages, generates AI-driven agricultural advice, and returns responses in markdown format.

The system prompt ensures the AI assistant remains focused on agriculture in Nepal.

---

## Prerequisites

* Python 3.8 or higher
* Flask

---

## Installation & Setup

1. **Clone the repository**:

   ```bash
   git clone https://github.com/Creepyrishi/Agro-tech-Backend.git
   cd Agro-tech-Backend
   ```

2. **Create a virtual environment**:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   forwindows .\venv\Scripts\Activate.ps1

   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```

4. **Run the app**:

   ```bash
   python app.py
   ```

By default, the Flask server runs in debug mode on `http://127.0.0.1:5000`.

---

## Environment Variables

Configure any sensitive settings via environment variables or a `.env` file, for example:

```bash
MODEL="gemma2-9b-it"
OPENAI_API=""
BASE_URL_GROQ="https://api.groq.com/openai/v1"
MONGO_CONNECTION_STRING=""
```

Make sure to load these in your code (e.g., via `python-dotenv`).

---

## Endpoints

### POST `/save_data`

**Description**: Stores sensor data plus AI-predicted flammability.

* **URL**: `/save_data`
* **Method**: `POST`
* **Headers**: `Content-Type: application/json`

#### Request Body Schema

```json
{
  "device_id": "station-01",
  "data": {
    "temperature": 26.4,
    "humidity": 61,
    "soil_moisture": 432,
    "gas_level": 230,
    "ph_value": 6.7,
    "soil_temperature": 23.5,
    "light_intensity": 320
  }
}
```

#### Response

* **200 OK**: `{"status": "success"}`
* **500 Internal Server Error**: `{"status": "failed"}`

### GET `/get_all_data`

**Description**: Retrieves all stored sensor records, sorted newest first.

* **URL**: `/get_all_data`
* **Method**: `GET`

#### Response

* **200 OK**: Array of records:

```json
[
  {
    "_id": "<record_id>",
    "device_id": "station-01",
    "timestamp": "2025-07-25T12:30:00Z",
    "data": { ... },
    "prediction": 34
  },
  ...
]
```

* **500 Internal Server Error**: `{"status": "failed"}`

### GET `/get_current_data`

**Description**: Retrieves the latest sensor record.

* **URL**: `/get_current_data`
* **Method**: `GET`

#### Response

* **200 OK**: Single record object (same schema as above).
* **500 Internal Server Error**: `{"status": "failed"}`

### POST `/chat`

**Description**: Logs user message, queries AI for a response, and returns markdown.

* **URL**: `/chat`
* **Method**: `POST`
* **Headers**: `Content-Type: application/json`

#### Request Body

```json
{
  "_id": "<device_or_user_id>",
  "message": "How do I improve soil fertility in Terai?"
}
```

#### Response

* **200 OK**: Markdown string (`Content-Type: text/plain`)
* **500 Internal Server Error**: `{"status": "failed"}`

---

## Error Handling

* **500**: Generic failure. Check server logs (`log.txt`) for details.
* On database or AI errors, the service logs the exception and returns `status: failed`.

---

## Logging

All requests and errors are logged to `log.txt` with timestamp, log level, and message. Adjust `logging.basicConfig` as needed.

---

## Usage Examples

```bash
# Save data
curl -X POST http://127.0.0.1:5000/save_data \
     -H "Content-Type: application/json" \
     -d '{ "device_id": "station-01", "data": { "temperature": 25.1, "humidity": 55, ... } }'

# Get all data
curl http://127.0.0.1:5000/get_all_data

# Chat
curl -X POST http://127.0.0.1:5000/chat \
     -H "Content-Type: application/json" \
     -d '{ "_id": "245251", "message": "Best irrigation methods for maize?" }'
```

---