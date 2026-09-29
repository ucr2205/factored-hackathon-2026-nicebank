---
tags: [arquitectura, datos, er]
actualizado: 2026-09-29
---

# Modelo ER

> [!tip] Cómo verlo
> Obsidian dibuja estos diagramas solo (Mermaid). Hay dos modelos: la **capa silver** (lo que produce
> `make etl`, en vocabulario canónico del diccionario) y la **base operativa** (contrato C1, lo que usa
> el sistema). Se muestran las columnas clave; el detalle completo por columna está en
> `docs/etl_rules.md` y `infra/postgres/init/01_schema.sql`.

## 1. Capa silver (dataset saneado, `data/silver/`)

Dimensiones y hechos del dataset más las tres dimensiones creadas por la normalización 3FN
(`dim_cities`, `dim_merchants`, `dim_categories`). Las relaciones punteadas del origen que **no se
cumplen** en los datos (sucursal de registro inexistente) no se dibujan: quedaron como banderas.

```mermaid
erDiagram
    CUSTOMERS ||--o{ PRODUCTS : "posee"
    CUSTOMERS ||--o{ TRANSACTIONS : "realiza"
    PRODUCTS ||--o{ TRANSACTIONS : "instrumenta"
    CUSTOMERS ||--o{ COMPLAINTS : "presenta"
    CUSTOMERS ||--o{ CALL_CENTER_INTERACTIONS : "contacta"
    SERVICE_AGENTS ||--o{ CALL_CENTER_INTERACTIONS : "atiende"
    CALL_CENTER_INTERACTIONS ||--o| CALL_TRANSCRIPTS : "transcribe"
    CALL_CENTER_INTERACTIONS ||--o{ SATISFACTION_SURVEYS : "evalua"
    MARKETING_CAMPAIGNS ||--o{ CAMPAIGN_SENDS : "envia"
    CUSTOMERS ||--o{ CAMPAIGN_SENDS : "recibe"
    CUSTOMERS |o--o{ DIGITAL_EVENTS : "genera"
    DIM_CITIES ||--o{ CUSTOMERS : "ubica"
    DIM_CITIES ||--o{ BRANCHES : "ubica"
    DIM_MERCHANTS |o--o{ TRANSACTIONS : "clasifica"
    DIM_CATEGORIES ||--o{ COMPLAINTS : "detalla"
    DAILY_EXCHANGE_RATES ||..o{ TRANSACTIONS : "convierte a USD"

    CUSTOMERS {
        varchar customer_id PK
        varchar document_number UK "unico (diccionario)"
        varchar document_type "DNI CURP CC CE Passport"
        varchar email "nulo si compartido + flag"
        varchar city FK "state vive en dim_cities"
        varchar country "Mexico Colombia Argentina"
        varchar segment
        boolean email_shared "flag saneamiento"
        boolean branch_unresolved "sucursal de registro rota"
    }
    PRODUCTS {
        varchar product_id PK
        varchar customer_id FK
        varchar product_type "Credit Card, Debit Card, ..."
        varchar card_last4 "el numero completo no llega a silver"
        varchar card_brand "visa mastercard amex other"
        varchar currency
        varchar product_status
        boolean expired_active_card "flag"
    }
    TRANSACTIONS {
        varchar transaction_id PK
        varchar product_id FK
        varchar customer_id FK "desnormalizado a proposito (RLS)"
        timestamp transaction_date "fecha de negocio"
        date event_date "derivada; process_date solo es carga"
        double amount
        double amount_usd "recalculada con tasa del dia"
        varchar merchant_name FK
        boolean is_international
        boolean is_fraud "solo etiqueta de evaluacion"
    }
    COMPLAINTS {
        varchar complaint_id PK
        varchar customer_id FK
        varchar category FK "subcategoria en dim_categories"
        varchar status
        double claimed_amount "ruido: no liga a transaccion"
    }
    CALL_CENTER_INTERACTIONS {
        varchar interaction_id PK
        varchar customer_id FK
        varchar agent_id FK
        varchar reason_category "contact_reason era identica"
        boolean was_resolved "solo etiqueta de evaluacion"
    }
    CALL_TRANSCRIPTS {
        varchar transcript_id PK
        varchar interaction_id FK
        varchar full_text "2 plantillas de saldo, sin disputas"
    }
    SATISFACTION_SURVEYS {
        varchar survey_id PK
        varchar interaction_id FK
        varchar survey_type "CSAT NPS CES"
        bigint main_score
    }
    CAMPAIGN_SENDS {
        varchar send_id PK
        varchar campaign_id FK
        varchar customer_id FK
    }
    DIGITAL_EVENTS {
        varchar event_id PK
        varchar customer_id FK "nulo 24%"
        varchar session_id
        varchar event_type
    }
    BRANCHES {
        varchar branch_id PK
        varchar branch_code UK
        varchar city FK
    }
    SERVICE_AGENTS {
        varchar agent_id PK
        varchar employee_code UK "nulo si conflicto + flag"
        varchar email UK
        varchar languages
        varchar specialty
    }
    MARKETING_CAMPAIGNS {
        varchar campaign_id PK
        varchar campaign_type
    }
    DAILY_EXCHANGE_RATES {
        date rate_date PK
        varchar source_currency PK
        varchar target_currency PK
        double exchange_rate
    }
    DIM_CITIES {
        varchar city PK
        varchar state
        varchar country
    }
    DIM_MERCHANTS {
        varchar merchant_name PK
        varchar merchant_category
    }
    DIM_CATEGORIES {
        varchar category PK
        varchar subcategory
    }
```

