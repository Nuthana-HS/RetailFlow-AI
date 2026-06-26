# RetailFlow AI — High-Level Design (HLD)

**Version:** 1.0.0  
**Status:** Approved  
**Author:** RetailFlow AI — Technical Architecture Team  
**Linked to:** PRD v1.0.0  

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture Style](#2-architecture-style)
3. [Component Architecture](#3-component-architecture)
4. [Service Descriptions](#4-service-descriptions)
5. [Data Flow Architecture](#5-data-flow-architecture)
6. [Real-Time Architecture](#6-real-time-architecture)
7. [AI/ML Pipeline Architecture](#7-aiml-pipeline-architecture)
8. [Technology Choices & Justifications](#8-technology-choices--justifications)
9. [Security Architecture](#9-security-architecture)
10. [Deployment Architecture](#10-deployment-architecture)
11. [Scalability Strategy](#11-scalability-strategy)
12. [Failure Modes & Resilience](#12-failure-modes--resilience)

---

## 1. System Overview

RetailFlow AI is composed of **four independently deployable services** that communicate through well-defined interfaces:

```
┌─────────────────────────────────────────────────────────┐
│                    CLIENT LAYER                         │
│  ┌──────────────────┐    ┌──────────────────────────┐  │
│  │  Manager/Admin   │    │    Customer App           │  │
│  │  Dashboard       │    │    (Public View)          │  │
│  │  (Next.js SSR)   │    │    (Next.js SSR)          │  │
│  └────────┬─────────┘    └────────────┬─────────────┘  │
└───────────┼──────────────────────────┼─────────────────┘
            │ HTTPS + WSS              │ HTTPS
┌───────────▼──────────────────────────▼─────────────────┐
│                   BACKEND LAYER                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │          Core API Service (FastAPI)             │   │
│  │  - Auth Module    - Store Module                │   │
│  │  - Queue Module   - Analytics Module            │   │
│  │  - Notification   - WebSocket Hub               │   │
│  └──────────┬──────────────────────────────────────┘   │
└─────────────┼───────────────────────────────────────────┘
              │
┌─────────────┼───────────────────────────────────────────┐
│             │     DATA LAYER                            │
│  ┌──────────▼──────┐    ┌──────────────────────────┐   │
│  │  PostgreSQL      │    │  Redis                   │   │
│  │  (Primary DB)    │    │  - Queue state cache     │   │
│  │                  │    │  - Pub/Sub channels       │   │
│  └──────────────────┘    │  - Session/Rate limit    │   │
│                          └──────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
              │
┌─────────────┼───────────────────────────────────────────┐
│             │     AI LAYER                              │
│  ┌──────────▼──────────────────────────────────────┐   │
│  │       AI Service (FastAPI)                      │   │
│  │  ┌─────────────────┐  ┌───────────────────────┐ │   │
│  │  │ CV Module        │  │ ML Module             │ │   │
│  │  │ YOLOv8 + OpenCV  │  │ XGBoost Predictor     │ │   │
│  │  └─────────────────┘  └───────────────────────┘ │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Architecture Style

### Decision: Modular Monolith → Microservices-Ready

**Chosen Pattern:** Modular Monolith with clear service boundaries

**Rationale:**

| Option | Pros | Cons | Decision |
|---|---|---|---|
| Full Microservices | Perfect isolation, independent scaling | Operational complexity, network latency, hard to debug | ❌ Too early |
| Monolith | Simple to develop and deploy | Tight coupling, hard to scale specific components | ❌ Not scalable |
| **Modular Monolith** | **Separation of concerns, single deployment, easy to split later** | **Needs disciplined module boundaries** | **✅ Chosen** |

The Core API and AI Service are kept as **separate deployable units** because:
1. AI/CV workloads require GPU resources — different hardware profile
2. AI service can be updated independently without redeploying the API
3. This mirrors how real production systems are structured at companies like Zomato, Swiggy

---

## 3. Component Architecture

### 3.1 Frontend — Next.js App Router

```
frontend/
├── app/
│   ├── (auth)/           # Login, Register pages (unauthenticated)
│   ├── (dashboard)/      # Manager/Admin views (protected)
│   │   ├── dashboard/    # Live counter view
│   │   ├── stores/       # Store management
│   │   ├── analytics/    # Reports & heatmaps
│   │   └── settings/     # Alert config, profile
│   └── (public)/         # Customer-facing pages (no login)
│       └── store/[id]/   # Customer queue view
├── components/           # Reusable UI components
├── hooks/                # Custom React hooks (useQueue, useWebSocket)
├── lib/                  # API client, auth utilities
├── store/                # Zustand global state
└── types/                # TypeScript type definitions
```

**Key Frontend Decisions:**
- **App Router (not Pages Router):** Enables React Server Components → faster initial load, better SEO for customer-facing pages
- **Zustand (not Redux):** Lighter weight, less boilerplate for this scale. Redux is overkill without very complex shared state
- **React Query (TanStack):** Server state management for API calls with automatic caching, refetching, and background sync
- **shadcn/ui:** Component library based on Radix primitives — accessible, themeable, no lock-in (components are copied into project, not imported)
- **Chart.js:** Mature, widely understood charting library. Recharts was considered but Chart.js has better animation support

---

### 3.2 Backend — FastAPI Core API

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth/         # Auth router, dependencies
│   │       ├── stores/       # Store & counter routers
│   │       ├── queues/       # Queue engine routers
│   │       ├── analytics/    # Analytics routers
│   │       └── notifications/# Notification routers
│   ├── core/
│   │   ├── config.py         # Settings (pydantic-settings)
│   │   ├── security.py       # JWT utils, password hashing
│   │   ├── database.py       # SQLAlchemy engine, session
│   │   └── redis.py          # Redis client factory
│   ├── models/               # SQLAlchemy ORM models
│   ├── schemas/              # Pydantic request/response schemas
│   ├── services/             # Business logic layer
│   ├── repositories/         # Data access layer (repository pattern)
│   ├── websocket/            # WebSocket connection manager
│   └── main.py               # FastAPI app factory
├── alembic/                  # Database migrations
└── tests/                    # Test suite
```

**Key Backend Decisions:**
- **FastAPI over Django/Flask:** Native async, automatic OpenAPI docs, Pydantic integration, 3× faster than Flask for I/O bound workloads
- **Repository Pattern:** Decouples business logic from data access. Makes testing trivial (mock the repository). Industry standard in clean architecture
- **Dependency Injection (FastAPI `Depends`):** All services receive their dependencies injected — no global state, highly testable
- **Alembic for migrations:** Never modify the database schema directly in production. All changes tracked, reversible, and version-controlled
- **Pydantic v2:** All request/response data validated at the boundary. Type errors are caught before they reach business logic

---

### 3.3 AI Service — FastAPI AI

```
ai-service/
├── app/
│   ├── cv/
│   │   ├── detector.py       # YOLOv8 inference engine
│   │   ├── zone_manager.py   # ROI zone configuration
│   │   └── stream.py         # Video stream handler
│   ├── ml/
│   │   ├── predictor.py      # XGBoost wait time predictor
│   │   ├── trainer.py        # Model training pipeline
│   │   └── features.py       # Feature engineering
│   ├── api/
│   │   └── v1/               # AI service REST API
│   └── main.py
├── models/                   # Serialized model files (.pkl, .pt)
└── tests/
```

**Key AI Architecture Decisions:**
- **Separate service:** CV inference is CPU/GPU intensive. Keeping it separate prevents queue update latency from being affected by inference time
- **Push model (not poll):** CV service pushes detected counts to Core API every 5 seconds. Core API doesn't poll CV service. This is more efficient and decoupled
- **Model versioning:** Models stored with version numbers. Rollback possible without code changes
- **Redis cache for predictions:** ML predictions cached for 30 seconds in Redis to avoid redundant inference on rapidly changing queues

---

### 3.4 Database Layer

**Primary Database: PostgreSQL 16**
- Chosen for: ACID compliance, complex JOIN queries for analytics, mature ecosystem, Neon PostgreSQL for serverless hosting
- NOT a NoSQL DB: Queue history is relational data — counters belong to stores, snapshots belong to counters. Relational model is correct here

**Cache + Pub/Sub: Redis 7**
- **Cache:** Current queue state per counter (sub-millisecond reads vs. 50ms DB reads)
- **Pub/Sub:** WebSocket events. When queue updates, it's published to a Redis channel. All WebSocket servers subscribed to that channel broadcast to connected clients
- **Why Redis Pub/Sub over Kafka:** Kafka is appropriate at millions of events/second. Redis Pub/Sub handles our 1,000 events/second target with far less operational complexity

---

## 4. Service Descriptions

| Service | Technology | Port | Responsibility |
|---|---|---|---|
| `frontend` | Next.js 14 | 3000 | UI for all user types |
| `backend` | FastAPI + Python 3.12 | 8000 | Core business logic, REST API, WebSocket |
| `ai-service` | FastAPI + Python 3.12 | 8001 | CV inference, ML prediction |
| `postgres` | PostgreSQL 16 | 5432 | Persistent relational data |
| `redis` | Redis 7 | 6379 | Cache, pub/sub, rate limiting |

---

## 5. Data Flow Architecture

### 5.1 Manual Queue Update Flow

```
Cashier/Manager
      │
      │ PATCH /api/v1/queues/{counter_id}
      ▼
  FastAPI Backend
      │
      ├─── 1. Validate JWT + RBAC
      ├─── 2. Validate request body (Pydantic)
      ├─── 3. Write to PostgreSQL (queue_snapshots)
      ├─── 4. Update Redis cache (SET queue:{counter_id})
      └─── 5. Publish to Redis channel (queue:store:{store_id})
                        │
                        │ Redis Pub/Sub
                        ▼
              WebSocket Connection Manager
                        │
                        │ Broadcast to all connected clients
                        ▼
              Manager Dashboard (live update)
              Customer App (live update)
```

### 5.2 Computer Vision Auto-Update Flow

```
CCTV Camera / Webcam
      │
      │ Video frames
      ▼
  AI Service (YOLOv8)
      │
      ├─── 1. Capture frame every 500ms
      ├─── 2. Run YOLO inference (detect persons)
      ├─── 3. Filter by ROI zone
      ├─── 4. Count persons in zone
      └─── 5. POST /api/v1/queues/{counter_id}/cv-update (every 5s)
                        │
                        ▼ (same as manual update flow above)
              PostgreSQL + Redis + WebSocket broadcast
```

---

## 6. Real-Time Architecture

### WebSocket Design

```
Client (Browser)
    │
    │ WSS /ws/store/{store_id}
    ▼
FastAPI WebSocket Handler
    │
    ├── 1. Authenticate via token query param
    ├── 2. Register connection in ConnectionManager
    └── 3. Subscribe to Redis channel queue:store:{store_id}
                │
                │ (Background async task per connection)
                ▼
        Redis Pub/Sub Listener
                │
                │ On message → forward to WebSocket client
                ▼
        Browser receives JSON payload:
        {
          "event": "queue_update",
          "counter_id": "...",
          "queue_length": 5,
          "ewt_minutes": 3.5,
          "timestamp": "..."
        }
```

**Connection Manager Design:**
- Dict keyed by `store_id → List[WebSocket]`
- On connection: append to list
- On disconnect: remove from list, clean up Redis subscription
- Handles graceful disconnection, reconnection events

---

## 7. AI/ML Pipeline Architecture

### 7.1 Computer Vision Pipeline

```
Video Input → Frame Capture → Preprocessing → YOLOv8 Inference
                                                     │
                                              ┌──────▼──────┐
                                              │ Detections  │
                                              │ (bounding   │
                                              │  boxes)     │
                                              └──────┬──────┘
                                                     │
                                             ROI Filtering
                                             (only count
                                              persons in
                                              queue zone)
                                                     │
                                             Count Aggregation
                                                     │
                                             Push to Core API
                                             (every 5 seconds)
```

### 7.2 ML Prediction Pipeline

```
Request arrives at /api/v1/queues/{counter_id}/predict
                │
                ▼
    Check Redis cache (30s TTL)
    ├── Cache HIT → Return cached prediction
    └── Cache MISS →
              │
              ▼
    Feature Engineering:
    - queue_length (from Redis)
    - hour_of_day (from system time)
    - day_of_week (from system time)
    - num_open_counters (from Redis store state)
    - store_avg_service_time (from PostgreSQL, cached)
              │
              ▼
    XGBoost Model Inference
              │
              ▼
    Post-processing:
    - Clamp predictions (min: 0, max: 60 minutes)
    - Calculate confidence interval
              │
              ▼
    Cache in Redis (30s TTL)
              │
              ▼
    Return: { ewt_minutes, confidence, method: "ml" }
```

---

## 8. Technology Choices & Justifications

| Technology | Alternative Considered | Why Chosen |
|---|---|---|
| **Next.js 14 (App Router)** | Vite + React SPA | SSR for customer pages, built-in routing, production-proven |
| **FastAPI** | Django REST, Flask | Native async/await, auto OpenAPI, 3× faster, Pydantic native |
| **PostgreSQL** | MySQL, MongoDB | ACID, complex analytics queries, JSON support, Neon cloud hosting |
| **Redis** | Memcached, RabbitMQ | Pub/Sub + caching in one tool, extremely fast, battle-tested |
| **YOLOv8 (Ultralytics)** | MediaPipe, DETR | Best accuracy/speed tradeoff, excellent Python SDK, pre-trained weights |
| **XGBoost** | scikit-learn RandomForest, LightGBM | Handles tabular data best, interpretable, production-proven in retail ML |
| **SQLAlchemy 2.0** | Tortoise ORM, raw SQL | Mature, async support in v2, excellent migration tooling via Alembic |
| **Docker Compose** | Kubernetes | Appropriate for single-server deployment; K8s overkill for initial scale |
| **shadcn/ui** | Material UI, Ant Design | No lock-in (code ownership), Radix primitives (accessible), fully customizable |
| **Zustand** | Redux Toolkit | Simpler API, less boilerplate, sufficient for our state complexity |
| **React Query** | SWR, Apollo | Excellent caching, background sync, devtools, mutation handling |

---

## 9. Security Architecture

### 9.1 Authentication Flow

```
User → POST /auth/login
              │
              ▼
    Verify email/password (bcrypt compare)
              │
              ▼
    Generate:
    ┌─────────────────────────────────────────────┐
    │ Access Token (JWT)                          │
    │ - Payload: {user_id, email, role, store_ids}│
    │ - Expiry: 15 minutes                        │
    │ - Stored: Memory (JS variable)              │
    └─────────────────────────────────────────────┘
    ┌─────────────────────────────────────────────┐
    │ Refresh Token (Opaque UUID)                 │
    │ - Hashed and stored in DB                   │
    │ - Expiry: 7 days                            │
    │ - Stored: httpOnly, Secure cookie           │
    └─────────────────────────────────────────────┘
```

### 9.2 Request Authorization

Every protected API endpoint uses a FastAPI dependency:
```
Request → Extract Bearer token from Authorization header
               │
               ▼
          Decode JWT (verify signature + expiry)
               │
               ▼
          Extract user_id + role
               │
               ▼
          Check role against endpoint's required role
          └── 403 if insufficient permissions
               │
               ▼
          Inject user context into route handler
```

### 9.3 Security Controls Summary

| Control | Implementation |
|---|---|
| Password storage | bcrypt, 12 salt rounds |
| Token storage | Access: JS memory; Refresh: httpOnly cookie |
| Token rotation | Refresh token rotated on every use |
| CORS | Allowlist: production frontend URL only |
| Rate limiting | slowapi (100 req/min unauthenticated, 1000 req/min authenticated) |
| SQL injection | SQLAlchemy ORM only — no raw SQL with user input |
| XSS | Next.js escapes by default; CSP headers added |
| Input validation | Pydantic on all request bodies |

---

## 10. Deployment Architecture

### Production Topology

```
Internet
    │
    ▼
Vercel CDN (Frontend)          Render.com (Backend + AI)
    │                                    │
    │ HTTPS                              │ HTTPS
    ▼                                    ▼
Next.js App (Vercel Edge)    FastAPI Backend (Render Web Service)
                                         │
                              ┌──────────┼────────────┐
                              │          │            │
                              ▼          ▼            ▼
                         Neon DB    Render Redis   AI Service
                         (PostgreSQL) (Redis Cloud) (Render)
```

### Local Development Topology

```
Docker Compose
├── frontend (Next.js, port 3000)
├── backend (FastAPI, port 8000)
├── ai-service (FastAPI, port 8001)
├── postgres (PostgreSQL, port 5432)
└── redis (Redis, port 6379)
```

---

## 11. Scalability Strategy

### Phase 1 (MVP): Single Server

- Docker Compose on a single Render instance
- Redis as single node
- PostgreSQL on Neon (serverless, auto-scales reads)

### Phase 2 (10–50 stores):

- FastAPI deployed with multiple Gunicorn workers
- Redis cluster for pub/sub at scale
- PostgreSQL read replica for analytics queries
- AI Service with GPU-enabled instance

### Phase 3 (50+ stores):

- Kubernetes deployment
- Horizontal pod autoscaling based on WebSocket connection count
- Redis Cluster mode
- CDN for static assets
- Message queue (Kafka) for CV event ingestion

---

## 12. Failure Modes & Resilience

| Component | Failure Mode | Detection | Recovery |
|---|---|---|---|
| Redis | Connection dropped | Health check endpoint | Fallback to DB reads; WebSocket reconnects |
| AI Service | Inference crash | HTTP health check | CV updates stop; manual input continues |
| WebSocket | Client disconnect | TCP close event | Client auto-reconnects with exponential backoff |
| PostgreSQL | Connection pool exhausted | SQLAlchemy pool events | Connection queuing; alert sent |
| Queue update | Concurrent writes | Optimistic locking | Last-write-wins with timestamp |
| CV camera | Stream unavailable | Timeout on frame read | Log error; use last known count |

---

*Document version: 1.0.0 | Approved by: RetailFlow AI Technical Architecture Team*  
*Next: LLD.md — Low-Level Design, API contracts, data models*
