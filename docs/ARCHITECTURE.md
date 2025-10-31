# Architecture

## System Overview

vLLM Batch Server is a production-ready batch inference system for local LLMs with integrated data curation capabilities.

```
┌─────────────────┐
│  Aris Web App   │  (Next.js - sends conquest requests)
└────────┬────────┘
         │ HTTP POST /v1/batches
         ▼
┌─────────────────────────────────────────────────────────────┐
│  vLLM Batch API Server (Port 4080)                          │
│  - OpenAI-compatible batch API                              │
│  - SQLite job queue                                         │
│  - File management                                          │
└────────┬────────────────────────────────────────────────────┘
         │ Worker polls queue
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Batch Worker Process                                        │
│  - Processes jobs with vLLM                                 │
│  - GPU inference (RTX 4080 16GB)                            │
│  - Incremental result saving                                │
└────────┬────────────────────────────────────────────────────┘
         │ Auto-import results
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Label Studio (Port 4015)                                    │
│  - PostgreSQL backend                                       │
│  - Task storage                                             │
│  - Annotation database                                      │
└────────┬────────────────────────────────────────────────────┘
         │ API integration
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Curation API (Port 8001)                                    │
│  - FastAPI backend                                          │
│  - Conquest schema registry                                 │
│  - Bulk import endpoint                                     │
│  - Gold-star marking                                        │
└────────┬────────────────────────────────────────────────────┘
         │ Serves UI
         ▼
┌─────────────────────────────────────────────────────────────┐
│  Curation Web UI                                             │
│  - Beautiful gradient interface                             │
│  - Side-by-side model comparison                            │
│  - Training dataset export                                  │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. vLLM Batch API Server (`batch_app/api_server.py`)
- **Port**: 4080
- **Purpose**: OpenAI-compatible batch processing endpoint
- **Database**: SQLite (`data/vllm_batch.db`)
- **Features**:
  - Create batch jobs
  - Upload input files (JSONL)
  - Track job status
  - Download results
  - Webhook notifications

### 2. Batch Worker (`batch_app/worker.py`)
- **Purpose**: Background process that executes batch jobs
- **GPU**: RTX 4080 16GB
- **Models**: Gemma 3 4B, Qwen 2.5 3B, Llama 3.2 3B
- **Features**:
  - Polls job queue
  - Loads models with vLLM
  - Processes batches
  - Saves results incrementally
  - Auto-imports to Label Studio

### 3. Label Studio
- **Port**: 4015
- **Database**: PostgreSQL
- **Purpose**: Data annotation and storage backbone
- **Features**:
  - Task storage
  - Annotation interface
  - Project management
  - Export functionality

### 4. Curation API (`curation_app/api.py`)
- **Port**: 8001
- **Purpose**: Custom FastAPI layer over Label Studio
- **Features**:
  - Conquest schema registry
  - Bulk import endpoint
  - Schema prompt generation
  - Gold-star marking
  - Training dataset export

### 5. Conquest Schemas (`conquest_schemas/`)
- **Purpose**: Define data sources, questions, and rendering for each conquest type
- **Types**:
  - `candidate_evaluation` - Evaluate software engineers
  - `cv_parsing` - Extract structured data from resumes
  - `cartographer` - Map career journeys
  - `quil_email` - Generate recruiting emails
  - `email_evaluation` - Evaluate email quality
  - `report_evaluation` - Evaluate reports

## Data Flow

### Conquest Request → Training Dataset

1. **Aris sends conquest request** → vLLM Batch API (POST /v1/batches)
2. **Batch API creates job** → Stores in SQLite queue
3. **Worker picks up job** → Loads model, processes batch
4. **Worker saves results** → JSONL file in `data/batches/output/`
5. **Auto-import triggers** → Sends results to Label Studio
6. **Label Studio stores tasks** → PostgreSQL database
7. **Curation UI displays** → Beautiful web interface
8. **Human curates** → Corrects errors, marks gold-stars
9. **Export training data** → ICL examples or fine-tuning datasets

## Technology Stack

- **Python 3.13**
- **FastAPI** - Web framework
- **vLLM** - GPU inference engine
- **Label Studio** - Annotation platform
- **PostgreSQL** - Label Studio database
- **SQLite** - Batch job queue
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **Prometheus/Grafana** - Monitoring

## File Structure

```
vllm-batch-server/
├── batch_app/           # Batch API and worker
│   ├── api_server.py    # OpenAI-compatible API
│   ├── worker.py        # Background job processor
│   ├── database.py      # SQLite models
│   └── benchmarks.py    # Benchmarking tools
├── curation_app/        # Curation system
│   ├── api.py           # FastAPI backend
│   ├── conquest_schemas.py  # Schema registry
│   └── label_studio_client.py  # LS integration
├── conquest_schemas/    # Schema definitions (JSON)
├── static/              # Web UI assets
├── tests/               # Test suite
├── tools/               # Utility scripts
├── benchmarks/          # Benchmark results
├── data/                # Runtime data
│   ├── batches/         # Batch input/output
│   ├── files/           # Uploaded files
│   ├── results/         # Benchmark results
│   └── vllm_batch.db    # Job queue database
├── docs/                # Documentation
└── monitoring/          # Prometheus/Grafana configs
```

## Deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production deployment instructions.

## Integration

See [ARIS_INTEGRATION.md](ARIS_INTEGRATION.md) for Aris web app integration.

