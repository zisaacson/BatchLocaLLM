# Auto-Start on Boot Setup

This guide shows how to configure the vLLM Batch Server to automatically start when your computer boots.

---

## 🚀 **Quick Install**

```bash
# Install and enable auto-start (requires sudo)
sudo ./scripts/install-systemd-services.sh
```

**That's it!** The services will now start automatically on boot.

---

## 📋 **What Gets Installed**

Two systemd services:

1. **vllm-api-server.service** - Batch API server (port 4080)
2. **vllm-watchdog.service** - Auto-recovery watchdog (monitors worker)

Both services:
- ✅ Start automatically on boot
- ✅ Restart automatically on crash
- ✅ Run as your user (not root)
- ✅ Log to `logs/` directory

---

## 🔧 **Manual Installation**

If you prefer to install manually:

```bash
# Copy service files
sudo cp deployment/systemd/vllm-api-server.service /etc/systemd/system/
sudo cp deployment/systemd/vllm-watchdog.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable vllm-api-server
sudo systemctl enable vllm-watchdog

# Start services now
sudo systemctl start vllm-api-server
sudo systemctl start vllm-watchdog
```

---

## 📊 **Check Status**

```bash
# Check if services are running
sudo systemctl status vllm-api-server
sudo systemctl status vllm-watchdog

# View logs
sudo journalctl -u vllm-api-server -f
sudo journalctl -u vllm-watchdog -f

# Or use local log files
tail -f logs/api_server.log
tail -f logs/watchdog.log
tail -f logs/worker.log
```

---

## 🛑 **Stop/Disable Auto-Start**

```bash
# Stop services
sudo systemctl stop vllm-api-server
sudo systemctl stop vllm-watchdog

# Disable auto-start on boot
sudo systemctl disable vllm-api-server
sudo systemctl disable vllm-watchdog
```

---

## 🔄 **Restart Services**

```bash
# Restart API server
sudo systemctl restart vllm-api-server

# Restart watchdog (will also restart worker)
sudo systemctl restart vllm-watchdog

# Restart both
sudo systemctl restart vllm-api-server vllm-watchdog
```

---

## 🐛 **Troubleshooting**

### **Services won't start**

1. Check logs:
   ```bash
   sudo journalctl -u vllm-api-server -n 50
   sudo journalctl -u vllm-watchdog -n 50
   ```

2. Check if ports are in use:
   ```bash
   sudo netstat -tlnp | grep -E "4080|4081"
   ```

3. Check database is running:
   ```bash
   sudo systemctl status postgresql
   ```

### **Services start but crash immediately**

1. Check Python environment:
   ```bash
   /home/zack/Documents/augment-projects/Local/vllm-batch-server/venv/bin/python --version
   ```

2. Check dependencies:
   ```bash
   source venv/bin/activate
   pip list | grep -E "vllm|fastapi|sqlalchemy"
   ```

3. Test manually:
   ```bash
   python -m core.batch_app.api_server
   python -m core.batch_app.watchdog
   ```

---

## 📝 **Service Files**

Located in `deployment/systemd/`:

- `vllm-api-server.service` - API server configuration
- `vllm-watchdog.service` - Watchdog configuration

Edit these files to customize:
- User/group
- Working directory
- Environment variables
- Restart policy
- Logging

After editing, reload systemd:
```bash
sudo systemctl daemon-reload
sudo systemctl restart vllm-api-server vllm-watchdog
```

---

## ✅ **Verification**

After installation, verify everything works:

```bash
# 1. Check services are enabled
systemctl is-enabled vllm-api-server
systemctl is-enabled vllm-watchdog

# 2. Check services are running
systemctl is-active vllm-api-server
systemctl is-active vllm-watchdog

# 3. Test API endpoint
curl http://localhost:4080/health

# 4. Reboot and verify auto-start
sudo reboot
# After reboot:
curl http://localhost:4080/health
```

---

## 🎯 **What Happens on Boot**

1. **System boots**
2. **PostgreSQL starts** (dependency)
3. **API Server starts** (port 4080)
4. **Watchdog starts** (monitors worker)
5. **Watchdog auto-starts Worker** (vLLM GPU process)
6. **System ready** ✅

Total boot time: ~30-60 seconds (depending on model loading)

---

**Your vLLM Batch Server will now start automatically every time you boot your computer!** 🎉

