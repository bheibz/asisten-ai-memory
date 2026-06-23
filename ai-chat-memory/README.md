# 🧠 AI Chat with Long-Term Memory

Fast, token-efficient AI chat app dengan 3-tier memory architecture + **9Router proxy** sebagai LLM gateway. Auto-fallback ke SQLite + in-memory storage jika PostgreSQL/Redis/Qdrant tidak tersedia.

---

## 📋 Fitur

- **💬 Chat Streaming** — REST API + WebSocket real-time via 9Router
- **🧠 3-Tier Memory** — Working memory, Short-term summaries, Long-term vector search
- **⚡ Token-Optimized** — Smart retrieval, model routing, compression, response cache
- **🔀 Model Routing** — Otomatis pilih model sesuai complexity + category
- **🌐 Web Search** — Cari info real-time via DuckDuckGo (gratis, tanpa API key)
- **📝 Memory Command** — Perintah `ingat`, `lupa`, `perbaharui`, `ganti namaku/namamu` dari chat
- **🔍 Semantic Search** — Cari memory relevan pakai cosine similarity + keyword overlap
- **📉 Memory Decay** — Background task auto-cleanup memory yang jarang diakses
- **🔌 Auto-Fallback** — SQLite, in-memory cache, fake embeddings (tanpa service tambahan)
- **🕐 Tanggal & Waktu** — AI tahu tanggal/jam sekarang
- **🗑️ Hapus Percakapan** — Delete percakapan dari sidebar (×)
- **🗑️ Hapus Pesan** — Delete pesan langsung (hover → 🗑)
- **📥 Export Chat** — Download riwayat chat (.txt)
- **🔍 Cari Percakapan** — Search bar di sidebar
- **⏹ Stop Streaming** — Tombol batal saat AI mengetik
- **🌓 Dark/Light Mode** — Toggle tema
- **🕐 Timestamp** — Waktu otomatis di setiap pesan
- **🐳 Docker Ready** — Mode penuh pakai docker-compose (opsional)

---

## 🏗️ Arsitektur

```
┌──────────────────────────────────────────────────────────────┐
│                     CLIENT (REST / WebSocket)                  │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────────┐
│                    🧠 BRAIN ORCHESTRATOR                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐   │
│  │ Query    │  │ Memory   │  │ Prompt   │  │ Model     │   │
│  │ Classify │  │ Manager  │  │ Compiler │  │ Router    │   │
│  └──────────┘  └──────────┘  └──────────┘  └───────────┘   │
└──────────────────────────┬───────────────────────────────────┘
                           │
         ┌─────────────────┼──────────────────────┐
         ▼                 ▼                      ▼
┌──────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  9Router     │  │  MEMORY STORAGE  │  │  BACKEND TASKS   │
│  Proxy       │  │  ┌────────────┐  │  │  ┌────────────┐  │
│  ┌──────────┐│  │  │ SQLite/   │  │  │  │ Fact       │  │
│  │ OC/Deep- ││  │  │ Postgres  │  │  │  │ Extractor  │  │
│  │ Seek     ││  │  ├────────────┤  │  │  ├────────────┤  │
│  │ OC/Mimo  ││  │  │ Memory/   │  │  │  │ Compressor │  │
│  │ OC/North ││  │  │ Redis     │  │  │  ├────────────┤  │
│  │ OC/Big   ││  │  ├────────────┤  │  │  │ Decay      │  │
│  │ Pickle   ││  │  │ Local/    │  │  │  │ Engine     │  │
│  └──────────┘│  │  │ Qdrant    │  │  │  └────────────┘  │
└──────────────┘  │  └────────────┘  │  └──────────────────┘
                  └──────────────────┘
```

### Storage Auto-Fallback

| Service | Primary | Fallback | Aktif Ketika |
|---------|---------|----------|-------------|
| Database | PostgreSQL (port 5432) | SQLite (`data/aichat.db`) | PG tidak reachable |
| Cache | Redis (port 6379) | In-memory dict | Redis tidak reachable |
| Vector DB | Qdrant (port 6333) | In-memory + cosine sim | Qdrant tidak reachable |

