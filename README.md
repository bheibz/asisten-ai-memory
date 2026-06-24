# 🧠 Asisten AI Memory

**AI Chat Assistant dengan Long-Term Memory Architecture** — Fast, Token-Efficient & Self-Improving.

> 📌 **Status**: Work-In-Progress (WIP) | Architecture: Planned | Core: In Development

---

## 🎯 Visi

Membangun AI assistant yang:
- **Mengingat** konteks percakapan jangka panjang (3-tier memory)
- **Hemat token** melalui smart retrieval & model routing
- **Responsif** dengan streaming real-time via WebSocket
- **Scalable** dengan fallback otomatis (SQLite/Redis/Qdrant)
- **Intelligent** dengan semantic search & fact extraction

---

## ✨ Fitur (Planned)

### 💬 Chat & Memory
- [x] REST API chat endpoint
- [x] WebSocket real-time chat
- [x] 3-Tier memory system (working/short-term/long-term)
- [x] Auto-create conversations & messages
- [x] Semantic search memory via embeddings
- [x] Memory decay & cleanup engine
- [ ] Custom memory commands (ingat, lupa, perbaharui)
- [ ] Knowledge base (simpan catatan)

### 🧠 Intelligence
- [x] Query classifier (rule-based)
- [x] Smart model routing (simple → cheap, complex → smart)
- [x] Prompt optimizer (token-efficient compilation)
- [x] Token counter & tracking
- [ ] Fact extraction & storage
- [ ] Conversation compression
- [ ] Context-aware web search

### 🔌 LLM Gateway
- [x] 9Router proxy integration (`http://localhost:20128`)
- [x] Model fallback system
- [ ] OpenAI integration
- [ ] Anthropic (Claude) integration
- [ ] Local LLM support (Ollama)

### 💾 Storage
- [x] Auto-fallback: PostgreSQL → SQLite
- [x] Auto-fallback: Redis → In-memory
- [x] Auto-fallback: Qdrant → Fake embeddings
- [x] Database migrations
- [ ] Connection pooling optimization

### 🌐 Additional Features
- [ ] Web search (DuckDuckGo)
- [ ] File upload & parsing
- [ ] Response caching
- [ ] Rate limiting
- [ ] User authentication
- [ ] Admin dashboard

---

## 🏗️ Arsitektur

```
┌─────────────────────────────────────────────┐
│         CLIENT (REST / WebSocket)           │
└────────────────┬────────────────────────────┘
                 │
┌────────────────▼────────────────────────────┐
│       🧠 BRAIN ORCHESTRATOR                 │
│  ┌──────────┐ ┌──────────┐ ┌────────────┐  │
│  │  Query   │ │ Memory   │ │  Prompt    │  │
│  │Classifier│ │ Manager  │ │ Compiler   │  │
│  └──────────┘ └──────────┘ └────────────┘  │
└────────────────┬────────────────────────────┘
                 │
    ┌────────────┼────────────┐
    ▼            ▼            ▼
┌──────────┐ ┌─────────┐ ┌─────────┐
│9Router   │ │ MEMORY  │ │TOOLS &  │
│Gateway   │ │STORAGE  │ │SERVICES │
└──────────┘ └─────────┘ └─────────┘
```

### Memory 3-Tier
| Tier | Storage | Purpose | TTL | Speed |
|------|---------|---------|-----|-------|
| **Working** | Redis | Recent messages (last 3-5) | 30 min | ⚡ Ultra |
| **Short-term** | PostgreSQL | Session summaries | 7-30 hari | 🔄 Medium |
| **Long-term** | Qdrant | Extracted facts & semantic | Permanent | 💾 Slower |

---

## 🚀 Quick Start

### 1. Clone & Setup
```bash
cd asisten-ai-memory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Database Migration
```bash
export PYTHONPATH="$PWD"
python scripts/migrate_db.py
```

### 3. Configure .env
```bash
# Copy from template
cp .env.example .env

# Edit dengan config Anda:
NINE_ROUTER_BASE_URL=http://localhost:20128/v1
NINE_ROUTER_API_KEY=your-key-here
DATABASE_URL=postgresql+asyncpg://user:pass@localhost/aichat
# (optional - fallback ke SQLite jika tidak ada)
```

### 4. Run Server
```bash
# Option A: Direct
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Option B: Bash script
bash start.sh
```

### 5. Test Chat
```bash
# REST API
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user1",
    "conversation_id": "conv1",
    "message": "Halo! Siapa kamu?"
  }'

