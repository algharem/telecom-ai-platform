
## How to Run Phase 3

### 1. Start Complete Platform
# Your Next Steps

## 📋 Prerequisites

- python3 3.10+
- pip or uv package manager

## 🛠️ Installation

```bash

python3 -m venv ~/telecom-env
source ~/telecom-env/bin/activate

============
# Clone or download the project
python3 -m venv ../shared_venv

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  

# Install dependencies
pip install -r requirements.txt
```
```bash

pip install python-json-logger
pip install pytz python-dateutil
pip install -r requirements.txt --prefer-binary
pip install --no-index --find-links=packages -r requirements.txt
```

### Option 3 — Pre-download once (BEST for slow internet)

# Download all dependencies once:
```bash

pip download -r requirements.txt -d packages/

#Then install offline:

pip install --no-index --find-links=packages -r requirements.txt
```

```bash
### Recommended setup for YOU

# Since you’re doing telecom + AI work:

# 👉 Best combo:

python3 -m venv venv --system-site-packages
source venv/bin/activate
pip install -r requirements.txt

AND keep a local package repo:

pip download -r requirements.txt -d ~/pip-packages
``` 
```bash
# Start API (includes all phases)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level warning
```
in other terminal:
python3 -m services.kpi_simulator

### 2. Test xApp Endpoints

#### Check xApp Status
```bash
curl http://localhost:8000/api/v1/xapp/status
```

**Response:**
```json
{
  "xapp_id": "xapp-smart-optimizer",
  "version": "1.0.0",
  "state": "RUNNING",
  "registered_with_ric": true,
  "subscribed_e2_nodes": ["gNB_001", "gNB_002", "gNB_003"],
  "control_loop_active": true,
  "decisions_per_second": 9.8,
  "last_decision_timestamp": "2024-01-15T11:30:45.123Z",
  "total_decisions": 1523,
  "total_actions_executed": 89
}
```

#### Get Recent Decisions
```bash
curl http://localhost:8000/api/v1/xapp/decisions?limit=5
```

**Response:**
```json
[
  {
    "decision_id": "dec-001",
    "xapp_id": "xapp-smart-optimizer",
    "timestamp": "2024-01-15T11:30:45",
    "target_cell": "gNB_001_Cell1",
    "action_type": "LOAD_BALANCING",
    "priority": 2,
    "trigger_metrics": {"current_load": 88.5, "target_load": 45.2},
    "predicted_outcome": "Balance load to gNB_002 [EXECUTED]",
    "confidence": 0.85,
    "control_parameters": {"target_cell": "gNB_002", "handover_candidates": "low_cqi_ues"}
  },
  {
    "decision_id": "dec-002",
    "xapp_id": "xapp-smart-optimizer",
    "timestamp": "2024-01-15T11:30:42",
    "target_cell": "gNB_002_Cell1",
    "action_type": "ADMISSION_CONTROL",
    "priority": 3,
    "trigger_metrics": {"prb_usage": 72.3},
    "predicted_outcome": "Prevent congestion by blocking new users [EXECUTED]",
    "confidence": 0.80,
    "control_parameters": {"admission_rate_limit": 50}
  }
]
```

#### Simulate RAN Metric Injection
```bash
curl -X POST "http://localhost:8000/api/v1/xapp/simulate/ran-metric?gnb_id=gNB_001"
```

#### Check Cell Load
```bash
curl http://localhost:8000/api/v1/xapp/cells/gNB_001/load
```

#### Check Policies
```bash
curl http://localhost:8000/api/v1/xapp/policies
```

---

