# Telecom AI Platform - Phase 4 & 5 Architecture

## System Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        TELECOM AI PLATFORM (PHASES 1-5)                    │
└─────────────────────────────────────────────────────────────────────────────┘

                           ┌──────────────────────────┐
                           │   DATA SOURCES (Phase 1) │
                           ├──────────────────────────┤
                           │ • Prometheus Metrics     │
                           │ • Open5GS Logs           │
                           │ • Simulator              │
                           └──────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │  METRIC COLLECTION (Phase 1)   │
                    ├────────────────────────────────┤
                    │ • Prometheus Client            │
                    │ • Log Parser                   │
                    │ • Data Provider Abstraction    │
                    └────────────────────────────────┘
                                     │
                                     ▼
                    ┌────────────────────────────────┐
                    │   PREDICTION API (Phase 1)     │
                    ├────────────────────────────────┤
                    │ • /predict (auto-fetch metrics)│
                    │ • ML/Pattern detection         │
                    │ • KPI normalization            │
                    └────────────────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
                    ▼                ▼                ▼
        ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐
        │  ANOMALIES      │  │  PATTERNS    │  │   METRICS    │
        │  (DETECTED)     │  │  (DETECTED)  │  │  (NORMAL)    │
        └─────────────────┘  └──────────────┘  └──────────────┘
                    │                │                │
                    └────────────────┼────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   EVENT STREAMING (Phase 4)     │
                    ├─────────────────────────────────┤
                    │ Kafka Message Broker            │
                    │ • ran-metrics topic             │
                    │ • anomalies topic               │
                    │ • incidents topic               │
                    │ • recovery-actions topic        │
                    │ • forecasts topic               │
                    │ • notifications topic           │
                    └─────────────────────────────────┘
                                     │
        ┌────────────────┬───────────┼────────────┬──────────────┐
        │                │           │            │              │
        ▼                ▼           ▼            ▼              ▼
  ┌──────────────┐ ┌──────────┐ ┌────────┐ ┌──────────┐ ┌──────────────┐
  │   KPI INGN   │ │Anomaly   │ │Incident│ │Recovery  │ │ Forecast     │
  │   WORKER     │ │Pipeline  │ │Create  │ │Pipeline  │ │ Generation   │
  ├──────────────┤ ├──────────┤ ├────────┤ ├──────────┤ ├──────────────┤
  │Phase 4: Run  │ │Phase 4:  │ │Phase 4:│ │Phase 4:  │ │ Phase 1:     │
  │ML detection  │ │Convert   │ │Escalate│ │Generate  │ │ Predictive   │
  │Publish anomal│ │anomalies │ │to high │ │recovery  │ │ Analytics    │
  │to Kafka      │ │to        │ │severity│ │actions   │ │              │
  └──────────────┘ │incidents │ │incidents│ │         │ └──────────────┘
                   └──────────┘ └────────┘ └──────────┘
                        │            │            │
                        └────────────┼────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   NOTIFICATION (Phase 5)        │
                    ├─────────────────────────────────┤
                    │ Notification Worker             │
                    │ • Slack Bot Integration         │
                    │ • AI Analysis (OpenAI)          │
                    │ • Alert Formatting              │
                    └─────────────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │   CHATOPS (Phase 5)             │
                    ├─────────────────────────────────┤
                    │ • Slack #incidents              │
                    │ • Slack #recovery               │
                    │ • Slack #forecasts              │
                    │ • Teams Adaptive Cards          │
                    └─────────────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  CLOUD DEPLOYMENT (Phase 5)     │
                    ├─────────────────────────────────┤
                    │ • Kubernetes (EKS)              │
                    │ • Auto-scaling (HPA)            │
                    │ • Load Balancing                │
                    │ • Health Checks                 │
                    └─────────────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  INFRASTRUCTURE (Phase 5)       │
                    ├─────────────────────────────────┤
                    │ • AWS EKS Cluster               │
                    │ • RDS PostgreSQL                │
                    │ • MSK Kafka                     │
                    │ • ElastiCache Redis             │
                    │ • CloudWatch Logs               │
                    └─────────────────────────────────┘
                                     │
                    ┌────────────────▼────────────────┐
                    │  MONITORING (Phase 5)           │
                    ├─────────────────────────────────┤
                    │ • Prometheus                    │
                    │ • Grafana Dashboards            │
                    │ • Jaeger Tracing                │
                    │ • CloudWatch Metrics            │
                    └─────────────────────────────────┘