---

## 🚀 Quick Start

### 1. Setup

```bash
cd ai-chat-memory
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install aiosqlite
```

Isi `.env` sudah include 9Router config (`http://localhost:20128`).

### 2. Migrate Database

```bash
source venv/bin/activate
PYTHONPATH="$PWD" python scripts/migrate_db.py
```

### 3. Jalankan App

```bash
source venv/bin/activate
PYTHONPATH="$PWD" python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Atau pakai script:

```bash
bash start.sh
```

### 4. Test

```bash
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"user_id": "user1", "conversation_id": "conv1", "message": "Halo! Siapa kamu?"}'
```

---

## 🧠 Model Routing

Menggunakan **9Router proxy** (`http://localhost:20128/v1`) dengan model:

| Complexity | Primary Model | Use Case |
|------------|---------------|----------|
| **simple** | `oc/north-mini-code-free` | Sapaan, thanks, pertanyaan pendek |
| **moderate** | `oc/mimo-v2.5-free` | Percakapan umum |
| **complex** | `oc/deepseek-v4-flash-free` | Coding, analisis, debugging |
| **creative** | `oc/big-pickle` | Writing, essay, konten panjang |
| **coding** | `oc/north-mini-code-free` | Pertanyaan coding (prioritas) |

> **Catatan:** Model yang tersedia tergantung 9Router proxy. Semua model `oc/*` adalah reasoning model — respons akan menampilkan proses berpikir AI. Gunakan model non-reasoning seperti `gpt-4o-mini` jika API key OpenAI tersedia.

---

## 💬 Memory Commands (dalam Chat)

Kamu bisa perintahkan AI langsung dari chat:

| Perintah | Contoh | Fungsi |
|----------|--------|--------|
| `ingat <isi>` | `ingat hutang budi 50000` | Simpan memory baru (otomatis update jika key sama) |
| `lupa <isi>` | `lupa hutang` | Hapus memory |
| `perbaharui <isi>` | `perbaharui hutang` | Update memory yang sudah ada |

**Cara kerja key:** AI pakai kata pertama sebagai key. Misal `ingat hutang budi 50000` → key=`hutang`, value=`hutang budi 50000`. Jika perintah `ingat` dengan key yang sama diulang, value akan di-update.

Lihat memory via endpoint: `GET /api/v1/memory/{user_id}`

---

## 🌐 Web Search

AI bisa search internet real-time pakai DuckDuckGo (gratis, tanpa API key). Otomatis terpicu jika chat mengandung kata kunci seperti: `cari`, `search`, `berita`, `info`, `siapa`, `apa itu`, dll.

**Contoh:**
```
Kamu: cari berita AI terbaru
AI:   [mencari dari DuckDuckGo...] memberikan hasil
```

Hasil search dimasukkan ke prompt sebagai `[WEB SEARCH RESULTS]` dan AI merespons berdasarkan data tersebut.

---

## 🔌 API Endpoints

### Chat

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/v1/chat` | Chat streaming (SSE) |
| `WS` | `/ws/chat/{user_id}` | Chat real-time WebSocket |
| `GET` | `/api/v1/conversations/{user_id}` | List percakapan user |
| `GET` | `/api/v1/conversations/{conv_id}/messages` | Lihat pesan percakapan |

### Memory

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/api/v1/memory/{user_id}` | Lihat apa yang AI ingat |
| `DELETE` | `/api/v1/memory/{user_id}/{fact_id}` | Hapus memory spesifik |
| `POST` | `/api/v1/memory/{user_id}/teach` | Ajari AI secara manual |

### User

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `POST` | `/api/v1/users` | Buat user baru |
| `GET` | `/api/v1/users/{user_id}` | Detail user |

### Health

| Method | Endpoint | Deskripsi |
|--------|----------|-----------|
| `GET` | `/` | Root info |
| `GET` | `/health` | Health check |

---

## 📂 Project Structure