## Complete Architecture: Phase 1 + 2 + 3

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           5G CORE / RAN                                 │
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│   │     AMF      │     │     SMF      │     │     PCF      │            │
│   │  (Access &   │     │  (Session    │     │  (Policy)    │            │
│   │   Mobility)  │     │   Mgmt)      │     │              │            │
│   └──────┬───────┘     └──────┬───────┘     └──────┬───────┘            │
│          │                    │                    │                      │
│          └────────────────────┴────────────────────┘                      │
│                               │                                         │
│                    Nnwdaf_AnalyticsSubscription                         │
│                    Nnwdaf_AnalyticsInfo_Request                         │
│                               │                                         │
└───────────────────────────────┼─────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      YOUR AI-POWERED PLATFORM                           │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │  Phase 3: O-RAN xApp (Smart Optimizer)                         │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │   │
│  │  │  Admission   │  │    Load      │  │   Handover   │         │   │
│  │  │   Control    │  │  Balancing   │  │   Control    │         │   │
│  │  │  (Block new  │  │  (Move UEs   │  │  (UE redirect│         │   │
│  │  │   users)     │  │   to cells)  │  │   to better  │         │   │
│  │  │              │  │              │  │   signal)    │         │   │
│  │  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘         │   │
│  │         │                 │                 │                  │   │
│  │         └─────────────────┴─────────────────┘                  │   │
│  │                           │                                     │   │
│  │              ┌────────────▼────────────┐                      │   │
│  │              │    Policy Engine          │                      │   │
│  │              │  • Protect emergency calls │                      │   │
│  │              │  • Prevent ping-pong HO   │                      │   │
│  │              │  • CPU overload protection │                      │   │
│  │              └────────────┬────────────┘                      │   │
│  │                           │                                     │   │
│  │              ┌────────────▼────────────┐                      │   │
│  │              │   E2 Interface (E2AP)    │                      │   │
│  │              │  • E2Setup                 │                      │   │
│  │              │  • RICsubscription         │                      │   │
│  │              │  • RICindication           │                      │   │
│  │              │  • RICcontrol              │                      │   │
│  │              └────────────┬────────────┘                      │   │
│  │                           │                                     │   │
│  └───────────────────────────┼─────────────────────────────────────┘   │
│                              │                                          │
│  ┌───────────────────────────┼─────────────────────────────────────┐    │
│  │  Phase 2: NWDAF Analytics │                                     │    │
│  │  ┌──────────────┐  ┌─────▼──────┐  ┌──────────────┐           │    │
│  │  │  Load Level   │  │   Service  │  │   Anomaly    │           │    │
│  │  │  Analytics    │  │ Experience │  │    Events    │           │    │
│  │  │  (Congestion  │  │  (QoS/MOS  │  │  (Exposure   │           │    │
│  │  │   forecast)   │  │  scores)   │  │   to NFs)    │           │    │
│  │  └───────────────┘  └────────────┘  └──────────────┘           │    │
│  │                                                                  │    │
│  │  ┌─────────────────────────────────────────────────────────┐    │    │
│  │  │         Time-Series Database (InfluxDB)                │    │    │
│  │  │    • Historical KPIs    • Forecasting    • Trends       │    │    │
│  │  └─────────────────────────────────────────────────────────┘    │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐     │
│  │  Phase 1: ML Anomaly Detection                                  │     │
│  │  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │     │
│  │  │   Isolation  │    │     KPI      │    │   FastAPI    │     │     │
│  │  │    Forest    │◄───│   Simulator  │◄───│    REST      │     │     │
│  │  │   (Real-time │    │ (Realistic   │    │   Gateway    │     │     │
│  │  │   detection) │    │   RAN data)  │    │              │     │     │
│  │  └──────────────┘    └──────────────┘    └──────────────┘     │     │
│  └─────────────────────────────────────────────────────────────────┘     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         gNBs (E2 Nodes)                                 │
│                                                                         │
│   ┌──────────────┐     ┌──────────────┐     ┌──────────────┐          │
│   │    gNB_001   │     │    gNB_002   │     │    gNB_003   │          │
│   │   ┌──────┐   │     │   ┌──────┐   │     │   ┌──────┐   │          │
│   │   │Cell 1│   │     │   │Cell 1│   │     │   │Cell 1│   │          │
│   │   │Cell 2│   │     │   │Cell 2│   │     │   │Cell 2│   │          │
│   │   └──────┘   │     │   └──────┘   │     │   └──────┘   │          │
│   │              │     │              │     │              │          │
│   │  E2AP: 38472 │     │  E2AP: 38472 │     │  E2AP: 38472 │          │
│   └──────────────┘     └──────────────┘     └──────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---




# Your Next Steps

## 📋 Prerequisites

- python3 3.10+
- pip or uv package manager

## 🛠️ Installation

```bash
# Clone or download the project

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  

# Install dependencies
pip install -r requirements.txt
```


## Week 1-2: Master Phase 1
```bash
# Setup environment
pip install fastapi uvicorn scikit-learn pandas redis httpx slack-sdk openai

# Run each component
python3 telecom_kpi_simulator.py      # Generate data + train models
uvicorn api_server:app --reload      # Test REST API
```

## Week 3-4: Build Phase 2-3
```bash
# Start Redis for NWDAF
docker run -d -p 6379:6379 redis

# Run NWDAF + xApp
python3 nwdaf_analytics_engine.py
python3 oran_xapp_framework.py
```

## Week 5: Add Phase 4 AI
```bash
# Set your OpenAI key
export OPENAI_API_KEY="sk-..."

# Run ChatOps bot
uvicorn aiops_chatbot:app --port 8000
```

## Week 6: Integration
```bash
# Deploy full platform
docker-compose up -d  # Redis + API + xApp
kubectl apply -f k8s-deployment.yaml  # Production
```

---

