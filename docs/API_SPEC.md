# API Specification - Research Agent

## 1. Overview

The Research Agent API provides endpoints for interacting with the RAG-powered research assistant.

## 2. Base URL

```
http://localhost:8000/api
```

## 3. Authentication

Currently no authentication is required (development mode).

## 4. Endpoints

### 4.1 Health Check

**GET** `/health`

Check system health status.

**Response:**

```json
{
  "status": "healthy",
  "app": {
    "status": "running",
    "version": "1.0.0"
  },
  "config": {
    "status": "loaded",
    "llm_provider": "azure",
    "vector_store": "chroma"
  },
  "db": {
    "status": "connected",
    "tables": ["chat_history", "user_preferences"]
  }
}
```

### 4.2 Chat

**POST** `/chat`

Send a chat message and get a response.

**Request:**

```json
{
  "query": "What is hybrid search?",
  "session_id": "user_123",
  "temperature": 0.7,
  "max_tokens": 2048
}
```

**Response:**

```json
{
  "answer": "Hybrid search is...",
  "session_id": "user_123",
  "tool_steps": [
    {
      "tool": "rag_search",
      "status": "success",
      "result": "Found 5 chunks"
    }
  ],
  "citations": [
    {
      "chunk_id": "chunk_123",
      "text": "Hybrid search combines...",
      "source": "doc1.pdf",
      "score": 0.95
    }
  ],
  "metadata": {
    "total_tokens": 1500,
    "model": "gpt-4o"
  }
}
```

### 4.3 Chat Stream

**POST** `/chat/stream`

Send a chat message and get a streaming response.

**Request:** Same as `/chat`

**Streamed Response**

Follows Server-Sent Events (SSE) format.

**Events:**

- `start`: Session started
- `tool_step`: Tool execution step
- `token`: Token chunk
- `citation`: Citation source
- `done`: Completion
- `error`: Error occurred

## 5. Error Handling

All errors return JSON with error details:

```json
{
  "error": "Error message",
  "code": "ERROR_CODE",
  "details": {}
}
```

## 6. Rate Limiting

No rate limiting in development mode.