```
ai-chat-memory/
├── app/
│   ├── main.py                    # FastAPI entry point + lifespan
│   ├── config.py                  # Pydantic settings (env vars)
│   ├── api/
│   │   ├── routes_chat.py         # Chat endpoints (REST + WebSocket)
│   │   ├── routes_memory.py       # Memory management
│   │   ├── routes_user.py         # User management
│   │   └── middleware.py          # Logging + rate limiting
│   ├── core/
│   │   ├── orchestrator.py        # 🧠 Brain - main pipeline
│   │   ├── query_classifier.py    # Rule-based query classification
│   │   ├── model_router.py        # Route ke model optimal
│   │   ├── prompt_compiler.py     # Build optimized prompts
│   │   └── token_counter.py       # Token tracking (tiktoken)
│   ├── memory/
│   │   ├── memory_manager.py      # Central memory controller
│   │   ├── working_memory.py      # Buffer pesan terbaru
│   │   ├── short_term.py          # Session summaries
│   │   ├── long_term.py           # Semantic memory (vector)
│   │   ├── compressor.py          # Summarize percakapan
│   │   ├── fact_extractor.py      # Extract facts from chat
│   │   └── decay_engine.py        # Memory decay & cleanup
│   ├── tools/
│   │   ├── web_search.py          # DuckDuckGo search (gratis)
│   │   └── __init__.py
│   ├── llm/
│   │   ├── gateway.py             # 9Router unified interface
│   │   ├── embeddings.py          # Embeddings + fake fallback
│   │   └── providers/             # Provider fallback
│   ├── db/
│   │   ├── models.py              # SQLAlchemy models
│   │   ├── database.py            # Auto-detect DB (SQLite/PG)
│   │   ├── postgres.py            # Database operations
│   │   ├── redis_client.py        # Redis + in-memory fallback
│   │   └── vector_store.py        # Qdrant + in-memory fallback
│   ├── utils/
│   │   ├── logger.py              # Structured logging
│   │   ├── hashing.py             # Cache key hashing
│   │   └── helpers.py             # Utility functions
│   └── workers/
│       └── memory_worker.py       # Background decay cycle
├── data/
│   └── aichat.db                  # SQLite database (auto-created)
├── scripts/
│   ├── migrate_db.py              # Create database tables
│   └── seed_data.py               # Seed demo data
├── start.sh                       # Quick start script
├── venv/                          # Python virtual env
├── docker-compose.yml             # Docker mode (opsional)
├── Dockerfile
├── requirements.txt
├── .env                           # Local config
└── .env.example                   # Template config
```

---

## 💰 Token Optimization Strategy

| Strategi | Penghematan | Cara Kerja |
|----------|-------------|------------|
| **🧠 3-Tier Memory** | ~70% token | Kirim hanya memory relevan |
| **🔀 Model Routing** | ~60% cost | Simple → model murah |
| **📦 Compression** | ~80% storage | Summarize percakapan lama |
| **⚡ Response Cache** | 100% (cache hit) | Response instant utk pertanyaan identik |
| **🔍 Semantic Search** | ~90% token | Top-3 relevant vs seluruh history |
| **📉 Memory Decay** | Storage savings | Auto-archive memory jarang diakses |
| **🏃 Async Post-process** | Faster UX | Extract facts SETELAH response |
| **📏 Rule-based Classifier** | 0 extra token | Classify tanpa panggil LLM |

---

## 🧪 Development

```bash
# Aktifkan venv
source venv/bin/activate
export PYTHONPATH="$PWD"

# Jalankan (setelah edit kode)
uvicorn app.main:app --reload

# Seed data demo
python scripts/seed_data.py

# Lihat log
tail -f /tmp/aichat.log
```

### Environment Variables (.env)