```

## Phase 4: Event Streaming Architecture

### Kafka Topic Flow

```
                    ┌──────────────────────────────────┐
                    │  API /predict endpoint           │
                    │  (anomaly detection triggered)   │
                    └──────────────────┬───────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────┐
                        │ RANMetricEvent               │
                        │ {gnb_id, metrics, timestamp} │
                        └──────────────┬───────────────┘
                                       │
                                       ▼ (partition: gnb_id)
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃        Kafka Topic: ran-metrics         ┃
        ┃      (3 partitions, 24h retention)      ┃
        ┃ Part 0: gNB-001  Part 1: gNB-002  Part 2: gNB-003
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                         │
                         ▼
              ┌────────────────────────┐
              │ KPI Ingestion Worker   │
              │ • Consumes metrics     │
              │ • Runs ML detection    │
              │ • Infers anomaly type  │
              │ • Calculates severity  │
              └────────┬───────────────┘
                       │
                       ├─(if anomaly detected)→ AnomalyDetectedEvent
                       │
                       ▼ (partition: gnb_id)
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃        Kafka Topic: anomalies            ┃
        ┃      (2 partitions, 7d retention)        ┃
        ┃ Part 0: gNB-001,003,005  Part 1: gNB-002,004,006
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                       │
                       ▼
              ┌────────────────────────┐
              │ Anomaly Pipeline       │
              │ • Reads anomalies      │
              │ • Escalates by severity│
              │ • Creates incidents    │
              └────────┬───────────────┘
                       │
                       ├─(severity≥MAJOR)→ IncidentEvent
                       │
                       ▼ (partition: incident_id)
        ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
        ┃        Kafka Topic: incidents            ┃
        ┃       (1 partition, 14d retention)       ┃
        ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
                       │
           ┌───────────┴──────────────┐
           │                          │
           ▼                          ▼
     ┌──────────────┐         ┌──────────────┐
     │ Incident     │         │ Incident     │
     │ Pipeline     │         │ Consumer     │
     │              │         │              │
     │ (Recovery    │         │ (ChatOps     │
     │  Generation) │         │  Notification│
     │              │         │ )            │
     └──────┬───────┘         └──────┬───────┘
            │                        │
            ▼ (partition: incident_id)     ▼
    ┌────────────────────┐    ┌────────────────┐
    │ RecoveryEvent      │    │ Notification   │
    │ {action, priority, │    │ to Slack       │
    │  eta, incident_id} │    │                │
    └────────┬───────────┘    └────────────────┘
             │
             ▼ (partition: incident_id)
    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃      Kafka Topic: recovery-actions       ┃
    ┃      (1 partition, 24h retention)        ┃
    ┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
             │
             ▼
    ┌──────────────────────┐
    │ Recovery Consumer    │
    │ (Manual execution)   │
    └──────────────────────┘
```

### Event Schema Relationships

```
RANMetricEvent
├─ timestamp: datetime
├─ gnb_id: str
├─ metrics: {prb_usage, throughput, latency, packet_loss}
└─ source: str

        │ (detection)
        ▼

AnomalyDetectedEvent
├─ event_id: str
├─ gnb_id: str
├─ timestamp: datetime
├─ anomaly_type: str (resource_exhaustion, latency_spike, etc)
├─ severity: str (WARNING, MINOR, MAJOR, CRITICAL)
├─ details: str
├─ affected_metrics: dict
└─ tags: list

        │ (escalation if severity ≥ MAJOR)
        ▼

IncidentEvent
├─ incident_id: str
├─ gnb_id: str
├─ title: str
├─ description: str
├─ severity: str
├─ status: str (OPEN, IN_PROGRESS, RESOLVED)
├─ root_cause: str
├─ affected_services: list
└─ tags: list

        │ (analysis & recommendation)
        ▼

