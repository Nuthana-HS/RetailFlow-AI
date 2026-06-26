# RetailFlow AI — Architecture Diagrams

**Version:** 1.0.0  
**Tooling:** Mermaid.js (render at mermaid.live or in any Mermaid-compatible viewer)

---

## Diagram 1: System Architecture (Component View)

```mermaid
graph TB
    subgraph CLIENT["🖥️ Client Layer"]
        FE1["Manager Dashboard\n(Next.js App Router)"]
        FE2["Customer App\n(Next.js Public Route)"]
        FE3["Admin Panel\n(Next.js App Router)"]
    end

    subgraph GATEWAY["🔀 API Gateway"]
        NGINX["NGINX / Vercel Edge\nLoad Balancer + TLS Termination"]
    end

    subgraph BACKEND["⚙️ Core API Service (FastAPI)"]
        AUTH["Auth Module\n/api/v1/auth"]
        STORE["Store Module\n/api/v1/stores"]
        QUEUE["Queue Module\n/api/v1/queues"]
        ANALYTICS["Analytics Module\n/api/v1/analytics"]
        NOTIF["Notification Module\n/api/v1/notifications"]
        WS["WebSocket Hub\n/ws/store/{id}"]
    end

    subgraph AI["🤖 AI Service (FastAPI)"]
        CV["CV Module\nYOLOv8 + OpenCV"]
        ML["ML Module\nXGBoost Predictor"]
    end

    subgraph DATA["💾 Data Layer"]
        PG[("PostgreSQL 16\nNeon Serverless")]
        REDIS[("Redis 7\nCache + Pub/Sub")]
    end

    subgraph INFRA["📡 External Services"]
        EMAIL["Email\nSMTP (SendGrid)"]
        CAM["CCTV Camera\nRTSP Stream"]
    end

    FE1 -->|HTTPS/WSS| NGINX
    FE2 -->|HTTPS| NGINX
    FE3 -->|HTTPS| NGINX
    NGINX -->|Proxy| AUTH & STORE & QUEUE & ANALYTICS & NOTIF & WS

    QUEUE -->|Read/Write| PG
    QUEUE -->|Cache + Pub| REDIS
    AUTH -->|Read/Write| PG
    STORE -->|Read/Write| PG
    ANALYTICS -->|Aggregate Reads| PG
    NOTIF -->|Send| EMAIL

    WS -->|Subscribe| REDIS

    CV -->|Read frames| CAM
    CV -->|POST queue count| QUEUE
    ML -->|Fetch features| REDIS
    ML -->|Fetch history| PG
    ML -->|Cache predictions| REDIS

    QUEUE -->|Publish events| REDIS
    REDIS -->|Broadcast| WS
```

---

## Diagram 2: Entity-Relationship (ER) Diagram

```mermaid
erDiagram
    USERS {
        uuid id PK
        string email UK
        string password_hash
        string full_name
        enum role "admin|manager|customer"
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    REFRESH_TOKENS {
        uuid id PK
        uuid user_id FK
        string token_hash UK
        timestamptz expires_at
        boolean revoked
        timestamptz created_at
    }

    STORES {
        uuid id PK
        string name
        text address
        string city
        string state
        string zip_code
        string phone
        uuid admin_id FK
        time open_time
        time close_time
        integer avg_service_time
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    STORE_MANAGERS {
        uuid store_id FK
        uuid user_id FK
        timestamptz assigned_at
    }

    COUNTERS {
        uuid id PK
        uuid store_id FK
        integer counter_number
        string label
        uuid cashier_id FK
        enum status "open|closed|break"
        boolean is_deleted
        timestamptz created_at
        timestamptz updated_at
    }

    QUEUE_SNAPSHOTS {
        uuid id PK
        uuid counter_id FK
        uuid store_id FK
        integer queue_length
        integer ewt_seconds
        enum update_source "manual|cv|ml"
        uuid updated_by FK
        timestamptz snapshot_at
    }

    ALERT_CONFIGS {
        uuid id PK
        uuid store_id FK
        uuid manager_id FK
        integer queue_threshold
        boolean email_enabled
        boolean push_enabled
        integer cooldown_minutes
        timestamptz last_alerted_at
        timestamptz created_at
    }

    NOTIFICATIONS {
        uuid id PK
        uuid user_id FK
        uuid store_id FK
        uuid counter_id FK
        string type
        string title
        text message
        boolean is_read
        timestamptz created_at
    }

    USERS ||--o{ REFRESH_TOKENS : "has many"
    USERS ||--o{ STORES : "administers"
    USERS ||--o{ STORE_MANAGERS : "manages"
    STORES ||--o{ STORE_MANAGERS : "has many"
    STORES ||--o{ COUNTERS : "has many"
    STORES ||--o{ QUEUE_SNAPSHOTS : "has many"
    STORES ||--o{ ALERT_CONFIGS : "has many"
    COUNTERS ||--o{ QUEUE_SNAPSHOTS : "has many"
    USERS ||--o{ NOTIFICATIONS : "receives"
    USERS ||--o{ ALERT_CONFIGS : "configures"
```

