# Systemd Service Files

Auto-start vLLM Batch Server on boot with proper dependency ordering.

## Installation

### 1. Copy service file to systemd directory

```bash
sudo cp systemd/vllm-batch-server.service /etc/systemd/system/
```

### 2. Update paths in service file (if needed)

Edit `/etc/systemd/system/vllm-batch-server.service` and update:
- `User=` and `Group=` to your username
- `WorkingDirectory=` to your project path
- `Environment="PATH=..."` to include your venv path
- `EnvironmentFile=` to your .env file path

### 3. Reload systemd

```bash
sudo systemctl daemon-reload
```

### 4. Enable auto-start on boot

```bash
sudo systemctl enable vllm-batch-server.service
```

### 5. Start the service

```bash
sudo systemctl start vllm-batch-server.service
```

## Usage

### Check status

```bash
sudo systemctl status vllm-batch-server.service
```

### View logs

```bash
# Real-time logs
sudo journalctl -u vllm-batch-server.service -f

# Last 100 lines
sudo journalctl -u vllm-batch-server.service -n 100

# Logs since boot
sudo journalctl -u vllm-batch-server.service -b
```

### Restart service

```bash
sudo systemctl restart vllm-batch-server.service
```

### Stop service

```bash
sudo systemctl stop vllm-batch-server.service
```

### Disable auto-start

```bash
sudo systemctl disable vllm-batch-server.service
```

## Troubleshooting

### Service fails to start

1. Check logs:
   ```bash
   sudo journalctl -u vllm-batch-server.service -n 50
   ```

2. Check if PostgreSQL is running:
   ```bash
   docker ps | grep postgres
   ```

3. Check GPU memory:
   ```bash
   nvidia-smi
   ```

4. Manually run startup scripts:
   ```bash
   ./scripts/wait_for_postgres.sh
   ./scripts/check_gpu_memory.sh
   ./scripts/restart_server.sh
   ```

### Service starts but crashes

Check application logs:
```bash
tail -100 logs/api_server.log
tail -100 logs/worker.log
```

### GPU memory issues

The service includes a pre-start GPU memory check. If it fails:

1. Check what's using GPU:
   ```bash
   nvidia-smi
   ```

2. Clear GPU memory manually:
   ```bash
   ./scripts/check_gpu_memory.sh
   ```

3. Restart service:
   ```bash
   sudo systemctl restart vllm-batch-server.service
   ```

## Dependencies

The service depends on:
- `docker.service` - Docker must be running
- `network.target` - Network must be available

The service waits for:
- PostgreSQL to be ready (via `wait_for_postgres.sh`)
- GPU memory to be available (via `check_gpu_memory.sh`)

## Boot Sequence

1. System boots
2. Docker starts
3. Docker Compose starts PostgreSQL container
4. Systemd waits 5 seconds
5. `wait_for_postgres.sh` checks PostgreSQL health
6. `check_gpu_memory.sh` verifies GPU memory
7. `restart_server.sh` starts API server and worker
8. Service is running

## Notes

- The service uses `Type=forking` because `restart_server.sh` starts background processes
- Restart policy: Restart on failure, max 5 attempts in 200 seconds
- Logs go to systemd journal (use `journalctl` to view)
- Service runs as your user (not root) to access GPU and Docker

