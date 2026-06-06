# Backend Architecture

This diagram illustrates the high-level architecture of the MobiKD system and how the backend interacts with external clients and databases.

```mermaid
graph TD
    %% Clients
    subgraph Clients
        Mobile[Flutter Mobile App]
        Admin[Next.js Admin Dashboard]
    end

    %% Backend Service
    subgraph Backend [FastAPI Backend]
        Auth[Authentication Service]
        API[REST API Endpoints]
        ML[Inference Engine (TFLite)]
    end

    %% Databases
    subgraph Database
        SQLite[(SQLite - Local)]
        Postgres[(PostgreSQL - Render)]
    end

    %% Client Connections
    Mobile -->|JSON / Image Data| API
    Admin -->|JSON| API

    %% Internal Routing
    API --> Auth
    API --> ML

    %% Database Connections
    Auth -->|Read/Write| Postgres
    API -->|Read/Write History| Postgres
    
    %% Environment split
    Postgres -.-> |Fallback for Dev| SQLite
    
    style Backend fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    style Postgres fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px
    style SQLite fill:#f3e5f5,stroke:#7b1fa2,stroke-width:2px
```
