# RetailFlow AI — Product Requirements Document (PRD)

**Version:** 1.0.0  
**Status:** Approved  
**Author:** RetailFlow AI Engineering Team  
**Date:** 2026-06-26  
**Revision History:**

| Version | Date       | Author            | Description         |
|---------|------------|-------------------|---------------------|
| 1.0.0   | 2026-06-26 | Engineering Team  | Initial PRD         |

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Problem Statement](#2-problem-statement)
3. [Product Vision & Goals](#3-product-vision--goals)
4. [Target Audience & User Personas](#4-target-audience--user-personas)
5. [Functional Requirements](#5-functional-requirements)
6. [Non-Functional Requirements](#6-non-functional-requirements)
7. [MVP Scope](#7-mvp-scope)
8. [Future Scope](#8-future-scope)
9. [Constraints & Assumptions](#9-constraints--assumptions)
10. [Success Metrics (KPIs)](#10-success-metrics-kpis)
11. [Risks & Mitigations](#11-risks--mitigations)
12. [Glossary](#12-glossary)

---

## 1. Executive Summary

**RetailFlow AI** is an AI-powered Retail Queue Intelligence Platform designed to help brick-and-mortar retail stores monitor, predict, and optimize customer queue dynamics in real-time. By leveraging computer vision (YOLOv8), machine learning (XGBoost), and real-time WebSocket communication, RetailFlow AI enables store managers to make data-driven staffing decisions, reduces customer wait times, and improves the overall shopping experience.

**Target Deployment Environments:**
- D-Mart hypermarkets
- Zudio fashion retail stores
- Reliance Trends outlets
- Supermarkets and grocery chains
- Shopping mall anchor stores

**Core Value Proposition:**  
Reduce average customer wait time by 30–40% through intelligent counter staffing recommendations and real-time queue prediction, translating directly to improved customer satisfaction (NPS) and higher revenue per hour.

---

## 2. Problem Statement

### 2.1 Current Pain Points in Retail

| Pain Point | Impact |
|---|---|
| Long, unpredictable billing queues | Customer abandonment (15–25% during peak hours) |
| Manual queue management | Inefficient staffing, burnout among cashiers |
| No visibility into peak hours | Over/understaffing, wasted payroll |
| No real-time data for store managers | Reactive rather than proactive decision-making |
| Customers unaware of fastest counter | Poor customer experience, repeat complaints |

### 2.2 The Gap in the Market

Existing solutions (e.g., enterprise ERP systems like SAP Retail) are:
- Too expensive for mid-market retailers (₹50L+ annual licenses)
- Not AI-driven — purely rule-based
- Lacking real-time computer vision integration
- Not designed for the Indian retail market's unique operational patterns

RetailFlow AI fills this gap with a **lightweight, camera-integrated, ML-powered SaaS platform** that works with existing CCTV infrastructure.

---

## 3. Product Vision & Goals

### 3.1 Vision Statement

> *"Make every retail checkout experience faster, fairer, and frustration-free — for customers, cashiers, and store managers alike."*

### 3.2 Strategic Goals

| Goal | OKR |
|---|---|
| Reduce average wait time | Objective: Reduce avg. checkout wait by 35% within 90 days of deployment |
| Improve cashier utilization | Key Result: Achieve ≥85% counter utilization during peak hours |
| Enable real-time staffing decisions | Key Result: Manager response to queue alerts within 2 minutes |
| Deliver predictive intelligence | Key Result: Wait time prediction accuracy within ±2 minutes (90th percentile) |
| Build scalable SaaS | Key Result: Support 50+ stores from a single deployment without architecture changes |

---

## 4. Target Audience & User Personas

### Persona 1 — Aarav Mehta (Store Manager)

| Attribute | Detail |
|---|---|
| **Name** | Aarav Mehta |
| **Age** | 35 |
| **Role** | Store Manager, D-Mart Andheri |
| **Tech Savviness** | Medium |
| **Goal** | Keep queues short, avoid customer complaints, optimize staff rota |
| **Pain Points** | Can't see all 12 counters at once; receives complaints after the fact; has no data to justify staffing requests |
| **Device** | Store desktop + personal Android phone |
| **Session Length** | Checks dashboard 8–10 times/day; wants alerts on phone |
| **Quote** | *"If I could know a surge was coming 10 minutes before it happened, I could act on it."* |

---

### Persona 2 — Priya Sharma (Cashier / Counter Staff)

| Attribute | Detail |
|---|---|
| **Name** | Priya Sharma |
| **Age** | 24 |
| **Role** | Billing Cashier, Zudio |
| **Tech Savviness** | Low–Medium |
| **Goal** | Do her job efficiently; avoid burnout during peak hours |
| **Pain Points** | Manually informed when to open/close counter; no visibility on queue length behind her |
| **Device** | Counter display / small tablet |
| **Session Length** | Passive user — receives assignments |
| **Quote** | *"Sometimes I'm sitting idle and the next counter has 10 people."* |

---

### Persona 3 — Rohit Kumar (Customer)

| Attribute | Detail |
|---|---|
| **Name** | Rohit Kumar |
| **Age** | 29 |
| **Role** | Regular shopper at Reliance Trends |
| **Tech Savviness** | High |
| **Goal** | Get in and out of the store quickly; know where to stand |
| **Pain Points** | Joins a long queue not knowing a shorter one exists 10 feet away |
| **Device** | Android smartphone |
| **Session Length** | 1–3 minutes while in the billing area |
| **Quote** | *"Why didn't anyone tell me counter 3 was empty?"* |

---

### Persona 4 — Sanjana Iyer (Regional Operations Head / Admin)

| Attribute | Detail |
|---|---|
| **Name** | Sanjana Iyer |
| **Age** | 42 |
| **Role** | Regional Head of Operations, Supermarket Chain |
| **Tech Savviness** | Medium–High |
| **Goal** | Monitor performance across 15 stores; identify underperformers; report to leadership |
| **Pain Points** | No aggregated data; depends on store managers to self-report; no trend analysis |
| **Device** | MacBook Pro, large monitor |
| **Session Length** | 20–45 minutes, morning review |
| **Quote** | *"I need to know which stores are struggling before my Monday meeting."* |

---

## 5. Functional Requirements

### 5.1 Authentication & Authorization Module (FR-AUTH)

| ID | Requirement | Priority |
|---|---|---|
| FR-AUTH-01 | System shall allow users to register with email, password, store affiliation | P0 |
| FR-AUTH-02 | System shall authenticate users via email/password with JWT tokens | P0 |
| FR-AUTH-03 | System shall implement refresh token rotation with 7-day expiry | P0 |
| FR-AUTH-04 | System shall enforce Role-Based Access Control (RBAC) with roles: Admin, Manager, Customer | P0 |
| FR-AUTH-05 | System shall allow Admins to invite Managers to specific stores | P1 |
| FR-AUTH-06 | System shall log all authentication events (login, logout, token refresh) | P1 |
| FR-AUTH-07 | Passwords shall be hashed using bcrypt with salt rounds ≥ 12 | P0 |

### 5.2 Store Management Module (FR-STORE)

| ID | Requirement | Priority |
|---|---|---|
| FR-STORE-01 | Admin shall be able to create, read, update, delete (CRUD) store profiles | P0 |
| FR-STORE-02 | Each store shall have: name, address, city, state, total counters, operating hours | P0 |
| FR-STORE-03 | Admin shall be able to add/remove billing counters per store | P0 |
| FR-STORE-04 | Each counter shall track: counter number, assigned cashier, status (open/closed/break) | P0 |
| FR-STORE-05 | Admin shall be able to assign Managers to specific stores | P0 |
| FR-STORE-06 | System shall support multiple stores under a single admin account | P0 |

### 5.3 Queue Management Engine (FR-QUEUE)

| ID | Requirement | Priority |
|---|---|---|
| FR-QUEUE-01 | System shall maintain a real-time queue count per counter | P0 |
| FR-QUEUE-02 | System shall calculate estimated waiting time (EWT) per counter | P0 |
| FR-QUEUE-03 | System shall identify the fastest/shortest counter in real-time | P0 |
| FR-QUEUE-04 | System shall maintain queue history per counter per day | P0 |
| FR-QUEUE-05 | System shall support manual queue update (cashier/manager input) | P0 |
| FR-QUEUE-06 | System shall support automatic queue update via computer vision (Phase 8) | P1 |
| FR-QUEUE-07 | System shall broadcast queue updates via WebSocket to all connected clients | P0 |
| FR-QUEUE-08 | Customer shall be able to view fastest counter and estimated wait time | P0 |

### 5.4 Manager Dashboard (FR-DASH)

| ID | Requirement | Priority |
|---|---|---|
| FR-DASH-01 | Dashboard shall display live counter status across all store counters | P0 |
| FR-DASH-02 | Dashboard shall show real-time queue lengths as visual indicators | P0 |
| FR-DASH-03 | Dashboard shall render charts: queue trends, peak hours, counter performance | P0 |
| FR-DASH-04 | Dashboard shall display heatmap of busy hours (daily/weekly) | P1 |
| FR-DASH-05 | Dashboard shall send alerts when queue length exceeds threshold | P0 |
| FR-DASH-06 | Dashboard shall show AI-powered staffing recommendations | P1 |
| FR-DASH-07 | Manager shall be able to switch between multiple managed stores | P1 |

### 5.5 Computer Vision Module (FR-CV)

| ID | Requirement | Priority |
|---|---|---|
| FR-CV-01 | System shall process CCTV/webcam feed using YOLOv8 | P1 |
| FR-CV-02 | System shall detect and count people in defined queue zones | P1 |
| FR-CV-03 | System shall calculate crowd density scores per zone | P1 |
| FR-CV-04 | System shall automatically push detected counts to queue engine | P1 |
| FR-CV-05 | System shall support configurable detection zones (ROI) per camera | P2 |

### 5.6 ML Prediction Module (FR-ML)

| ID | Requirement | Priority |
|---|---|---|
| FR-ML-01 | System shall predict estimated wait times using historical data | P1 |
| FR-ML-02 | Model inputs: queue length, time of day, day of week, counter count, historical avg | P1 |
| FR-ML-03 | Model shall output: predicted wait time (minutes) + confidence interval | P1 |
| FR-ML-04 | System shall provide staffing recommendation (open/close counter) | P1 |
| FR-ML-05 | Model shall be retrained on new data weekly (cron job) | P2 |

### 5.7 Notifications Module (FR-NOTIF)

| ID | Requirement | Priority |
|---|---|---|
| FR-NOTIF-01 | System shall send email alerts when queue exceeds threshold | P1 |
| FR-NOTIF-02 | System shall send SMS alerts (mock implementation) to manager phone | P1 |
| FR-NOTIF-03 | System shall support in-app push notifications via WebSocket | P0 |
| FR-NOTIF-04 | Managers shall be able to configure alert thresholds per counter | P1 |

### 5.8 Analytics Module (FR-ANALYTICS)

| ID | Requirement | Priority |
|---|---|---|
| FR-ANALYTICS-01 | System shall generate daily, weekly, monthly queue reports | P1 |
| FR-ANALYTICS-02 | System shall calculate counter efficiency scores | P1 |
| FR-ANALYTICS-03 | System shall identify and display peak hours per store | P1 |
| FR-ANALYTICS-04 | System shall export reports as CSV/PDF | P2 |

---

## 6. Non-Functional Requirements

### 6.1 Performance

| NFR ID | Requirement | Target |
|---|---|---|
| NFR-PERF-01 | API response time (95th percentile) | ≤ 200ms |
| NFR-PERF-02 | WebSocket queue update latency | ≤ 500ms end-to-end |
| NFR-PERF-03 | Dashboard page load time (TTI) | ≤ 3 seconds on 4G |
| NFR-PERF-04 | Computer vision inference time | ≤ 100ms per frame (with GPU) |
| NFR-PERF-05 | Database query response time | ≤ 50ms for 95th percentile |

### 6.2 Scalability

| NFR ID | Requirement | Target |
|---|---|---|
| NFR-SCALE-01 | Support concurrent users per store | ≥ 100 simultaneous WebSocket connections |
| NFR-SCALE-02 | Support number of stores | ≥ 500 stores per deployment |
| NFR-SCALE-03 | Queue event throughput | ≥ 1,000 events/second via Redis pub/sub |
| NFR-SCALE-04 | Horizontal scalability | Backend shall be stateless and horizontally scalable |

### 6.3 Reliability & Availability

| NFR ID | Requirement | Target |
|---|---|---|
| NFR-REL-01 | System uptime SLA | 99.5% per month |
| NFR-REL-02 | Maximum planned downtime | ≤ 1 hour/month |
| NFR-REL-03 | Data backup frequency | Daily automated backups |
| NFR-REL-04 | Graceful degradation | If CV module fails, manual input remains functional |

### 6.4 Security

| NFR ID | Requirement |
|---|---|
| NFR-SEC-01 | All API endpoints must be authenticated via JWT (except /auth/login, /auth/register) |
| NFR-SEC-02 | HTTPS enforced in production (TLS 1.2+) |
| NFR-SEC-03 | Input validation on all API endpoints (Pydantic schemas) |
| NFR-SEC-04 | SQL injection prevention via SQLAlchemy ORM (parameterized queries only) |
| NFR-SEC-05 | CORS policy: restricted to known frontend origins |
| NFR-SEC-06 | Rate limiting: 100 requests/minute per IP for unauthenticated routes |
| NFR-SEC-07 | Secrets management via environment variables (never hardcoded) |
| NFR-SEC-08 | Sensitive data (passwords) never returned in API responses |

### 6.5 Maintainability

| NFR ID | Requirement |
|---|---|
| NFR-MAINT-01 | Code coverage ≥ 80% (unit + integration tests) |
| NFR-MAINT-02 | All public APIs documented with OpenAPI/Swagger |
| NFR-MAINT-03 | Consistent logging with structured JSON logs |
| NFR-MAINT-04 | Database migrations via Alembic (never direct DDL in production) |
| NFR-MAINT-05 | Dependency pinning via requirements.txt and package-lock.json |

### 6.6 Usability & Accessibility

| NFR ID | Requirement |
|---|---|
| NFR-UX-01 | UI shall be fully responsive (mobile, tablet, desktop) |
| NFR-UX-02 | Dashboard shall meet WCAG 2.1 AA accessibility standards |
| NFR-UX-03 | Customer-facing pages shall load in ≤ 2 seconds |
| NFR-UX-04 | All error states shall have human-readable error messages |

---

## 7. MVP Scope

The MVP (Minimum Viable Product) focuses on delivering a **fully functional core system** that can be demonstrated end-to-end, including real-time queue monitoring, basic AI prediction, and role-based dashboards.

### In Scope for MVP

| Feature | Module |
|---|---|
| ✅ User Registration & Login (JWT) | Auth |
| ✅ RBAC (Admin, Manager, Customer) | Auth |
| ✅ Store & Counter CRUD | Store Management |
| ✅ Real-time Queue Engine (WebSocket) | Queue Engine |
| ✅ Fastest Counter Detection | Queue Engine |
| ✅ Estimated Wait Time Calculation (rule-based) | Queue Engine |
| ✅ Manager Dashboard (live counters, charts) | Dashboard |
| ✅ Customer App (view fastest counter, EWT) | Customer App |
| ✅ Basic queue alerts (WebSocket push) | Notifications |
| ✅ YOLOv8 Queue Detection (simulated feed) | Computer Vision |
| ✅ ML Wait Time Prediction (XGBoost) | ML Module |
| ✅ Docker + Docker Compose deployment | DevOps |
| ✅ Swagger API documentation | Documentation |

### Out of Scope for MVP (Phase 2+)

| Feature | Reason |
|---|---|
| ❌ SMS notifications (live gateway) | Requires paid Twilio/SMS gateway; mock only |
| ❌ Email notifications (live SMTP) | Deferred to Phase 10 |
| ❌ CSV/PDF report export | Phase 11 |
| ❌ Multi-region deployment | Phase 12 |
| ❌ Mobile native app (React Native) | Future scope |
| ❌ POS system integration | Future scope |

---

## 8. Future Scope

| Feature | Description | Timeline |
|---|---|---|
| Native Mobile App | iOS/Android app for customers and managers | v2.0 |
| POS Integration | Connect to billing POS for automatic queue updates | v2.0 |
| Multi-language Support | Hindi, Tamil, Marathi UI | v2.1 |
| AI-powered Product Recommendations | Suggest products while customers wait | v3.0 |
| Customer Loyalty Integration | Queue priority for loyalty program members | v2.5 |
| Voice Announcements | "Counter 5 is now open" PA system integration | v2.0 |
| Digital Queue Tokens | QR-code based virtual queuing | v2.0 |
| Predictive Staffing Calendar | Weekly staffing suggestions based on historical patterns | v2.5 |
| WhatsApp Notifications | Queue status updates via WhatsApp Business API | v2.1 |
| Franchise Analytics | Multi-brand analytics for franchise chains | v3.0 |

---

## 9. Constraints & Assumptions

### Constraints

| # | Constraint |
|---|---|
| C-01 | The system must work with existing CCTV infrastructure (no new hardware required) |
| C-02 | Initial deployment targets stores with stable internet connectivity (≥ 10 Mbps) |
| C-03 | The system must be deployable on commodity hardware (1 CCTV camera per zone minimum) |
| C-04 | Budget: OpenAI/GPT APIs are NOT used in this project (cost constraint) |
| C-05 | All ML models must be self-hosted (no external ML API calls in core pipeline) |

### Assumptions

| # | Assumption |
|---|---|
| A-01 | Store managers have access to a web-enabled device (desktop/tablet) |
| A-02 | Each billing counter has a unique ID within its store |
| A-03 | Queue length is defined as number of customers in line, not items in cart |
| A-04 | Average service time per customer is initially estimated at 3 minutes (calibrated per store) |
| A-05 | Computer vision cameras are ceiling-mounted with top-down view for best detection accuracy |
| A-06 | Stores will have a dedicated staff member responsible for system data entry during early adoption |

---

## 10. Success Metrics (KPIs)

### Business KPIs

| KPI | Baseline (Pre-RetailFlow) | Target (90 days post-deployment) |
|---|---|---|
| Average customer wait time | 12–18 minutes | ≤ 8 minutes |
| Customer satisfaction score (CSAT) | 3.2 / 5.0 | ≥ 4.2 / 5.0 |
| Queue abandonment rate | 18% | ≤ 8% |
| Counter utilization rate | 62% | ≥ 82% |
| Manager response time to queue surge | 8–12 minutes | ≤ 2 minutes |

### Technical KPIs

| KPI | Target |
|---|---|
| API uptime | ≥ 99.5% |
| Wait time prediction accuracy | ±2 minutes (90th percentile) |
| YOLOv8 detection accuracy | ≥ 92% mAP |
| WebSocket update latency | ≤ 500ms |
| Test coverage | ≥ 80% |

---

## 11. Risks & Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Poor camera angles in-store | High | High | Provide camera placement guide; support multiple ROI configurations |
| Store staff reluctance to adopt | Medium | High | Simple UI; training videos; gradual rollout starting with 1 store |
| ML model accuracy on new stores | Medium | Medium | Cold-start with rule-based EWT; ML kicks in after 2 weeks of data collection |
| WebSocket connection drops | Low | Medium | Implement reconnection logic with exponential backoff |
| Database performance at scale | Low | High | Read replicas + Redis caching layer; query optimization with indexes |
| GDPR / Privacy concerns with CCTV | Medium | High | Process only anonymized bounding box counts; no face recognition; privacy policy |

---

## 12. Glossary

| Term | Definition |
|---|---|
| **EWT** | Estimated Waiting Time — AI-predicted time a customer will wait in queue |
| **Counter** | A billing point / checkout lane in a retail store |
| **Queue Length** | Number of customers currently waiting at a counter |
| **CCTV** | Closed-Circuit Television — existing store surveillance cameras |
| **ROI** | Region of Interest — defined zone in camera feed used for queue detection |
| **YOLOv8** | You Only Look Once v8 — state-of-the-art real-time object detection model |
| **mAP** | Mean Average Precision — metric for object detection model accuracy |
| **WebSocket** | Full-duplex communication protocol for real-time data streaming |
| **JWT** | JSON Web Token — stateless authentication token |
| **RBAC** | Role-Based Access Control — permission system based on user roles |
| **SaaS** | Software as a Service — cloud-hosted, subscription-based software model |
| **TTI** | Time to Interactive — frontend performance metric |
| **NPS** | Net Promoter Score — customer loyalty measurement |
| **CSAT** | Customer Satisfaction Score |

---

*Document approved by: RetailFlow AI Engineering Team*  
*Next: Phase 1 — System Design (HLD, LLD, Architecture Diagrams)*
