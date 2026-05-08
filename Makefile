.PHONY: help install dev test lint format clean docker-build docker-up docker-down k8s-deploy tf-plan tf-apply

help:
	@echo "Telecom AI Platform - Make Commands"
	@echo "===================================="
	@echo ""
	@echo "Development:"
	@echo "  make install        - Install dependencies"
	@echo "  make dev            - Run development server"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run linters"
	@echo "  make format         - Format code with black/isort"
	@echo ""
	@echo "Docker & Local Deployment:"
	@echo "  make docker-build   - Build Docker image"
	@echo "  make docker-up      - Start docker-compose stack"
	@echo "  make docker-down    - Stop docker-compose stack"
	@echo "  make docker-logs    - View docker-compose logs"
	@echo ""
	@echo "Kubernetes Deployment:"
	@echo "  make k8s-deploy     - Deploy to Kubernetes"
	@echo "  make k8s-logs       - View pod logs"
	@echo ""
	@echo "Infrastructure (Terraform):"
	@echo "  make tf-plan        - Plan Terraform changes"
	@echo "  make tf-apply       - Apply Terraform changes"
	@echo "  make tf-destroy     - Destroy AWS infrastructure"
	@echo ""

install:
	pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest -v

lint:
	flake8 . --max-line-length=100
	mypy . --ignore-missing-imports

format:
	black . --line-length=100
	isort . --profile=black

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache .mypy_cache htmlcov .coverage

docker-build:
	docker build -t telecom-ai-platform:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-clean: docker-down
	docker-compose rm -v

k8s-deploy:
	@echo "Creating namespace..."
	kubectl create namespace telecom-ai || true
	@echo "Deploying API..."
	kubectl apply -f deployment/kubernetes/api-deployment.yaml
	@echo "Deploying HPA..."
	kubectl apply -f deployment/kubernetes/hpa.yaml
	@echo "Deployment complete!"
	kubectl get pods -n default

k8s-logs:
	kubectl logs -f deployment/telecom-ai-api

k8s-clean:
	kubectl delete -f deployment/kubernetes/

tf-init:
	cd deployment/terraform && terraform init

tf-plan:
	cd deployment/terraform && terraform plan -var-file=prod.tfvars

tf-apply:
	cd deployment/terraform && terraform apply -var-file=prod.tfvars

tf-destroy:
	cd deployment/terraform && terraform destroy -var-file=prod.tfvars

# Development helpers
metrics-producer:
	python -m workers.kpi_ingestion_worker

notification-worker:
	python -m workers.notification_worker

prometheus:
	docker-compose up prometheus grafana

kafka-console:
	docker-compose exec kafka bash -c 'kafka-topics.sh --list --bootstrap-server localhost:9092'

# Application health checks
health:
	curl -X GET http://localhost:8000/health

ready:
	curl -X GET http://localhost:8000/ready

status:
	curl -X GET http://localhost:8000/api/v1/ml/data-source/status

# Production checks
prod-logs:
	kubectl logs -f -l app=telecom-ai-api --tail=100

prod-status:
	kubectl get deployments,pods,svc -l app=telecom-ai

prod-metrics:
	kubectl top nodes
	kubectl top pods -l app=telecom-ai
