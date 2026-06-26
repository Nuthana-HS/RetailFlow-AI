# RetailFlow AI — Low-Level Design (LLD)

**Version:** 1.0.0  
**Status:** Approved  
**Linked to:** HLD v1.0.0, PRD v1.0.0  

---

## Table of Contents

1. [Database Schema Design](#1-database-schema-design)
2. [API Contract Specification](#2-api-contract-specification)
3. [Service Layer Design](#3-service-layer-design)
4. [WebSocket Protocol Design](#4-websocket-protocol-design)
5. [Redis Data Structures](#5-redis-data-structures)
6. [ML Feature Schema](#6-ml-feature-schema)
7. [Error Codes & Response Standards](#7-error-codes--response-standards)
8. [Module Dependency Map](#8-module-dependency-map)

---

## 1. Database Schema Design

### 1.1 Table: `users`

```sql
CREATE TABLE users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email         VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    full_name     VARCHAR(255) NOT NULL,
    role          VARCHAR(20) NOT NULL CHECK (role IN ('admin', 'manager', 'customer')),
    is_active     BOOLEAN DEFAULT TRUE,
    created_at    TIMESTAMPTZ DEFAULT NOW(),
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);
```

### 1.2 Table: `refresh_tokens`

```sql
CREATE TABLE refresh_tokens (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  VARCHAR(255) UNIQUE NOT NULL,  -- SHA-256 of the raw token
    expires_at  TIMESTAMPTZ NOT NULL,
    revoked     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
CREATE INDEX idx_refresh_tokens_token_hash ON refresh_tokens(token_hash);
```

### 1.3 Table: `stores`

```sql
CREATE TABLE stores (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             VARCHAR(255) NOT NULL,
    address          TEXT NOT NULL,
    city             VARCHAR(100) NOT NULL,
    state            VARCHAR(100) NOT NULL,
    zip_code         VARCHAR(20),
    phone            VARCHAR(20),
    admin_id         UUID NOT NULL REFERENCES users(id),
    open_time        TIME NOT NULL DEFAULT '09:00:00',
    close_time       TIME NOT NULL DEFAULT '22:00:00',
    avg_service_time INTEGER NOT NULL DEFAULT 180,  -- seconds per customer
    is_active        BOOLEAN DEFAULT TRUE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_stores_admin_id ON stores(admin_id);
```

### 1.4 Table: `store_managers` (Association Table)

```sql
CREATE TABLE store_managers (
    store_id    UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (store_id, user_id)
);
```

### 1.5 Table: `counters`

```sql
CREATE TABLE counters (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id       UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    counter_number INTEGER NOT NULL,
    label          VARCHAR(100),          -- e.g., "Express Lane", "Counter 3"
    cashier_id     UUID REFERENCES users(id),
    status         VARCHAR(20) NOT NULL DEFAULT 'closed'
                     CHECK (status IN ('open', 'closed', 'break')),
    is_deleted     BOOLEAN DEFAULT FALSE, -- soft delete
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (store_id, counter_number)
);
CREATE INDEX idx_counters_store_id ON counters(store_id);
CREATE INDEX idx_counters_status ON counters(status) WHERE is_deleted = FALSE;
```

### 1.6 Table: `queue_snapshots` (Time-Series Queue Data)

```sql
CREATE TABLE queue_snapshots (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    counter_id      UUID NOT NULL REFERENCES counters(id) ON DELETE CASCADE,
    store_id        UUID NOT NULL REFERENCES stores(id),  -- denormalized for fast analytics
    queue_length    INTEGER NOT NULL DEFAULT 0 CHECK (queue_length >= 0),
    ewt_seconds     INTEGER NOT NULL DEFAULT 0,            -- estimated wait time
    update_source   VARCHAR(20) NOT NULL DEFAULT 'manual'
                      CHECK (update_source IN ('manual', 'cv', 'ml')),
    updated_by      UUID REFERENCES users(id),             -- NULL if CV update
    snapshot_at     TIMESTAMPTZ DEFAULT NOW()
);
-- Partition by month for large datasets (future optimization)
CREATE INDEX idx_snapshots_counter_id ON queue_snapshots(counter_id);
CREATE INDEX idx_snapshots_store_id_time ON queue_snapshots(store_id, snapshot_at DESC);
CREATE INDEX idx_snapshots_snapshot_at ON queue_snapshots(snapshot_at DESC);
```

### 1.7 Table: `alert_configs`

```sql
CREATE TABLE alert_configs (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    store_id          UUID NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
    manager_id        UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    queue_threshold   INTEGER NOT NULL DEFAULT 8,   -- alert when queue > this
    email_enabled     BOOLEAN DEFAULT TRUE,
    push_enabled      BOOLEAN DEFAULT TRUE,
    cooldown_minutes  INTEGER DEFAULT 30,            -- min minutes between alerts
    last_alerted_at   TIMESTAMPTZ,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (store_id, manager_id)
);
```

### 1.8 Table: `notifications`

```sql
CREATE TABLE notifications (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    store_id    UUID REFERENCES stores(id),
    counter_id  UUID REFERENCES counters(id),
    type        VARCHAR(50) NOT NULL,   -- 'queue_surge', 'counter_offline', 'system'
    title       VARCHAR(255) NOT NULL,
    message     TEXT NOT NULL,
    is_read     BOOLEAN DEFAULT FALSE,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_notifications_user_id ON notifications(user_id, is_read, created_at DESC);
```

---

## 2. API Contract Specification

### Standard Response Envelope

All API responses follow this structure:

```json
// Success Response
{
  "success": true,
  "data": { ... },
  "message": "Operation completed successfully",
  "timestamp": "2026-06-26T17:00:00Z"
}

// Error Response
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Human-readable error message",
    "details": [
      { "field": "email", "message": "Invalid email format" }
    ]
  },
  "timestamp": "2026-06-26T17:00:00Z"
}
```

---

### 2.1 Authentication API

#### `POST /api/v1/auth/register`

**Request:**
```json
{
  "email": "manager@dmart.com",
  "password": "SecurePass123!",
  "full_name": "Aarav Mehta",
  "role": "manager"
}
```

**Response (201):**
```json
{
  "success": true,
  "data": {
    "id": "uuid",
    "email": "manager@dmart.com",
    "full_name": "Aarav Mehta",
    "role": "manager",
    "created_at": "2026-06-26T17:00:00Z"
  }
}
```

---

#### `POST /api/v1/auth/login`

**Request:**
```json
{
  "email": "manager@dmart.com",
  "password": "SecurePass123!"
}
```

**Response (200):**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 900,
    "user": {
      "id": "uuid",
      "email": "manager@dmart.com",
      "full_name": "Aarav Mehta",
      "role": "manager",
      "store_ids": ["store-uuid-1", "store-uuid-2"]
    }
  }
}
```
*Note: Refresh token is set as `httpOnly` cookie: `rf_token`*

---

#### `POST /api/v1/auth/refresh`

**Headers:** Cookie: `rf_token=<refresh_token>`

**Response (200):** Same as login response — new access token + rotated refresh token cookie

---

#### `POST /api/v1/auth/logout`

**Headers:** `Authorization: Bearer <access_token>`

**Response (200):** Clears refresh token cookie, revokes token in DB

---

### 2.2 Store API

#### `POST /api/v1/stores` — Create Store `[Admin]`

**Request:**
```json
{
  "name": "D-Mart Andheri",
  "address": "Lokhandwala Complex, Andheri West",
  "city": "Mumbai",
  "state": "Maharashtra",
  "zip_code": "400053",
  "phone": "+91-22-6789-0123",
  "open_time": "09:00",
  "close_time": "22:00",
  "avg_service_time": 180
}
```

**Response (201):** Full store object

---

#### `GET /api/v1/stores` — List Stores `[Admin]`

**Query params:** `?page=1&limit=20&city=Mumbai&is_active=true`

**Response (200):**
```json
{
  "success": true,
  "data": {
    "items": [ { ...store } ],
    "total": 45,
    "page": 1,
    "limit": 20,
    "pages": 3
  }
}
```

---

#### `GET /api/v1/stores/{store_id}` — Get Store Details `[Admin, Manager]`

**Response (200):** Full store object with counters and managers list

---

#### `PATCH /api/v1/stores/{store_id}` — Update Store `[Admin]`

**Request:** Partial update (any store fields)

---

#### `DELETE /api/v1/stores/{store_id}` — Soft Delete Store `[Admin]`

---

### 2.3 Counter API

#### `POST /api/v1/stores/{store_id}/counters` — Create Counter `[Admin]`

**Request:**
```json
{
  "counter_number": 5,
  "label": "Express Lane",
  "status": "closed"
}
```

---

#### `GET /api/v1/stores/{store_id}/counters` — List Counters `[Admin, Manager]`

**Query params:** `?status=open`

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "uuid",
      "counter_number": 5,
      "label": "Express Lane",
      "status": "open",
      "cashier": { "id": "uuid", "full_name": "Priya Sharma" },
      "current_queue": {
        "queue_length": 3,
        "ewt_seconds": 540,
        "last_updated": "2026-06-26T17:00:00Z"
      }
    }
  ]
}
```

---

#### `PATCH /api/v1/counters/{counter_id}` — Update Counter Status `[Admin, Manager]`

**Request:**
```json
{
  "status": "open",
  "cashier_id": "uuid"
}
```

---

### 2.4 Queue API

#### `GET /api/v1/stores/{store_id}/queue` — Get Store Queue State `[Any Authenticated + Public]`

**Response:**
```json
{
  "success": true,
  "data": {
    "store_id": "uuid",
    "store_name": "D-Mart Andheri",
    "last_updated": "2026-06-26T17:00:00Z",
    "fastest_counter": {
      "counter_id": "uuid",
      "counter_number": 3,
      "queue_length": 1,
      "ewt_seconds": 180,
      "ewt_display": "~3 min"
    },
    "counters": [
      {
        "counter_id": "uuid",
        "counter_number": 1,
        "label": "Counter 1",
        "status": "open",
        "queue_length": 6,
        "ewt_seconds": 1080,
        "ewt_display": "~18 min",
        "prediction_method": "ml",
        "confidence": 0.87
      }
    ]
  }
}
```

---

#### `PATCH /api/v1/queues/{counter_id}` — Update Queue Count `[Admin, Manager, Cashier]`

**Request:**
```json
{
  "queue_length": 5,
  "update_source": "manual"
}
```

**Response (200):** Updated queue state for that counter

*Side effects: Writes to `queue_snapshots`, updates Redis cache, publishes to Redis pub/sub*

---

#### `POST /api/v1/queues/{counter_id}/cv-update` — CV Auto Update `[Internal, AI Service only]`

**Request:**
```json
{
  "queue_length": 4,
  "confidence": 0.91,
  "frame_timestamp": "2026-06-26T17:00:00Z"
}
```

*This endpoint is only callable by the AI service using a service-to-service API key*

---

#### `GET /api/v1/queues/{counter_id}/predict` — Get ML Prediction `[Admin, Manager]`

**Response:**
```json
{
  "success": true,
  "data": {
    "counter_id": "uuid",
    "queue_length": 5,
    "ewt_minutes": 4.2,
    "ewt_seconds": 252,
    "confidence": 0.83,
    "prediction_method": "ml",
    "cached": false,
    "model_version": "1.2.0"
  }
}
```

---

#### `GET /api/v1/queues/{counter_id}/history` — Queue History `[Admin, Manager]`

**Query params:** `?from=2026-06-26T00:00:00Z&to=2026-06-26T23:59:59Z&interval=5m`

**Response:** Array of time-series snapshots aggregated by interval

---

### 2.5 Analytics API

#### `GET /api/v1/analytics/stores/{store_id}/peak-hours` — Peak Hours Heatmap `[Admin, Manager]`

**Query params:** `?days=30`

**Response:**
```json
{
  "success": true,
  "data": {
    "heatmap": [
      {
        "day_of_week": 1,
        "hour": 9,
        "avg_queue_length": 2.3,
        "max_queue_length": 7
      }
    ],
    "peak_day": "Saturday",
    "peak_hour": "18:00–19:00",
    "avg_daily_customers": 342
  }
}
```

---

#### `GET /api/v1/analytics/stores/{store_id}/summary` — Store Analytics Summary `[Admin, Manager]`

**Query params:** `?period=daily|weekly|monthly`

---

### 2.6 Notifications API

#### `GET /api/v1/notifications` — Get User Notifications `[Any Auth]`

**Query params:** `?unread_only=true&limit=20`

---

#### `PATCH /api/v1/notifications/{id}/read` — Mark as Read

---

#### `GET /api/v1/notifications/settings` — Get Alert Config `[Manager]`

#### `PATCH /api/v1/notifications/settings` — Update Alert Config `[Manager]`

---

## 3. Service Layer Design

### 3.1 Queue Service Interface

```python
class QueueService:
    """
    Business logic for queue management.
    All methods are async and transactional.
    """
    
    async def update_queue(
        self,
        counter_id: UUID,
        queue_length: int,
        update_source: UpdateSource,
        updated_by: Optional[UUID]
    ) -> QueueSnapshot:
        """
        Updates queue count for a counter.
        Writes to DB, updates Redis cache, publishes WebSocket event.
        """
        ...

    async def get_store_queue_state(
        self,
        store_id: UUID
    ) -> StoreQueueState:
        """
        Returns full queue state for all counters in a store.
        Reads from Redis cache first (≤5ms), falls back to DB.
        """
        ...

    async def get_fastest_counter(
        self,
        store_id: UUID
    ) -> CounterQueueInfo:
        """
        Returns the counter with lowest queue_length among open counters.
        Tie-break: lowest counter_number.
        """
        ...

    async def calculate_ewt(
        self,
        counter_id: UUID,
        queue_length: int
    ) -> EWTResult:
        """
        Calculates estimated wait time.
        Uses ML prediction if available and confident, else rule-based.
        """
        ...
```

### 3.2 Auth Service Interface

```python
class AuthService:
    """JWT authentication and token lifecycle management."""
    
    async def register_user(self, data: UserRegisterSchema) -> User: ...
    
    async def authenticate_user(
        self, 
        email: str, 
        password: str
    ) -> Tuple[str, str]:
        """Returns (access_token, refresh_token)"""
        ...
    
    async def refresh_access_token(
        self, 
        refresh_token: str
    ) -> Tuple[str, str]:
        """Rotates refresh token, returns new (access_token, refresh_token)"""
        ...
    
    async def revoke_refresh_token(self, refresh_token: str) -> None: ...
```

### 3.3 Store Service Interface

```python
class StoreService:
    """Store and counter management business logic."""
    
    async def create_store(
        self, data: StoreCreateSchema, admin_id: UUID
    ) -> Store: ...
    
    async def assign_manager(
        self, store_id: UUID, manager_id: UUID, admin_id: UUID
    ) -> StoreManager: ...
    
    async def get_stores_for_manager(
        self, manager_id: UUID
    ) -> List[Store]: ...
    
    async def update_counter_status(
        self, counter_id: UUID, status: CounterStatus, user_id: UUID
    ) -> Counter: ...
```

---

## 4. WebSocket Protocol Design

### 4.1 Connection

```
Client connects to: wss://api.retailflow.ai/ws/store/{store_id}?token={access_token}
```

### 4.2 Server → Client Messages

All messages follow this envelope:

```typescript
interface WSMessage {
  event: WSEventType;
  store_id: string;
  timestamp: string;  // ISO 8601
  payload: unknown;
}

type WSEventType =
  | 'queue_update'
  | 'counter_status_change'
  | 'alert_triggered'
  | 'alert_resolved'
  | 'connection_established'
  | 'ping';
```

#### `queue_update` Event

```json
{
  "event": "queue_update",
  "store_id": "uuid",
  "timestamp": "2026-06-26T17:00:00Z",
  "payload": {
    "counter_id": "uuid",
    "counter_number": 3,
    "queue_length": 5,
    "ewt_seconds": 900,
    "ewt_display": "~15 min",
    "update_source": "cv",
    "fastest_counter_id": "uuid"
  }
}
```

#### `alert_triggered` Event

```json
{
  "event": "alert_triggered",
  "store_id": "uuid",
  "timestamp": "2026-06-26T17:00:00Z",
  "payload": {
    "alert_id": "uuid",
    "counter_number": 7,
    "queue_length": 12,
    "threshold": 8,
    "ewt_display": "~36 min",
    "suggestion": "Consider opening Counter 2 to reduce load"
  }
}
```

#### `counter_status_change` Event

```json
{
  "event": "counter_status_change",
  "store_id": "uuid",
  "timestamp": "2026-06-26T17:00:00Z",
  "payload": {
    "counter_id": "uuid",
    "counter_number": 2,
    "old_status": "closed",
    "new_status": "open",
    "cashier_name": "Priya Sharma"
  }
}
```

### 4.3 Client → Server Messages

```json
// Heartbeat (client sends every 30 seconds)
{ "event": "pong", "timestamp": "..." }
```

---

## 5. Redis Data Structures

### 5.1 Queue State Cache

```
Key:   queue:counter:{counter_id}
Type:  Hash
TTL:   60 seconds (auto-refreshed on update)
Fields:
  queue_length  → integer
  ewt_seconds   → integer
  status        → string (open/closed/break)
  updated_at    → ISO timestamp
  update_source → string (manual/cv/ml)

Example:
  HGETALL queue:counter:abc-123
  → { queue_length: "5", ewt_seconds: "900", status: "open", ... }
```

### 5.2 Store Queue Summary Cache

```
Key:   queue:store:{store_id}:summary
Type:  Hash
TTL:   30 seconds
Fields:
  total_queue    → integer (sum of all counter queues)
  open_counters  → integer
  fastest_counter_id → string

```

### 5.3 Pub/Sub Channels

```
Channel: queue:events:store:{store_id}

Published message format (JSON string):
{
  "event": "queue_update",
  "store_id": "...",
  "counter_id": "...",
  "timestamp": "...",
  "payload": { ... }
}
```

### 5.4 Rate Limiting

```
Key:   rate_limit:ip:{ip_address}
Type:  String (counter)
TTL:   60 seconds
Value: Request count within the TTL window
```

### 5.5 ML Prediction Cache

```
Key:   ml:predict:{counter_id}:{queue_length}
Type:  Hash
TTL:   30 seconds
Fields:
  ewt_minutes    → float
  confidence     → float
  model_version  → string
  predicted_at   → ISO timestamp
```

---

## 6. ML Feature Schema

### 6.1 Training Data Schema

```python
@dataclass
class QueueFeatures:
    """Input features for XGBoost wait time predictor."""
    
    # Queue state
    queue_length: int            # Current queue length (0–50)
    open_counters: int           # Number of open counters in store (1–20)
    
    # Temporal features
    hour_of_day: int             # 0–23
    minute_of_hour: int          # 0–59
    day_of_week: int             # 0=Monday, 6=Sunday
    is_weekend: int              # 0 or 1
    is_peak_hour: int            # 0 or 1 (based on historical data)
    
    # Store-specific features
    store_avg_service_time: int  # Seconds per customer (configured)
    store_avg_queue_this_hour: float  # Historical avg for this hour/day
    
    # Target variable (training only)
    actual_wait_seconds: Optional[int]
```

### 6.2 Model Output Schema

```python
@dataclass
class PredictionResult:
    ewt_minutes: float           # Predicted wait time
    ewt_seconds: int             # Same, in seconds
    confidence: float            # 0.0–1.0
    lower_bound_minutes: float   # 10th percentile
    upper_bound_minutes: float   # 90th percentile
    method: str                  # "ml" | "rule_based"
    model_version: str
```

---

## 7. Error Codes & Response Standards

| HTTP Status | Error Code | Description |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Request body/params failed Pydantic validation |
| 400 | `INVALID_QUEUE_LENGTH` | Queue length is negative or exceeds max |
| 401 | `UNAUTHORIZED` | Missing or invalid access token |
| 401 | `TOKEN_EXPIRED` | Access token has expired |
| 401 | `REFRESH_TOKEN_INVALID` | Refresh token invalid or revoked |
| 403 | `FORBIDDEN` | User does not have required role |
| 403 | `STORE_ACCESS_DENIED` | Manager does not manage this store |
| 404 | `STORE_NOT_FOUND` | Store with given ID does not exist |
| 404 | `COUNTER_NOT_FOUND` | Counter with given ID does not exist |
| 409 | `EMAIL_ALREADY_EXISTS` | Registration email already taken |
| 409 | `COUNTER_NUMBER_DUPLICATE` | Counter number already exists in store |
| 429 | `RATE_LIMIT_EXCEEDED` | Too many requests |
| 500 | `INTERNAL_SERVER_ERROR` | Unexpected server error |
| 503 | `ML_SERVICE_UNAVAILABLE` | AI service is down; using rule-based fallback |

---

## 8. Module Dependency Map

```
┌─────────────────────────────────────────────────────┐
│                   API Routes (Layer 4)               │
│   /auth  /stores  /counters  /queues  /analytics    │
└────────────────────┬────────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────────┐
│              Service Layer (Layer 3)                 │
│  AuthService  StoreService  QueueService             │
│  AnalyticsService  NotificationService               │
└────────────────────┬────────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────────┐
│            Repository Layer (Layer 2)               │
│  UserRepo  StoreRepo  CounterRepo  SnapshotRepo     │
│  TokenRepo  NotificationRepo                        │
└────────────────────┬────────────────────────────────┘
                     │ calls
┌────────────────────▼────────────────────────────────┐
│              Infrastructure (Layer 1)               │
│  PostgreSQL (SQLAlchemy)  Redis  Email  WebSocket   │
└────────────────────────────────────────────────────┘
```

**Dependency Rules:**
- Layer N can only call Layer N-1 (no skipping layers)
- No circular dependencies between modules
- All inter-module communication happens through defined interfaces (not direct class instantiation)
- All external dependencies (DB, Redis) are injected via FastAPI `Depends()`

---

*Document version: 1.0.0 | Approved by: RetailFlow AI Engineering Team*
