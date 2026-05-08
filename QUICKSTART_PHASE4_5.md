# Quick Start: Phase 4 & 5 Integration

This guide walks you through setting up and running the Telecom AI Platform with Phase 4 (Event Streaming) and Phase 5 (ChatOps & Production) features.

## Prerequisites

- Docker & Docker Compose
- Python 3.9+
- Kubernetes cluster (optional, for production)
- AWS account (optional, for Terraform deployment)

## Option 1: Local Development with Docker Compose

### 1. Start the Stack

```bash
# Navigate to project root
cd /vercel/share/v0-project

# Start all services
make docker-up

# Verify services are running
make health
```

This starts:
- API server (localhost:8000)
- Kafka + Zookeeper
- Prometheus (localhost:9090)
- Grafana (localhost:3000)
- PostgreSQL
- Redis
- MQTT broker

### 2. Configure Slack (Optional)

```bash
# Set Slack webhook URL for ChatOps
export SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
export SLACK_BOT_TOKEN=xoxb-your-token

# Restart API
make docker-down
make docker-up
```

### 3. Run Anomaly Detection with Kafka Streaming

**Terminal 1 - Start API:**
```bash
make dev
# API running on http://localhost:8000
```

**Terminal 2 - Start KPI Ingestion Worker:**
```bash
python -m workers.kpi_ingestion_worker
# Worker subscribes to ran-metrics topic and detects anomalies
```

**Terminal 3 - Start Notification Worker:**
```bash
python -m workers.notification_worker
# Worker sends incident alerts to Slack
```

### 4. Test the Pipeline

```bash
# Get metrics from Prometheus (auto-fetch)
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{"gnb_id": "gNB-001"}'

# Manual metric submission
curl -X POST http://localhost:8000/api/v1/ml/predict \
  -H "Content-Type: application/json" \
  -d '{
    "gnb_id": "gNB-001",
    "metrics": {
      "prb_usage": 95,
      "throughput": 100,
      "latency": 80,
      "packet_loss": 5
    }
  }'

# Check data source status
curl http://localhost:8000/api/v1/ml/data-source/status

# View Prometheus metrics
curl http://localhost:9090/api/v1/targets
```

### 5. Monitor with Grafana

- Open http://localhost:3000
- Default credentials: admin/admin
- Add Prometheus datasource: http://prometheus:9090
- Create dashboards for:
  - Anomaly detection metrics
  - Kafka consumer lag
  - API latency
  - Resource usage

### 6. View Kafka Topics

```bash
# List topics
make kafka-console

# Monitor specific topic
docker-compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic anomalies \
  --from-beginning

# Monitor another topic
docker-compose exec kafka kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic incidents \
  --from-beginning
```

## Option 2: Kubernetes Deployment

### 1. Create Namespace and Secrets

```bash
# Create namespace
kubectl create namespace telecom-ai

# Create secrets for sensitive data
kubectl create secret generic telecom-ai-secrets \
  --from-literal=slack_webhook_url=https://hooks.slack.com/... \
  --from-literal=openai_api_key=sk-... \
  -n telecom-ai

# Create ConfigMap
kubectl create configmap telecom-ai-config \
  --from-literal=prometheus_url=http://prometheus:9090 \
  -n telecom-ai
```

### 2. Deploy to Kubernetes

```bash
# Deploy API and HPA
kubectl apply -f deployment/kubernetes/ -n telecom-ai

# Verify deployment
kubectl get deployments,pods,svc -n telecom-ai

# Check logs
kubectl logs -f deployment/telecom-ai-api -n telecom-ai
```

### 3. Access Services

```bash
# Port-forward to API
kubectl port-forward svc/telecom-ai-api 8000:8000 -n telecom-ai

# Test API
curl http://localhost:8000/health
```

## Option 3: AWS Production Deployment with Terraform

### 1. Prerequisites

