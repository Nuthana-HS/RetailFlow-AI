# RetailFlow AI — User Stories & Acceptance Criteria

**Version:** 1.0.0  
**Status:** Approved  
**Linked to:** PRD v1.0.0  

---

## Epic 1: Authentication & Access Control

### US-AUTH-01 — User Registration

> **As a** new store manager,  
> **I want to** register an account with my email and store details,  
> **So that** I can access the RetailFlow AI dashboard for my store.

**Acceptance Criteria:**
- [ ] AC-1: User can submit a registration form with: full name, email, password, store name, role
- [ ] AC-2: Password must be minimum 8 characters, contain at least 1 uppercase, 1 number, 1 special character
- [ ] AC-3: System returns HTTP 201 with user profile (no password) on success
- [ ] AC-4: System returns HTTP 400 with validation errors if fields are missing or invalid
- [ ] AC-5: System returns HTTP 409 if email is already registered
- [ ] AC-6: Password is stored as bcrypt hash (never plaintext)
- [ ] AC-7: Registration form shows real-time field validation

**Story Points:** 3  
**Priority:** P0 (Must Have)

---

### US-AUTH-02 — User Login

> **As a** registered user,  
> **I want to** log in with my email and password,  
> **So that** I receive a JWT token to access protected resources.

**Acceptance Criteria:**
- [ ] AC-1: Login form accepts email and password
- [ ] AC-2: System returns access token (15 min expiry) and refresh token (7 days expiry) on success
- [ ] AC-3: System returns HTTP 401 with "Invalid credentials" if email/password are wrong
- [ ] AC-4: Access token is stored in memory (not localStorage) to prevent XSS
- [ ] AC-5: Refresh token is stored in an httpOnly cookie
- [ ] AC-6: After 5 failed login attempts, account is rate-limited for 15 minutes

**Story Points:** 5  
**Priority:** P0 (Must Have)

---

### US-AUTH-03 — Role-Based Access Control

> **As an** admin,  
> **I want to** assign roles (Admin, Manager, Customer) to users,  
> **So that** users can only access features appropriate to their role.

**Acceptance Criteria:**
- [ ] AC-1: Admin can view all users and assign/change roles
- [ ] AC-2: Manager cannot access Admin-only routes (returns HTTP 403)
- [ ] AC-3: Customer cannot access Manager or Admin routes (returns HTTP 403)
- [ ] AC-4: Role is embedded in JWT payload and verified on each request
- [ ] AC-5: Frontend hides UI elements based on user role

**Story Points:** 5  
**Priority:** P0 (Must Have)

---

### US-AUTH-04 — Token Refresh

> **As a** logged-in user,  
> **I want** my session to automatically refresh before it expires,  
> **So that** I am not unexpectedly logged out while using the dashboard.

**Acceptance Criteria:**
- [ ] AC-1: Frontend detects when access token is within 60 seconds of expiry
- [ ] AC-2: Frontend automatically calls `/auth/refresh` with the httpOnly refresh token
- [ ] AC-3: System returns a new access token and rotates the refresh token
- [ ] AC-4: If refresh token is expired or invalid, user is redirected to login page
- [ ] AC-5: Old refresh token is invalidated immediately after rotation

**Story Points:** 3  
**Priority:** P0 (Must Have)

---

## Epic 2: Store Management

### US-STORE-01 — Create Store

> **As an** admin,  
> **I want to** create a new store profile in the system,  
> **So that** I can start monitoring queues for that location.

**Acceptance Criteria:**
- [ ] AC-1: Admin can create a store with: name, address, city, state, ZIP, phone, operating hours (open/close time), max counters
- [ ] AC-2: System auto-generates a unique store_id
- [ ] AC-3: System returns HTTP 201 with full store object on success
- [ ] AC-4: Duplicate store names within the same admin account return HTTP 409
- [ ] AC-5: All fields validated server-side (Pydantic schema)

**Story Points:** 3  
**Priority:** P0 (Must Have)

---

### US-STORE-02 — Manage Counters

> **As an** admin or manager,  
> **I want to** add, edit, and remove billing counters for a store,  
> **So that** the queue engine tracks the correct number of active counters.

**Acceptance Criteria:**
- [ ] AC-1: Admin can create a counter with: counter number, label, store_id, initial status (open/closed)
- [ ] AC-2: Manager can change counter status (open/closed/break) in real-time
- [ ] AC-3: Counter deletion is soft-deleted (not permanently removed) to preserve historical data
- [ ] AC-4: System emits a WebSocket event when counter status changes
- [ ] AC-5: Counter list is visible on the dashboard sorted by counter number

**Story Points:** 5  
**Priority:** P0 (Must Have)

---

### US-STORE-03 — Assign Manager to Store

> **As an** admin,  
> **I want to** assign a manager to one or more stores,  
> **So that** that manager can only view and control their assigned stores.