## 2. Base operativa (contrato C1, Postgres)

Lo que carga `make seed` (`etl/load_postgres.py`) más las tablas que escribe el propio sistema. Todas
las tablas de cliente están bajo RLS; la identidad vive **cifrada** y separada ([[Seguridad]]).

```mermaid
erDiagram
    customers ||--o{ products : "posee"
    customers ||--o{ transactions : "realiza"
    products ||--o{ transactions : "instrumenta"
    customers ||--|| customer_identity : "seudonimiza"
    customers ||--o{ chat_sessions : "conversa"
    chat_sessions ||--o{ messages : "contiene"
    chat_sessions ||--o{ pending_actions : "propone"
    transactions ||--o{ dispute_cases : "disputa"
    products ||--o{ card_blocks : "bloquea"
    chat_sessions ||--o{ handoffs : "escala"
    chat_sessions ||--o{ notifications : "notifica"
    customers ||--o{ audit_events : "audita"
    daily_exchange_rates ||..o{ transactions : "convierte"

    customers {
        text customer_id PK
        text country
        text segment
        text customer_status "sin nombres: ver customer_identity"
    }
    customer_identity {
        text customer_ref PK "unico id que viaja en el token"
        text customer_id FK,UK
        bytea first_name_ct "AES-256-GCM"
        bytea last_name_ct
        bytea email_ct "clienteNN@example.test en demo"
    }
    products {
        text product_id PK
        text customer_id FK
        text product_type "Credit Card, ..."
        text card_last4
        text card_brand
    }
    transactions {
        text transaction_id PK
        text customer_id FK
        text product_id FK
        timestamptz transaction_date
        numeric amount
        numeric amount_usd
        text origin "organizer_synthetic o team_generated"
    }
    chat_sessions {
        uuid session_id PK
        text customer_id FK "RLS lo fija por transaccion"
        jsonb state
    }
    messages {
        bigserial id PK
        uuid session_id FK
        text role "customer o assistant"
    }
    pending_actions {
        uuid action_id PK
        uuid session_id FK
        text action_type "open_dispute_case o block_card"
        text status
    }
    dispute_cases {
        text case_id PK "DSP-000000"
        text transaction_id FK
        text idempotency_key UK
    }
    card_blocks {
        text block_id PK "BLK-000000"
        text product_id FK
    }
    handoffs {
        uuid handoff_id PK
        uuid session_id FK
        text status "open claimed closed"
        text claimed_by
    }
    audit_events {
        bigserial id PK
        uuid session_id
        text step
        text policy_rule_id
    }
    notifications {
        bigserial id PK
        uuid session_id FK
        text kind
        text status "outbox: pending sending sent failed"
    }
    daily_exchange_rates {
        date rate_date PK
        text source_currency PK
        text target_currency PK
    }
    service_agents {
        text agent_id PK
        text languages
        text specialty
    }
    kb_chunks {
        bigserial id PK
        vector embedding "384 dims (RAG, P3)"
    }
```

Notas de lectura: `..` = relación lógica (sin FK física); `UK` = único; los flags booleanos de
saneamiento están en [[Datos del proyecto#Validación de duplicados (29 sep)]] y `docs/etl_rules.md`.
