# System Architecture

## 1. Style

Modular, event-driven, with independently deployable AI services. Frontend and backend communicate
over authenticated HTTP and WebSockets. Industrial telemetry enters through an MQTT broker or an
HTTP ingestion endpoint. A LangGraph orchestrator coordinates the specialized agents.

## 2. High-level view

```text
                     NEXT.JS FRONTEND
                            |
                      API GATEWAY
                            |
                 AUTHENTICATION SERVICE
                            |
         +------------------+------------------+
         |                  |                  |
    FACTORY API       QUALITY API        MACHINE API
         |                  |                  |
         +------------------+------------------+
                            |
                    EVENT PROCESSING
                            |
        +-------------------+-------------------+
        |                   |                   |
    IMAGE QUEUE       SENSOR QUEUE      PRODUCTION EVENTS
        |                   |                   |
    VISION AI        PREDICTIVE AI      ANALYTICS ENGINE
        |                   |                   |
        +-------------------+-------------------+
                            |
                 INDUSTRIAL DATA LAYER
                            |
                   ROOT CAUSE ENGINE
                            |
                  LANGGRAPH ORCHESTRATOR
                            |
        +-------------------+-------------------+
        |                   |                   |
   QUALITY AGENT    MAINTENANCE AGENT    PRODUCTION AGENT
        |                   |                   |
        +-------------------+-------------------+
                            |
                  FACTORY INTELLIGENCE
                            |
               REPORTS / ALERTS / APIS
                            |
                     USER DASHBOARD
```

## 3. Layers

| Layer | Technology | Responsibility |
|---|---|---|
| Presentation | Next.js, TypeScript, Tailwind, Recharts, WebSockets | Auth screens, factory dashboard, machine monitoring, inspection UI, investigation UI, reports, admin |
| API / application | Python, FastAPI, Pydantic, SQLAlchemy | Auth integration, business logic, validation, data access, service communication, API docs |
| Event ingestion | MQTT 5.0 (EMQX / Mosquitto), Redis Streams or durable queue | Receive sensor messages, validate schemas, resolve machine identity, route, retry, dead-letter |
| AI/ML services | Independent services | Fabric vision, machine anomaly, failure risk, root cause analytics, production forecasting |
| Agent intelligence | LangGraph, LLM provider abstraction, structured output validation, RAG | Delegation, coordination, evidence retrieval, investigation summaries, recommendations, human approval |
| Storage | PostgreSQL + TimescaleDB, Redis, S3-compatible object store, Qdrant | Operational data, time series, cache/coordination, images and artifacts, embeddings |
| Cloud infrastructure | Docker, managed Postgres/object storage/broker, orchestration as needed, CI/CD, centralized logging | Deployment, scaling, observability |

## 4. Why the event boundary matters

Online ingestion is separated from offline analytics so that a burst of sensor traffic cannot
starve dashboard queries, and a long-running model evaluation cannot delay alerting. Long AI tasks
are always asynchronous: submit, persist a job record, return immediately, notify on completion.

## 5. Deployment model

Next.js on Vercel or containerized hosting; FastAPI on cloud container hosting; managed PostgreSQL;
S3-compatible object storage; managed Redis; managed or secured cloud MQTT broker; model inference
on dedicated containers or managed endpoints; Prometheus and Grafana for monitoring. The system
must not depend on a single cloud vendor.

## 6. Industrial connectivity

- **Method A — simulated telemetry.** Used during research and early development.
- **Method B — MQTT sensor gateway.** Industrial sensors or gateways publish machine data.
- **Method C — factory integration adapter.** Future layer for supported PLC, OPC UA, MES or ERP.

MQTT is appropriate for lightweight machine-to-machine messaging and is standardized by OASIS.
Industrial integration must still follow the factory's own network and security requirements.

## 7. Agent topology

The orchestrator is the only entry point for multi-agent investigations. It classifies intent,
decomposes the task, selects agents, validates every returned contract (schema, evidence
references, timestamps, model version, tenant permission), consolidates results, and routes
consequential recommendations to a human. An agent output that fails validation is rejected and
the run is retried or failed explicitly — never passed through as if it were trustworthy.

## 8. Cloud plus edge

Cloud is the primary architecture. Raw industrial video streamed continuously to the cloud is
expensive and fragile over unreliable links, so the design keeps a factory gateway path open for
camera inference and sensor aggregation.