**Acceptance Criteria:**
- [ ] AC-1: Admin can search for users with the Manager role and assign them to a store
- [ ] AC-2: A manager can be assigned to multiple stores
- [ ] AC-3: Manager's JWT payload includes list of assigned store_ids
- [ ] AC-4: Manager cannot view stores they are not assigned to (returns HTTP 403)
- [ ] AC-5: Admin can remove a manager's access to a store

**Story Points:** 3  
**Priority:** P0 (Must Have)

---

## Epic 3: Queue Engine

### US-QUEUE-01 — View Real-Time Queue

> **As a** manager,  
> **I want to** see the real-time queue length at each counter in my store,  
> **So that** I can quickly identify which counters need attention.

**Acceptance Criteria:**
- [ ] AC-1: Dashboard shows a card per counter displaying: queue length, EWT, cashier name, status
- [ ] AC-2: Data updates in real-time via WebSocket (no manual refresh needed)
- [ ] AC-3: Counter cards are color-coded: green (0–3 customers), yellow (4–7), red (8+)
- [ ] AC-4: Last updated timestamp is shown on each card
- [ ] AC-5: If WebSocket disconnects, the UI shows a "Reconnecting..." banner

**Story Points:** 8  
**Priority:** P0 (Must Have)

---

### US-QUEUE-02 — View Fastest Counter (Customer)

> **As a** customer in a store,  
> **I want to** see which counter has the shortest queue and estimated wait time,  
> **So that** I can choose the fastest checkout option.

**Acceptance Criteria:**
- [ ] AC-1: Customer app shows a single highlighted "Fastest Counter" recommendation
- [ ] AC-2: Recommendation includes: counter number, current queue length, estimated wait time
- [ ] AC-3: Recommendation updates in real-time as queues change
- [ ] AC-4: If all counters are equal, the lowest-numbered counter is shown
- [ ] AC-5: Customer app is accessible without login (public view) or via QR code at billing zone

**Story Points:** 5  
**Priority:** P0 (Must Have)

---

### US-QUEUE-03 — Update Queue (Manual)

> **As a** cashier or manager,  
> **I want to** manually update the queue count at my counter,  
> **So that** the system reflects the accurate current state.

**Acceptance Criteria:**
- [ ] AC-1: Authorized user can increment or decrement queue count via the UI
- [ ] AC-2: Queue count cannot go below 0 (validated both client and server)
- [ ] AC-3: Each update is logged with timestamp, user_id, and counter_id in queue_history
- [ ] AC-4: Update is broadcast to all connected clients via WebSocket within 500ms
- [ ] AC-5: Bulk update (set queue to specific number) is also supported

**Story Points:** 3  
**Priority:** P0 (Must Have)

---

### US-QUEUE-04 — Estimated Wait Time Calculation

> **As a** customer or manager,  
> **I want to** see an estimated wait time per counter,  
> **So that** I can make an informed decision about which queue to join.

**Acceptance Criteria:**
- [ ] AC-1: EWT is calculated as: queue_length × avg_service_time_per_customer
- [ ] AC-2: Default avg_service_time = 3 minutes (configurable per store)
- [ ] AC-3: When ML model is available, EWT uses ML prediction instead of rule-based formula
- [ ] AC-4: EWT is displayed in minutes and seconds (e.g., "~4 min 30 sec")
- [ ] AC-5: EWT shows confidence level when ML prediction is used

**Story Points:** 5  
**Priority:** P0 (Must Have)

---

## Epic 4: Manager Dashboard

### US-DASH-01 — Live Counter Overview

> **As a** manager,  
> **I want to** see all my store counters in a single, live-updating view,  
> **So that** I can monitor the entire store at a glance without walking the floor.

**Acceptance Criteria:**
- [ ] AC-1: Dashboard loads with all active counters for the selected store
- [ ] AC-2: Each counter card shows: counter #, status, queue length (with visual bar), cashier name, EWT
- [ ] AC-3: Counter cards animate when queue counts change (pulsing highlight)
- [ ] AC-4: Manager can filter counters by status (all, open, closed, break)
- [ ] AC-5: Dashboard works on tablet (1024px) and desktop (1440px) screens

**Story Points:** 8  
**Priority:** P0 (Must Have)

---

### US-DASH-02 — Queue Trend Chart

> **As a** manager,  
> **I want to** view a chart showing queue trends over the past few hours,  
> **So that** I can understand whether things are getting better or worse.

**Acceptance Criteria:**
- [ ] AC-1: Line chart showing total store queue length over time (last 2 hours, 30-second intervals)
- [ ] AC-2: Chart is interactive (hover for exact values, zoom)
- [ ] AC-3: Chart updates in real-time with new data points
- [ ] AC-4: Each counter can be toggled on/off on the chart
- [ ] AC-5: Chart shows a "surge threshold" line at manager-configured queue level

**Story Points:** 5  
**Priority:** P0 (Must Have)

---

### US-DASH-03 — Surge Alert

> **As a** manager,  
> **I want to** receive an alert when a counter's queue exceeds a configured threshold,  
> **So that** I can take action before customers become frustrated.