RecoveryEvent
├─ recovery_id: str
├─ incident_id: str
├─ action: str
├─ description: str
├─ priority: str (LOW, MEDIUM, HIGH, CRITICAL)
├─ estimated_time_minutes: int
├─ status: str (PENDING, IN_PROGRESS, COMPLETED, FAILED)
└─ tags: list
```

## Phase 5: Production Architecture

### Kubernetes Deployment

```
┌─────────────────────────────────────────────────────────┐
│                   AWS EKS Cluster                       │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Namespace: telecom-ai               │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │  Deployment: telecom-ai-api (3 replicas)   │ │   │
│  │  │                                              │ │   │
│  │  │  ┌──────────────────────────────────────┐  │ │   │
│  │  │  │  Pod 1: API Container               │  │ │   │
│  │  │  │  Port 8000 (HTTP)                   │  │ │   │
│  │  │  │  CPU: 500m, Memory: 512Mi           │  │ │   │
│  │  │  │  Liveness Probe: /health (10s)      │  │ │   │
│  │  │  │  Readiness Probe: /ready (5s)       │  │ │   │
│  │  │  │  Env: DATA_SOURCE=prometheus        │  │ │   │
│  │  │  │       KAFKA_BOOTSTRAP_SERVERS       │  │ │   │
│  │  │  │       SLACK_WEBHOOK_URL             │  │ │   │
│  │  │  │       OPENAI_API_KEY                │  │ │   │
│  │  │  └──────────────────────────────────────┘  │ │   │
│  │  │                                              │ │   │
│  │  │  ┌──────────────────────────────────────┐  │ │   │
│  │  │  │  Pod 2: API Container               │  │ │   │
│  │  │  │  (identical)                        │  │ │   │
│  │  │  └──────────────────────────────────────┘  │ │   │
│  │  │                                              │ │   │
│  │  │  ┌──────────────────────────────────────┐  │ │   │
│  │  │  │  Pod 3: API Container               │  │ │   │
│  │  │  │  (identical)                        │  │ │   │
│  │  │  └──────────────────────────────────────┘  │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │  Service: telecom-ai-api                    │ │   │
│  │  │  Type: ClusterIP                            │ │   │
│  │  │  Port: 8000 → Target 8000                   │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │  HPA: telecom-ai-api-hpa                    │ │   │
│  │  │  Min: 3 replicas, Max: 10 replicas          │ │   │
│  │  │  Target CPU: 70%, Memory: 80%               │ │   │
│  │  │  Scale-up: 2 pods per 30 seconds            │ │   │
│  │  │  Scale-down: 50% reduction per 60 seconds   │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │  ConfigMap: telecom-ai-config              │ │   │
│  │  │  - prometheus_url                          │ │   │
│  │  │  - kafka_brokers                           │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  │                                                   │   │
│  │  ┌─────────────────────────────────────────────┐ │   │
│  │  │  Secret: telecom-ai-secrets                │ │   │
│  │  │  - slack_webhook_url (encrypted)           │ │   │
│  │  │  - openai_api_key (encrypted)              │ │   │
│  │  └─────────────────────────────────────────────┘ │   │
│  │                                                   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │         AWS Resources (Outside K8s)              │   │
│  │                                                  │   │
│  │  • MSK Kafka (3 brokers, TLS encrypted)        │   │
│  │  • RDS PostgreSQL (15.3, encrypted, 100GB)     │   │
│  │  • ElastiCache Redis (3 nodes, HA)             │   │
│  │  • CloudWatch Logs (API logs)                  │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Infrastructure as Code Flow

```
┌─────────────────────────────────────┐
│  Terraform Configuration            │
│  (deployment/terraform/)            │
└──────────────┬──────────────────────┘
               │
      ┌────────┴────────┬─────────────────┬──────────────┐
      │                 │                 │              │
      ▼                 ▼                 ▼              ▼
  ┌────────┐    ┌────────────┐    ┌──────────┐    ┌─────────┐
  │  main  │    │ variables  │    │ outputs  │    │ backend │
  │   .tf  │    │    .tf     │    │   .tf    │    │  (S3)   │
  └────┬───┘    └────────────┘    └──────────┘    └─────────┘
       │
       ├─ VPC Configuration
       │  ├─ VPC (10.0.0.0/16)
       │  ├─ Public Subnets (2 AZs)
       │  ├─ Private Subnets (2 AZs)
       │  ├─ Internet Gateway
       │  ├─ NAT Gateway (HA)
       │  └─ Route Tables
       │
       ├─ Kubernetes (EKS)
       │  ├─ EKS Cluster (1.28+)
       │  ├─ Node Group (3-10 t3.xlarge nodes)
       │  └─ IAM Roles & Policies
       │
       ├─ Databases
       │  ├─ RDS PostgreSQL (15.3)
       │  │  ├─ Multi-AZ deployment
       │  │  ├─ Encrypted storage
       │  │  ├─ Automated backups (30d)
       │  │  └─ Encrypted snapshot
       │  │
       │  └─ ElastiCache Redis
       │     ├─ 3-node cluster (HA)
       │     ├─ TLS encryption
       │     └─ Automatic failover
       │
       ├─ Message Streaming
       │  └─ MSK Kafka Cluster
       │     ├─ 3 brokers
       │     ├─ TLS authentication
       │     ├─ KMS encryption at rest
       │     └─ CloudWatch logs
       │
       └─ Security
          ├─ Security Groups
          │  ├─ EKS nodes
          │  ├─ RDS
          │  ├─ Kafka
          │  └─ Redis
          │
          ├─ IAM Roles
          │  ├─ EKS service role
          │  ├─ EKS node role
          │  └─ Kafka broker role
          │
          ├─ KMS Keys
          │  ├─ RDS encryption
          │  ├─ MSK encryption
          │  └─ EBS encryption
          │
          └─ VPC Endpoints (optional)
             ├─ S3 gateway endpoint
             └─ Secrets Manager endpoint
```