---

## Diagram 3: Sequence Diagram — User Login Flow

```mermaid
sequenceDiagram
    actor U as User (Browser)
    participant FE as Frontend (Next.js)
    participant API as Backend (FastAPI)
    participant DB as PostgreSQL
    participant CACHE as Redis

    U->>FE: Enter email + password
    FE->>FE: Client-side validation (React Hook Form)
    FE->>API: POST /api/v1/auth/login
    
    API->>DB: SELECT user WHERE email = ?
    DB-->>API: User record
    
    alt User not found
        API-->>FE: 401 UNAUTHORIZED
        FE-->>U: "Invalid credentials"
    end
    
    API->>API: bcrypt.compare(password, hash)
    
    alt Password mismatch
        API-->>FE: 401 UNAUTHORIZED
        FE-->>U: "Invalid credentials"
    end

    API->>API: Generate JWT access token (15 min)
    API->>API: Generate opaque refresh token
    API->>DB: INSERT refresh_tokens (token_hash, user_id, expires_at)
    
    API-->>FE: 200 OK\n{access_token, user}\n+ Set-Cookie: rf_token (httpOnly)
    
    FE->>FE: Store access_token in memory (Zustand)
    FE->>FE: Store user profile in Zustand
    FE-->>U: Redirect to /dashboard
```

---

## Diagram 4: Sequence Diagram — Real-Time Queue Update

```mermaid
sequenceDiagram
    actor M as Manager
    participant FE as Dashboard (React)
    participant API as Backend (FastAPI)
    participant DB as PostgreSQL
    participant REDIS as Redis
    participant WS as WebSocket Hub
    participant OTHER as Other Connected Clients

    M->>FE: Click "+1 customer" on Counter 3
    FE->>API: PATCH /api/v1/queues/{counter_id}\n{queue_length: 5}
    
    API->>API: Validate JWT + check manager role
    API->>API: Validate counter belongs to manager's store
    
    par Write to database
        API->>DB: INSERT queue_snapshots\n(counter_id, queue_length=5, updated_by=manager_id)
    and Update Redis cache
        API->>REDIS: HSET queue:counter:{id} queue_length 5 ewt_seconds 900
    end
    
    API->>API: Calculate fastest counter in store
    API->>REDIS: PUBLISH queue:events:store:{store_id} {event: queue_update, ...}
    
    API-->>FE: 200 OK {counter updated state}
    FE->>FE: Update local UI optimistically
    
    REDIS-->>WS: Message on queue:events:store:{store_id}
    
    par Broadcast to all subscribers
        WS->>FE: WS message: queue_update event
        WS->>OTHER: WS message: queue_update event (other managers)
    end
    
    FE->>FE: Animate counter card update
```

---

## Diagram 5: Sequence Diagram — Computer Vision Auto-Update

```mermaid
sequenceDiagram
    participant CAM as CCTV Camera
    participant AI as AI Service (YOLOv8)
    participant API as Core API
    participant REDIS as Redis
    participant WS as WebSocket Hub
    participant FE as Manager Dashboard

    loop Every 500ms
        CAM->>AI: Video frame (RTSP stream)
        AI->>AI: Decode frame (OpenCV)
        AI->>AI: YOLOv8 inference\n(detect all persons)
        AI->>AI: Filter by ROI zone\n(queue area only)
        AI->>AI: Count persons in zone
        AI->>AI: Buffer count (rolling 5s average)
    end

    Note over AI: Every 5 seconds (smoothed count ready)
    
    AI->>API: POST /api/v1/queues/{counter_id}/cv-update\n{queue_length: 4, confidence: 0.91}
    
    API->>API: Validate service API key (X-Service-Key header)
    API->>REDIS: HSET queue:counter:{id} queue_length 4 update_source cv
    API->>API: INSERT queue_snapshot (source='cv')
    API->>REDIS: PUBLISH queue:events:store:{store_id} {event: queue_update}
    
    REDIS-->>WS: New event
    WS->>FE: WS: queue_update {counter_id, queue_length: 4, source: "cv"}
    FE->>FE: Auto-update counter card\n(no user action needed)
```

---

