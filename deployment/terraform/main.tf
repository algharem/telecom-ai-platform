terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  
  backend "s3" {
    bucket         = "telecom-ai-tf-state"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "telecom-ai-platform"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  tags = {
    Name = "telecom-ai-vpc"
  }
}

# Subnets
resource "aws_subnet" "public" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  map_public_ip_on_launch = true
  
  tags = {
    Name = "telecom-ai-public-${count.index + 1}"
  }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.private_subnet_cidrs[count.index]
  availability_zone = data.aws_availability_zones.available.names[count.index]
  
  tags = {
    Name = "telecom-ai-private-${count.index + 1}"
  }
}

# EKS Cluster
resource "aws_eks_cluster" "main" {
  name            = "telecom-ai-eks"
  role_arn        = aws_iam_role.eks_cluster.arn
  version         = var.kubernetes_version
  
  vpc_config {
    subnet_ids              = concat(aws_subnet.public[*].id, aws_subnet.private[*].id)
    endpoint_private_access = true
    endpoint_public_access  = true
  }
  
  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
  ]
  
  tags = {
    Name = "telecom-ai-eks"
  }
}

# EKS Node Group
resource "aws_eks_node_group" "main" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "telecom-ai-nodes"
  node_role_arn   = aws_iam_role.eks_node.arn
  subnet_ids      = aws_subnet.private[*].id
  version         = var.kubernetes_version
  
  scaling_config {
    desired_size = 3
    max_size     = 10
    min_size     = 3
  }
  
  instance_types = [var.node_instance_type]
  
  depends_on = [
    aws_iam_role_policy_attachment.eks_worker_node_policy,
    aws_iam_role_policy_attachment.eks_cni_policy,
  ]
  
  tags = {
    Name = "telecom-ai-node-group"
  }
}

# RDS PostgreSQL
resource "aws_db_instance" "main" {
  identifier            = "telecom-ai-db"
  engine                = "postgres"
  engine_version        = "15.3"
  instance_class        = var.db_instance_class
  allocated_storage     = var.db_allocated_storage
  storage_encrypted     = true
  
  db_name  = "telecomaidb"
  username = var.db_username
  password = random_password.db_password.result
  
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  
  skip_final_snapshot       = false
  final_snapshot_identifier = "telecom-ai-db-final-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  backup_retention_period = 30
  backup_window           = "03:00-04:00"
  maintenance_window      = "sun:04:00-sun:05:00"
  
  tags = {
    Name = "telecom-ai-postgres"
  }
}

# MSK Kafka Cluster
resource "aws_msk_cluster" "main" {
  cluster_name           = "telecom-ai-kafka"
  kafka_version          = "3.6.0"
  number_of_broker_nodes = 3
  broker_node_group_info {
    instance_type   = "kafka.m5.large"
    ebs_volume_size = 100
    security_groups = [aws_security_group.kafka.id]
    subnet_ids      = aws_subnet.private[*].id
  }
  
  encryption_info {
    encryption_in_transit {
      client_broker = "TLS"
    }
    encryption_at_rest {
      enabled          = true
      kms_key_arn      = aws_kms_key.kafka.arn
    }
  }
  
  tags = {
    Name = "telecom-ai-kafka"
  }
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "main" {
  cluster_id           = "telecom-ai-redis"
  engine               = "redis"
  engine_version       = "7.0"
  node_type            = "cache.t3.medium"
  num_cache_nodes      = 3
  parameter_group_name = "default.redis7"
  port                 = 6379
  
  security_group_ids      = [aws_security_group.redis.id]
  subnet_group_name       = aws_elasticache_subnet_group.main.name
  automatic_failover_enabled = true
  
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  
  tags = {
    Name = "telecom-ai-redis"
  }
}

# Data sources
data "aws_availability_zones" "available" {
  state = "available"
}

# Random password for RDS
resource "random_password" "db_password" {
  length  = 16
  special = true
}

# Outputs
output "eks_cluster_endpoint" {
  value       = aws_eks_cluster.main.endpoint
  description = "EKS cluster endpoint"
}

output "rds_endpoint" {
  value       = aws_db_instance.main.endpoint
  description = "RDS PostgreSQL endpoint"
  sensitive   = true
}

output "kafka_bootstrap_servers" {
  value       = aws_msk_cluster.main.bootstrap_brokers
  description = "Kafka bootstrap servers"
}

output "redis_endpoint" {
  value       = aws_elasticache_cluster.main.cache_nodes[0].address
  description = "Redis endpoint"
}