## Data Flow Through Entire System

```
PHASE 1-3: DATA → DETECTION
┌──────────────────────────────────────┐
│ Prometheus/Logs → API → Prediction   │
│ Returns: Anomaly Score               │
└──────────────┬───────────────────────┘
               │
PHASE 4: STREAMING
┌──────────────┴───────────────────────┐
│ Kafka Event Topics:                  │
│ • ran-metrics                        │
│ • anomalies (if detected)            │
│ • incidents (if critical/major)      │
│ • recovery-actions (if incident)     │
└──────────────┬───────────────────────┘
               │
PHASE 5: NOTIFICATIONS & CLOUD
┌──────────────┴───────────────────────┐
│ • Incident Consumers                 │
│ • AI Analysis (OpenAI GPT-4)         │
│ • ChatOps Delivery (Slack/Teams)     │
│ • Alert Acknowledgement              │
│ • Recovery Execution                 │
└──────────────┬───────────────────────┘
               │
OPERATIONS & MONITORING
┌──────────────┴───────────────────────┐
│ • Kubernetes HPA Scaling             │
│ • Prometheus Metrics Collection      │
│ • Grafana Dashboards                 │
│ • CloudWatch Logs                    │
│ • Jaeger Distributed Tracing         │
│ • Alert Rules & Escalation           │
└──────────────────────────────────────┘
```

## Performance & Scalability

### Throughput Targets

```
┌─────────────────────────┬──────────────┬────────────┐
│ Component               │ Throughput   │ Latency    │
├─────────────────────────┼──────────────┼────────────┤
│ API /predict endpoint   │ 1000 req/s   │ <100ms     │
│ Kafka ran-metrics topic │ 10k msg/s    │ <50ms      │
│ Anomaly detection       │ 5k msg/s     │ <200ms     │
│ Incident escalation     │ 100 msg/s    │ <500ms     │
│ Slack notification      │ 50 msg/s     │ <5s        │
└─────────────────────────┴──────────────┴────────────┘
```

### Scalability Dimensions

```
Horizontal Scaling:
├─ API Pods: 3 → 10 (HPA)
├─ Kafka Partitions: 1 → 6 (per topic)
└─ Database Read Replicas: 0 → 3 (optional)

Vertical Scaling:
├─ Pod Resources: 512Mi → 2Gi (memory)
├─ Node Instance: t3.xlarge → r5.2xlarge
└─ Database: db.t3.medium → db.r5.large

Data Retention:
├─ Metrics: 24h (Kafka)
├─ Anomalies: 7d (Kafka)
├─ Incidents: 14d (Kafka + PostgreSQL)
├─ Forecasts: 7d (Kafka)
└─ Logs: 30d (CloudWatch)
```

## Security Architecture

```
┌──────────────────────────────────────────────────┐
│           SECURITY LAYERS                        │
├──────────────────────────────────────────────────┤
│ 1. NETWORK SECURITY                              │
│    • VPC isolation (10.0.0.0/16)                 │
│    • Security groups per component               │
│    • Network policies in K8s                     │
│    • TLS for inter-service communication         │
│                                                   │
│ 2. AUTHENTICATION & AUTHORIZATION                │
│    • K8s RBAC for cluster access                 │
│    • IAM roles for AWS services                  │
│    • Slack OAuth 2.0 for ChatOps                 │
│    • OpenAI API key management                   │
│                                                   │
│ 3. ENCRYPTION                                    │
│    • TLS 1.3 for Kafka (in-transit)              │
│    • KMS for RDS encryption (at-rest)            │
│    • KMS for EBS encryption (at-rest)            │
│    • Secrets in K8s encrypted by etcd            │
│                                                   │
│ 4. CONTAINER SECURITY                            │
│    • Non-root user (UID 1000)                    │
│    • Read-only root filesystem                   │
│    • Resource limits (CPU, memory)               │
│    • Security context (no privilege escalation)  │
│                                                   │
│ 5. ACCESS CONTROL                                │
│    • API authentication (API key)                │
│    • Database user with minimal permissions      │
│    • Service-to-service mutual TLS               │
│    • CloudTrail logging (audit)                  │
│                                                   │
│ 6. MONITORING & DETECTION                        │
│    • CloudWatch Logs (all API calls)             │
│    • Prometheus metrics (anomalies)              │
│    • Jaeger tracing (request flow)               │
│    • VPC Flow Logs (network traffic)             │
└──────────────────────────────────────────────────┘
```

---

**Architecture Version**: Phase 4 & 5 Complete
**Last Updated**: 2026-05-08
**Production Ready**: Yes