| Variable | Default | Deskripsi |
|----------|---------|-----------|
| `NINE_ROUTER_BASE_URL` | `http://localhost:20128/v1` | 9Router proxy URL |
| `NINE_ROUTER_API_KEY` | `sk-...` | 9Router API key |
| `DATABASE_URL` | `postgresql+asyncpg://...` | PostgreSQL (auto-fallback SQLite) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis (auto-fallback in-memory) |
| `QDRANT_URL` | `http://localhost:6333` | Qdrant (auto-fallback in-memory) |
| `AI_NAME` | `Clara` | Nama AI asisten |
| `DEFAULT_MODEL` | `oc/north-mini-code-free` | Model default |
| `EMBEDDING_MODEL` | `text-embedding-ada-002` | Model embedding (butuh OpenAI key) |
| `OPENAI_API_KEY` | `""` | API key OpenAI |
| `ANTHROPIC_API_KEY` | `""` | API key Anthropic |

---

## 📦 Changelog

### v1.2.0

- **🗑️ Hapus percakapan** — Delete via sidebar + API endpoint
- **🗑️ Hapus pesan** — Delete per-message via hover menu
- **📥 Export chat** — Download riwayat sebagai .txt
- **🔍 Cari percakapan** — Search/filter di sidebar
- **⏹ Cancel streaming** — AbortController + tombol stop
- **🌓 Dark/Light mode** — Toggle + localStorage persist
- **🕐 Timestamp** — Waktu dikirim di setiap pesan
- **🎨 Markdown improved** — Bold, italic, header rendering
- **🧠 Memory decay** — Background task otomatis (asyncio)
- **🔌 Auto-create user** — User auto-created di memory commands
- **🧠 Memory recall** — Keyword overlap + retrieve_all fallback
- **🔍 Search patterns** — "cek di internet", "bisa cek" dll trigger web search
- **🕐 Time query** — Tanggal/jam sekarang dari server
- **🐛 Regex ganti_nama** — "aku ganti nama kamu x ya" diperbaiki
- **🐛 Reasoning model** — Streaming via reasoning_content di-gateway

### v1.1.0

- **🧠 Memory recall diperbaiki** — AI selalu cari memory relevan, gak cuma saat ada trigger word
- **🔍 Keyword overlap scoring** — Fallback saat fake embedding, memory tetap ditemukan via kata kunci
- **✂️ Fact extractor rewrite** — Pindah dari LLM ke rule-based, cuma ambil dari user_msg (gak ambil dari response AI)
- **🆔 Payload `id` field** — Semua upsert sekarang include `id`, boost memory berfungsi
- **🔌 Auto-conversation** — Title otomatis dari pesan pertama, conversation auto-created
- **🌐 WebSearch async** — Dibungkus `asyncio.to_thread()`, gak blocking event loop
- **📦 MemoryStore cleanup** — Auto-purge expired keys, limit 10k entries
- **🪟 Memory modal** — Ganti `window.open` jadi modal dalam halaman (gak kena popup blocker)
- **📄 favicon.ico** — 404 jadi 200
- **🐛 Critical fixes** — `Message.id` + `SessionSummary.id` missing `default=gen_id` → crash (✅ fixed)

---

## 🔧 Troubleshooting

**Q: 9Router proxy tidak connect?**
```
curl http://localhost:20128/v1/models
Pastikan 9Router sudah running di port 20128.
```

**Q: ModuleNotFoundError saat run?**
```
source venv/bin/activate
export PYTHONPATH="$PWD"
```

**Q: Chat response "[... provider not configured]"?**
```
Cek NINE_ROUTER_BASE_URL dan NINE_ROUTER_API_KEY di .env
```

**Q: Embedding error (OpenAI)?**
```
Auto-fallback ke fake embeddings (hash-based).
Tanpa OpenAI key, semantic search via cosine similarity tetap jalan.
```

**Q: Memory modal tidak muncul?**
```
Pastikan tidak ada popup blocker. Modal tampil di dalam halaman,
bukan window baru — jadi seharusnya tidak diblokir.
```

**Q: Web search tidak jalan?**
```
Pastikan duckduckgo_search terinstall:
pip install duckduckgo_search
Test: python -c "from duckduckgo_search import DDGS; print(list(DDGS().text('test', max_results=1)))"
```

**Q: Mau pake PostgreSQL/Redis/Qdrant?**
```
docker-compose up -d postgres redis qdrant
# App akan auto-detect dan pakai service tersebut
```

---

## 📄 License

MIT
