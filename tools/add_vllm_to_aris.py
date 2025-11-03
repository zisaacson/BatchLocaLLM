#!/usr/bin/env python3
"""Add vLLM Batch API service to Aris docker-compose.yml"""

import sys
import os

DOCKER_COMPOSE_PATH = os.getenv("ARIS_DOCKER_COMPOSE_PATH", "./docker-compose.yml")

VLLM_SERVICE = """
  # vLLM Batch API - OpenAI Compatible Batch Processing
  vllm-batch-api:
    build:
      context: ../vllm-batch-server
      dockerfile: Dockerfile.batch-api
    image: vllm-batch-api:latest
    container_name: aristotle-vllm-batch-api
    ports:
      - "4080:4080"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    environment:
      - PORT=4080
      - LOG_LEVEL=INFO
      - MAX_REQUESTS_PER_JOB=50000
      - MAX_QUEUE_DEPTH=10
      - MAX_TOTAL_QUEUED_REQUESTS=100000
    volumes:
      - vllm-batch-data:/app/data
      - ../vllm-batch-server/benchmarks:/app/benchmarks:ro
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:4080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 30s
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
"""

def main():
    # Read the file
    with open(DOCKER_COMPOSE_PATH, 'r') as f:
        lines = f.readlines()
    
    # Find where to insert the service (after prefect service)
    service_insert_idx = None
    volumes_insert_idx = None
    
    for i, line in enumerate(lines):
        # Find the end of prefect service (look for next service or volumes section)
        if 'prefect:' in line:
            # Find the next service or volumes section
            for j in range(i + 1, len(lines)):
                if lines[j].strip().startswith('# ===') or lines[j].strip() == 'volumes:':
                    service_insert_idx = j
                    break
        
        # Find volumes section
        if line.strip() == 'volumes:':
            volumes_insert_idx = i + 1
    
    if service_insert_idx is None:
        print("ERROR: Could not find where to insert service")
        sys.exit(1)
    
    if volumes_insert_idx is None:
        print("ERROR: Could not find volumes section")
        sys.exit(1)
    
    # Insert the service
    lines.insert(service_insert_idx, VLLM_SERVICE + '\n')
    
    # Insert the volume (after volumes: line)
    lines.insert(volumes_insert_idx, '  vllm-batch-data:\n')
    
    # Write back
    with open(DOCKER_COMPOSE_PATH, 'w') as f:
        f.writelines(lines)
    
    print("✅ Successfully added vLLM Batch API service to Aris docker-compose.yml")
    print(f"   Service inserted at line {service_insert_idx}")
    print(f"   Volume inserted at line {volumes_insert_idx}")

if __name__ == '__main__':
    main()