# WebSocket (gunakan tool seperti wscat)
wscat -c ws://localhost:8000/ws/chat/user1
```

---

## 📚 API Endpoints

### Chat
| Method | Endpoint | Status |
|--------|----------|--------|
| `POST` | `/api/v1/chat` | ✅ Implemented |
| `WS` | `/ws/chat/{user_id}` | ✅ Implemented |
| `GET` | `/api/v1/conversations/{user_id}` | ✅ Implemented |
| `GET` | `/api/v1/conversations/{conv_id}/messages` | ✅ Implemented |
| `DELETE` | `/api/v1/conversations/{conv_id}` | 🔄 In Progress |

### Memory
| Method | Endpoint | Status |
|--------|----------|--------|
| `GET` | `/api/v1/memory/{user_id}` | ✅ Implemented |
| `DELETE` | `/api/v1/memory/{user_id}/{fact_id}` | 🔄 Planned |
| `POST` | `/api/v1/memory/{user_id}/teach` | 🔄 Planned |

### User
| Method | Endpoint | Status |
|--------|----------|--------|
| `POST` | `/api/v1/users` | 🔄 Planned |
| `GET` | `/api/v1/users/{user_id}` | 🔄 Planned |

### Health
| Method | Endpoint | Status |
|--------|----------|--------|
| `GET` | `/` | ✅ Implemented |
| `GET` | `/health` | ✅ Implemented |

---

## 📂 Project Structure

```
asisten-ai-memory/
├── app/
│   ├── main.py                 # FastAPI entry point + lifespan
│   ├── config.py               # Pydantic settings (env vars)
│   ├── api/
│   │   ├── routes_chat.py      # Chat endpoints
│   │   ├── routes_memory.py    # Memory endpoints
│   │   ├── routes_user.py      # User endpoints
│   │   └── middleware.py       # Logging, rate limiting
│   ├── core/
│   │   ├── orchestrator.py     # 🧠 Main pipeline
│   │   ├── query_classifier.py # Rule-based classification
│   │   ├── model_router.py     # Model selection
│   │   ├── prompt_compiler.py  # Prompt building
│   │   └── token_counter.py    # Token tracking
│   ├── memory/
│   │   ├── memory_manager.py   # Central memory controller
│   │   ├── working_memory.py   # Redis buffer
│   │   ├── short_term.py       # PostgreSQL summaries
│   │   ├── long_term.py        # Vector DB (Qdrant)
│   │   ├── compressor.py       # Conversation compression
│   │   ├── fact_extractor.py   # Extract facts
│   │   └── decay_engine.py     # Memory cleanup
│   ├── llm/
│   │   ├── gateway.py          # 9Router unified interface
│   │   ├── embeddings.py       # Embeddings + fallback
│   │   └── providers/          # LLM provider integrations
│   ├── db/
│   │   ├── models.py           # SQLAlchemy models
│   │   ├── database.py         # Auto-detect DB
│   │   ├── postgres.py         # PostgreSQL ops
│   │   ├── redis_client.py     # Redis + fallback
│   │   └── vector_store.py     # Qdrant + fallback
│   ├── tools/
│   │   ├── web_search.py       # Web search (planned)
│   │   └── __init__.py
│   ├── utils/
│   │   ├── logger.py           # Structured logging
│   │   ├── hashing.py          # Cache key hashing
│   │   └── helpers.py          # Utilities
│   └── workers/
│       └── memory_worker.py    # Background decay task
├── data/
│   └── aichat.db              # SQLite (auto-created)
├── scripts/
│   ├── migrate_db.py          # Database setup
│   └── seed_data.py           # Demo data
├── tests/                     # Unit & integration tests
├── docker-compose.yml         # Service orchestration
├── Dockerfile
├── requirements.txt
├── start.sh                   # Quick start script
├── .env                       # Local config
├── .env.example               # Config template
└── README.md
```

---

## ⚙️ Configuration

### Environment Variables (.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `NINE_ROUTER_BASE_URL` | `http://localhost:20128/v1` | 9Router API URL |
| `NINE_ROUTER_API_KEY` | `sk-...` | 9Router API key |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL (fallback: SQLite) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis (fallback: in-memory) |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant (fallback: fake embeddings) |
| `OPENAI_API_KEY` | (empty) | For embeddings |
| `ANTHROPIC_API_KEY` | (empty) | For Claude support |
| `AI_NAME` | `Clara` | Assistant name |
| `DEFAULT_MODEL` | `oc/north-mini-code-free` | Default LLM |
| `LOG_LEVEL` | `INFO` | Logging level |

---

## 🧪 Development

### Activate Environment
```bash
source venv/bin/activate
export PYTHONPATH="$PWD"
```

