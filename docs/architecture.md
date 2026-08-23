# Architecture Diagrams

Source diagrams for the project documentation. GitHub renders Mermaid natively.

## 1. System Architecture

```mermaid
graph TB
    subgraph client["Client Tier"]
        B1["Desktop Browser<br/>1280px+"]
        B2["Tablet<br/>768px"]
        B3["Mobile<br/>390px"]
    end

    subgraph lb["Load Balancing Tier"]
        LB["load_balancer.py<br/>Round-robin proxy<br/>:8000"]
        HC["Health-check thread<br/>scans :5000-5010 every 5s"]
    end

    subgraph app["Application Tier — Flask instances"]
        A1["Instance 1 :5000"]
        A2["Instance 2 :5001"]
        A3["Instance 3 :5002<br/>(added at runtime)"]
    end

    subgraph data["Data Tier"]
        D1[("app1.db")]
        D2[("app2.db")]
        D3[("app3.db")]
    end

    B1 --> LB
    B2 --> LB
    B3 --> LB
    HC -.discovers/evicts.-> LB
    LB -->|request 1| A1
    LB -->|request 2| A2
    LB -->|request 3| A3
    HC -.health probe.-> A1
    HC -.health probe.-> A2
    HC -.health probe.-> A3
    A1 --> D1
    A2 --> D2
    A3 --> D3
```

## 2. Application Structure (Flask blueprints)

```mermaid
graph LR
    subgraph factory["create_app() — app/__init__.py"]
        CFG["config.py<br/>env-driven"]
        LOG["AppLogger<br/>app/logger.py"]
        ERR["403 / 404 / 500<br/>handlers"]
        CLI["flask create-admin"]
    end

    subgraph bp["Blueprints — app/routes/"]
        AU["auth.py<br/>register, login, reset"]
        MA["main.py<br/>catalog, detail"]
        PR["products.py<br/>JSON API"]
        CA["cart.py<br/>cart, checkout"]
        OR["orders.py<br/>history, returns"]
        RV["reviews.py<br/>ratings"]
        AD["admin.py<br/>back office"]
    end

    subgraph models["Models — app/models.py"]
        M["User · Product · Tag<br/>Review · Order<br/>OrderItem · Complaint"]
    end

    factory --> bp
    bp --> models
    models --> DB[("SQLAlchemy<br/>SQLite / PostgreSQL")]
```

## 3. Checkout Flow (with security gates)

```mermaid
sequenceDiagram
    participant U as Shopper
    participant F as Flask app
    participant DB as Database

    U->>F: GET /cart/checkout
    F->>F: @login_required
    alt not authenticated
        F-->>U: redirect to /login
    end
    F-->>U: checkout form + CSRF token

    U->>F: POST /cart/checkout
    F->>F: validate CSRF token
    alt token missing/invalid
        F-->>U: 400 Bad Request
    end
    F->>F: server-side address validation
    alt required field empty
        F-->>U: flash error, redirect back
    end
    F->>DB: INSERT Order + OrderItems
    alt commit fails
        F->>DB: rollback
        F-->>U: "You have not been charged"
    end
    F->>F: clear session cart
    F-->>U: Order confirmation
```

## 4. CI/CD Pipeline

```mermaid
graph LR
    DEV["git push<br/>/ pull request"] --> GH["GitHub Actions"]
    GH --> T1["pytest<br/>131 tests"]
    GH --> T2["Docker build"]
    T1 --> R{"all green?"}
    T2 --> R
    R -->|yes| MERGE["merge to main"]
    R -->|no| FAIL["block merge"]
    MERGE --> RUN["Run on Codio<br/>or Docker"]
```