**Acceptance Criteria:**
- [ ] AC-1: Manager can configure alert threshold per store (e.g., alert when any counter > 8 customers)
- [ ] AC-2: Alert is displayed as a banner/toast notification in the dashboard UI
- [ ] AC-3: Alert includes: which counter, current queue length, EWT, suggested action
- [ ] AC-4: Alert is also sent via WebSocket push (visible even if dashboard tab is minimized)
- [ ] AC-5: Alert is dismissed manually or auto-dismissed when queue drops below threshold

**Story Points:** 5  
**Priority:** P0 (Must Have)

---

## Epic 5: Computer Vision

### US-CV-01 — Detect Queue via Camera

> **As a** store admin,  
> **I want** the system to automatically detect queue lengths from camera feeds,  
> **So that** no manual data entry is required from cashiers.

**Acceptance Criteria:**
- [ ] AC-1: CV module accepts a video stream URL (RTSP or webcam) as input
- [ ] AC-2: YOLOv8 detects all persons in the frame
- [ ] AC-3: Only persons within the defined ROI (queue zone) are counted
- [ ] AC-4: Detected count is pushed to the queue engine API every 5 seconds
- [ ] AC-5: A processed preview frame (with bounding boxes) is available for admin review
- [ ] AC-6: System gracefully handles camera disconnection (logs error, falls back to last known count)

**Story Points:** 13  
**Priority:** P1 (Should Have)

---

## Epic 6: ML Predictions

### US-ML-01 — Predict Wait Time with ML

> **As a** customer or manager,  
> **I want** the system to provide AI-predicted wait times,  
> **So that** the estimates are more accurate than a simple formula.

**Acceptance Criteria:**
- [ ] AC-1: ML model is trained on historical queue_history data
- [ ] AC-2: Model takes as input: queue_length, hour_of_day, day_of_week, num_open_counters, store_id
- [ ] AC-3: Model outputs: predicted_wait_minutes, confidence_score (0–1)
- [ ] AC-4: If confidence_score < 0.7, system falls back to rule-based EWT with a "Low confidence" label
- [ ] AC-5: Predictions are cached in Redis for 30 seconds to reduce model inference overhead

**Story Points:** 13  
**Priority:** P1 (Should Have)

---

## Epic 7: Notifications

### US-NOTIF-01 — Email Alert

> **As a** manager,  
> **I want to** receive an email notification when queue conditions are critical,  
> **So that** I am alerted even when not actively watching the dashboard.

**Acceptance Criteria:**
- [ ] AC-1: Email is sent when queue at any counter exceeds configured threshold for > 5 minutes
- [ ] AC-2: Email contains: store name, counter number, current queue length, EWT, dashboard link
- [ ] AC-3: Manager receives at most 1 email per counter per 30 minutes (throttling)
- [ ] AC-4: Manager can unsubscribe from email alerts per store in settings
- [ ] AC-5: Email sending failure is logged but does not affect core queue functionality

**Story Points:** 5  
**Priority:** P1 (Should Have)

---

## Epic 8: Analytics

### US-ANALYTICS-01 — View Peak Hours Report

> **As a** manager or admin,  
> **I want to** view a heatmap of peak queue hours for my store,  
> **So that** I can plan staffing rotas around the busiest times.

**Acceptance Criteria:**
- [ ] AC-1: Heatmap shows average queue length by hour (x-axis) and day of week (y-axis)
- [ ] AC-2: Data is computed from queue_history for the past 30 days
- [ ] AC-3: Heatmap is interactive (click on a cell to see that day/hour's data)
- [ ] AC-4: Report can be filtered by date range (last 7, 14, 30 days)
- [ ] AC-5: Admin can see aggregated heatmaps across all stores

**Story Points:** 8  
**Priority:** P1 (Should Have)

---

## Priority Summary

| Priority | Stories | Story Points |
|---|---|---|
| P0 — Must Have (MVP) | 12 | 64 SP |
| P1 — Should Have | 5 | 44 SP |
| P2 — Nice to Have | 3 | 18 SP |
| **Total** | **20** | **126 SP** |

---

## Sprint Planning Recommendation

| Sprint | Duration | Epics / Stories |
|---|---|---|
| Sprint 1 | 2 weeks | Auth (US-AUTH-01 to 04), Store CRUD (US-STORE-01 to 03) |
| Sprint 2 | 2 weeks | Queue Engine (US-QUEUE-01 to 04) |
| Sprint 3 | 2 weeks | Manager Dashboard (US-DASH-01 to 03) |
| Sprint 4 | 2 weeks | Customer App + Computer Vision (US-CV-01) |
| Sprint 5 | 2 weeks | ML Predictions (US-ML-01) + Notifications (US-NOTIF-01) |
| Sprint 6 | 2 weeks | Analytics (US-ANALYTICS-01) + Deployment + Polish |

---

*Last updated: 2026-06-26 | RetailFlow AI Engineering Team*