## Diagram 6: Sequence Diagram — ML Wait Time Prediction

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as Core API
    participant REDIS as Redis Cache
    participant ML as AI Service (ML)
    participant DB as PostgreSQL

    FE->>API: GET /api/v1/queues/{counter_id}/predict
    
    API->>REDIS: GET ml:predict:{counter_id}:{queue_length}
    
    alt Cache HIT
        REDIS-->>API: Cached prediction
        API-->>FE: 200 OK {ewt_minutes, confidence, cached: true}
    else Cache MISS
        API->>ML: POST /predict\n{queue_length, store_id, hour, day_of_week, ...}
        
        ML->>REDIS: GET queue:store:{store_id}:summary (open_counters)
        ML->>DB: SELECT avg_service_time FROM stores WHERE id = ?
        
        ML->>ML: Feature engineering
        ML->>ML: XGBoost inference
        ML->>ML: Calculate confidence interval
        
        alt Confidence >= 0.7
            ML-->>API: {ewt_minutes: 4.2, confidence: 0.83, method: "ml"}
        else Confidence < 0.7 (fallback)
            ML-->>API: {ewt_minutes: 5.0, confidence: 0.62, method: "rule_based"}
        end
        
        API->>REDIS: SETEX ml:predict:{counter_id}:{queue_length} 30 {prediction}
        API-->>FE: 200 OK {ewt_minutes, confidence, cached: false}
    end
```

---

## Diagram 7: Deployment Diagram (Production)

```mermaid
graph TB
    subgraph USERS["👥 End Users"]
        MGR["Manager Browser"]
        CUST["Customer Browser"]
        ADMIN["Admin Browser"]
    end

    subgraph VERCEL["☁️ Vercel (Frontend CDN)"]
        EDGE["Edge Network (Global CDN)"]
        NEXT["Next.js App\n(Serverless Functions)"]
        EDGE --> NEXT
    end

    subgraph RENDER["🟣 Render.com (Backend)"]
        BE["Core API\n(FastAPI - Web Service)\n2 vCPU, 1GB RAM"]
        AI["AI Service\n(FastAPI - Web Service)\n4 vCPU, 8GB RAM + GPU"]
    end

    subgraph NEON["🟢 Neon (Database)"]
        PG_MAIN[("PostgreSQL 16\nMain Branch\n(Read/Write)")]
        PG_READ[("PostgreSQL 16\nRead Replica\n(Analytics)")]
        PG_MAIN --> PG_READ
    end

    subgraph REDIS_CLOUD["🔴 Redis Cloud / Upstash"]
        RD[("Redis 7\nCache + Pub/Sub")]
    end

    subgraph MONITORING["📊 Monitoring"]
        SENTRY["Sentry\n(Error Tracking)"]
        PROM["Render Metrics\n(CPU/Memory)"]
    end

    MGR -->|HTTPS| EDGE
    CUST -->|HTTPS| EDGE
    ADMIN -->|HTTPS| EDGE

    NEXT -->|API calls| BE
    NEXT -->|WSS| BE

    BE -->|Read/Write| PG_MAIN
    BE -->|Analytics Reads| PG_READ
    BE <-->|Cache/PubSub| RD
    AI -->|CV Updates| BE
    AI -->|History| PG_READ

    BE -.->|Error logs| SENTRY
    AI -.->|Error logs| SENTRY
    BE -.->|Metrics| PROM
```

---

## Diagram 8: State Machine — Counter Status

```mermaid
stateDiagram-v2
    [*] --> Closed : Counter Created

    Closed --> Open : Manager opens counter\n(assigns cashier)
    Open --> Break : Cashier takes break
    Open --> Closed : Manager closes counter
    Break --> Open : Break ends
    Break --> Closed : Counter closed during break
    Closed --> [*] : Counter soft deleted

    note right of Open
        WebSocket event emitted:
        counter_status_change
        Queue begins accepting updates
    end note

    note right of Closed
        Queue frozen at 0
        EWT shows "Counter Closed"
    end note
```

---

## Diagram 9: Data Flow — Analytics Pipeline

```mermaid
graph LR
    subgraph RAW["📥 Raw Data"]
        QS["queue_snapshots\n(time-series table)"]
    end

    subgraph PROCESS["⚙️ Aggregation"]
        AGG1["Hourly Aggregation\nAVG queue per hour/day"]
        AGG2["Counter Efficiency\n% time at high queue"]
        AGG3["Peak Hour Detection\nTop 3 busy periods"]
    end

    subgraph CACHE["⚡ Redis Cache"]
        C1["analytics:store:{id}:daily\nTTL: 1 hour"]
        C2["analytics:store:{id}:heatmap\nTTL: 6 hours"]
    end

    subgraph OUTPUT["📤 API Response"]
        R1["Peak Hours Heatmap"]
        R2["Daily Summary"]
        R3["Counter Rankings"]
    end

    QS --> AGG1 & AGG2 & AGG3
    AGG1 --> C1
    AGG2 & AGG3 --> C2
    C1 --> R2
    C2 --> R1
    AGG2 --> R3
```

---

*Diagrams generated with Mermaid.js | View at https://mermaid.live*  
*Version: 1.0.0 | RetailFlow AI Engineering Team*