### Run with Auto-reload
```bash
uvicorn app.main:app --reload
```

### Seed Demo Data
```bash
python scripts/seed_data.py
```

### View Logs
```bash
tail -f /tmp/aichat.log
```

### Run Tests (future)
```bash
pytest tests/
```

---

## 🐳 Docker Deployment (Optional)

### Full Stack with Services
```bash
docker-compose up -d postgres redis qdrant
# App will auto-detect and use these services
docker-compose up -d app
```

### Single Container (SQLite mode)
```bash
docker build -t asisten-ai .
docker run -p 8000:8000 -e NINE_ROUTER_API_KEY=your-key asisten-ai
```

---

## 🧠 How It Works

### Query Processing Pipeline

```
User Message
    │
    ├─► Classify (simple/moderate/complex)
    │
    ├─► Check Cache (Redis)
    │   └─► Return if hit
    │
    ├─► Retrieve Memories (parallel)
    │   ├─► Working memory (last 3-5 messages from Redis)
    │   ├─► Relevant memories (semantic search from Qdrant)
    │   └─► User profile (cached context)
    │
    ├─► Compile Prompt (token-optimized)
    │   └─► Build messages array
    │
    ├─► Route to Model
    │   └─► simple → cheap, complex → smart
    │
    ├─► Stream Response
    │   └─► Send chunks in real-time
    │
    └─► Post-Process (async, non-blocking)
        ├─► Save messages
        ├─► Update working memory
        ├─► Extract & store facts
        ├─► Compress if needed
        └─► Cache response
```

### Memory Retrieval

1. **Working Memory**: Ultra-fast lookup of last 3-5 messages from Redis
2. **Semantic Search**: Query embedding → Qdrant vector search → Top-K relevant facts
3. **Fallback**: If embeddings fail, use keyword overlap scoring

### Model Selection

| Query | Complexity | Model | Cost |
|-------|-----------|-------|------|
| "Hi!" | simple | `oc/north-mini-code-free` | ✅ Cheap |
| "How do I learn Python?" | moderate | `oc/north-mini-code-free` | ✅ Cheap |
| "Build a full-stack app architecture" | complex | `oc/deepseek-v4-flash` | 🔄 Medium |
| Factual question | complex | `oc/deepseek-v4-flash` + web search | 🔄 Medium |

---

## 🔧 Troubleshooting

### 9Router Connection Error
```bash
# Check if 9Router is running
curl http://localhost:20128/v1/models

# If failed, start 9Router first or configure NINE_ROUTER_BASE_URL
```

### ModuleNotFoundError
```bash
source venv/bin/activate
export PYTHONPATH="$PWD"
```

### Database Connection Failed
```bash
# App auto-fallback ke SQLite
# Check .env DATABASE_URL or leave empty for SQLite

# To use PostgreSQL:
docker-compose up -d postgres
# Update DATABASE_URL in .env
python scripts/migrate_db.py
```

### Embedding Error
```bash
# App auto-fallback ke fake embeddings
# Semantic search will use keyword matching instead
```

### Memory not found
```bash
# Check if Redis is running
redis-cli ping
# If failed, app uses in-memory storage
```

---

## 📋 Roadmap

### Phase 1: Core (Current)
- [x] FastAPI setup
- [x] Chat endpoints (REST + WebSocket)
- [x] 3-Tier memory architecture
- [x] Query classifier
- [x] Model router
- [x] Auto-fallback system
- [ ] Fact extraction

### Phase 2: Intelligence
- [ ] Web search integration
- [ ] Conversation compression
- [ ] Memory decay optimization
- [ ] Context-aware responses

### Phase 3: UX & Features
- [ ] Memory commands (ingat, lupa)
- [ ] Knowledge base (simpan catatan)
- [ ] File upload & parsing
- [ ] Export chat history

### Phase 4: Production
- [ ] Authentication & authorization
- [ ] Rate limiting
- [ ] Admin dashboard
- [ ] Analytics & monitoring
- [ ] Deployment guides

---

## 🤝 Contributing

Kontribusi welcome! Untuk mulai:

1. Fork repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

### Development Setup
```bash
pip install -r requirements-dev.txt  # includes pytest, black, mypy
pre-commit install  # auto-format & lint
```

---

## 📝 License

MIT License — See LICENSE file for details

---

## 🙋 Support & Questions

- **Issues**: Report bugs on GitHub Issues
- **Discussions**: Ask questions on GitHub Discussions
- **Email**: (contact info if available)

---

**Made with 🧠 by [bheibz](https://github.com/bheibz)**