```bash
# Install Terraform
terraform version  # should be >= 1.0

# Configure AWS credentials
aws configure

# Create S3 bucket for Terraform state
aws s3 mb s3://telecom-ai-tf-state
aws s3api put-bucket-versioning \
  --bucket telecom-ai-tf-state \
  --versioning-configuration Status=Enabled
```

### 2. Plan Infrastructure

```bash
cd deployment/terraform

# Initialize Terraform
make tf-init

# Review plan
make tf-plan
```

### 3. Deploy Infrastructure

```bash
# Apply Terraform
make tf-apply

# Get outputs
terraform output eks_cluster_endpoint
terraform output rds_endpoint
terraform output kafka_bootstrap_servers
```

### 4. Deploy Application

```bash
# Configure kubectl
aws eks update-kubeconfig --name telecom-ai-eks

# Deploy to EKS
kubectl apply -f ../kubernetes/
```

## Common Tasks

### Start Only Specific Services

```bash
# API only
docker-compose up api

# Kafka only
docker-compose up kafka zookeeper

# Monitoring only
docker-compose up prometheus grafana
```

### Check Worker Status

```bash
# KPI Ingestion Worker stats
curl http://localhost:8001/stats

# Notification Worker stats
curl http://localhost:8002/stats
```

### View Logs

```bash
# All services
make docker-logs

# Specific service
docker-compose logs -f kafka

# API logs
docker-compose logs -f api
```

### Scale Kubernetes Deployment

```bash
# Manual scale
kubectl scale deployment telecom-ai-api --replicas=5

# Check HPA status
kubectl get hpa -n telecom-ai
```

### Monitor Kafka Lag

```bash
# Check consumer group lag
docker-compose exec kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group anomaly-processor \
  --describe
```

## Troubleshooting

### API won't start

```bash
# Check for port conflicts
netstat -tlnp | grep 8000

# Check logs
docker-compose logs api

# Restart fresh
make docker-clean
make docker-up
```

### Kafka topics not created

```bash
# Manually create topics
docker-compose exec kafka kafka-topics.sh \
  --create \
  --topic ran-metrics \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 2
```

### Workers not detecting anomalies

```bash
# Check Prometheus connectivity
curl http://localhost:9090/api/v1/targets

# Verify metrics are available
curl 'http://localhost:9090/api/v1/query?query=up'

# Check worker logs
docker-compose logs -f kpi-ingestion-worker
```

### Slack notifications not working

```bash
# Verify webhook URL
export SLACK_WEBHOOK_URL=your-webhook-url
curl -X POST $SLACK_WEBHOOK_URL \
  -d '{"text":"Test message"}'

# Check notification worker logs
docker-compose logs -f notification-worker
```

## Performance Tuning

### Increase Anomaly Detection Throughput

```yaml
# docker-compose.yml
kpi_ingestion_worker:
  environment:
    KAFKA_BATCH_SIZE: 100
    KAFKA_LINGER_MS: 100
```

### Optimize Kafka for Low Latency

```bash
# Reduce broker config
docker-compose exec kafka kafka-configs.sh \
  --bootstrap-server localhost:9092 \
  --alter \
  --entity-type brokers \
  --entity-name 0 \
  --add-config 'linger.ms=0'
```

### Scale Resource Limits

```bash
# Increase API resources
kubectl set resources deployment telecom-ai-api \
  --limits=cpu=2000m,memory=2Gi \
  --requests=cpu=1000m,memory=1Gi
```

## Next Steps

1. **Configure monitoring**: Create Grafana dashboards for anomalies and incidents
2. **Tune parameters**: Adjust anomaly thresholds and KPI derivation factors
3. **Set up alerts**: Configure Prometheus alerting rules
4. **Implement recovery**: Add automatic recovery actions for common incidents
5. **Multi-gNB**: Scale to multiple base stations with load balancing

## Support

For issues or questions:
1. Check logs: `make docker-logs` or `kubectl logs`
2. Review documentation: See `PHASE_4_5_MERGED.md`
3. Test connectivity: `make health`
4. Verify configuration: `make status`

---

**Ready to start?** Run `make docker-up` to begin!
