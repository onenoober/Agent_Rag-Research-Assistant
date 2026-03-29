# Deployment Guide - Research Agent

## 1. Environment Setup

### 1.1 Prerequisites

- Python 3.11+
- Conda (recommended) or virtualenv
- Windows / Linux / macOS

### 1.2 Activate Environment

```bash
# Using conda
conda activate bigmodel

# Or using virtualenv
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows
```

### 1.3 Install Dependencies

```bash
pip install -r requirements.txt
```

## 2. Local Deployment

### 2.1 FastAPI Server

Start the FastAPI server:

```bash
cd src/agent/api
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### 2.2 Streamlit App

Start the Streamlit UI:

```bash
streamlit run src/apps/research_agent/app.py --server.port 8501
```

The Streamlit app will be available at:
- http://localhost:8501

## 3. Configuration

### 3.1 Settings File

Configuration is loaded from `config/settings.yaml`.

Key settings:

```yaml
llm:
  provider: azure
  model: gpt-4o
  temperature: 0.7
  max_tokens: 2048

embedding:
  provider: azure
  model: text-embedding-ada-002

vector_store:
  provider: chroma
  collection_name: knowledge_hub

retrieval:
  fusion_top_k: 10
```

### 3.2 Environment Variables

Optional environment variables:

```bash
# Override settings
export LLM_PROVIDER=azure
export LLM_API_KEY=your_key
export EMBEDDING_API_KEY=your_key
```

## 4. Testing

### 4.1 Run All Tests

```bash
pytest tests/ -v
```

### 4.2 Run Unit Tests

```bash
pytest tests/unit/ -v
```

### 4.3 Run Integration Tests

```bash
pytest tests/integration/ -v
```

### 4.4 Run E2E Tests

```bash
pytest tests/e2e/ -v
```

### 4.5 Run Specific Test File

```bash
pytest tests/unit/test_config.py -v
```

## 5. Troubleshooting

### 5.1 Common Issues

1. **Import Errors**
   - Ensure you're in the correct conda environment
   - Check PYTHONPATH includes project root

2. **Database Errors**
   - Check SQLite file permissions
   - Verify data directory exists

3. **API Connection Errors**
   - Check network connectivity
   - Verify API keys are correct

4. **Streamlit Errors**
   - Clear Streamlit cache: `streamlit cache clear`
   - Restart the Streamlit server

### 5.2 Logs

Logs are written to:
- Console (INFO level by default)
- File (if configured in settings)

## 6. Production Deployment

### 6.1 Considerations

- Set up proper authentication
- Configure SSL/TLS
- Set up monitoring and logging
- Use a production-grade database
- Configure rate limiting

### 6.2 Docker (Future)

```bash
docker build -t research-agent .
docker run -p 8000:8000 research-agent
```

## 7. Project Structure

```
src/
├── agent/
│   ├── infra/          # Config, logging, DB
│   ├── adapters/       # RAG, ingestion adapters
│   ├── schemas/        # Data schemas
│   ├── graph/          # LangGraph agent
│   ├── tools/          # Agent tools
│   ├── memory/         # Memory system
│   ├── services/       # Chat, stream services
│   └── api/           # FastAPI routes
└── apps/
    └── research_agent/ # Streamlit UI
        ├── components/
        └── pages/
```
