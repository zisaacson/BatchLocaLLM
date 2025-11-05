"""
Watchdog process for automatic worker recovery.

Monitors worker health and automatically restarts on failure.

Features:
- Heartbeat monitoring (restart if heartbeat age > 60 seconds)
- Stuck job detection (cancel + restart if no progress for 30 minutes)
- Crash recovery (auto-restart on worker crash)
- Systemd integration (for production deployments)

Usage:
    python -m core.batch_app.watchdog
"""

import os
import time
import logging
import subprocess
import signal
from datetime import datetime, timezone, timedelta
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.batch_app.database import WorkerHeartbeat, BatchJob

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/watchdog.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class WorkerWatchdog:
    """
    Monitors worker health and automatically recovers from failures.
    """
    
    def __init__(self):
        self.api_url = f"http://localhost:{settings.BATCH_API_PORT}"
        self.check_interval = 30  # Check every 30 seconds
        self.heartbeat_timeout = 60  # Restart if heartbeat age > 60 seconds
        self.stuck_job_timeout = 1800  # 30 minutes
        self.running = True
        
        # Database connection
        engine = create_engine(settings.DATABASE_URL)
        self.SessionLocal = sessionmaker(bind=engine)
    
    def check_worker_heartbeat(self) -> bool:
        """
        Check if worker heartbeat is healthy.
        
        Returns:
            True if healthy, False if dead
        """
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            response.raise_for_status()
            data = response.json()
            
            worker = data.get('worker', {})
            status = worker.get('status')
            
            if status == 'healthy':
                return True
            elif status == 'dead':
                age_seconds = worker.get('age_seconds', 0)
                logger.warning(f"Worker heartbeat dead (age: {age_seconds}s)")
                return False
            else:
                logger.warning(f"Worker heartbeat unknown status: {status}")
                return False
                
        except Exception as e:
            logger.error(f"Error checking worker heartbeat: {e}")
            return False
    
    def check_stuck_jobs(self) -> bool:
        """
        Check for stuck jobs (no progress for 30 minutes).
        
        Returns:
            True if stuck job found, False otherwise
        """
        try:
            db = self.SessionLocal()
            
            # Find processing jobs with no recent progress
            stuck_jobs = db.query(BatchJob).filter(
                BatchJob.status == 'processing',
                BatchJob.last_progress_update < datetime.now(timezone.utc) - timedelta(seconds=self.stuck_job_timeout)
            ).all()
            
            if stuck_jobs:
                for job in stuck_jobs:
                    logger.warning(f"Stuck job detected: {job.batch_id} (no progress for {self.stuck_job_timeout}s)")
                    
                    # Cancel stuck job
                    job.status = 'cancelled'
                    job.error_message = 'Job stuck - no progress for 30 minutes'
                    db.commit()
                    
                    logger.info(f"Cancelled stuck job: {job.batch_id}")
                
                db.close()
                return True
            
            db.close()
            return False
            
        except Exception as e:
            logger.error(f"Error checking stuck jobs: {e}")
            return False
    
    def restart_worker(self):
        """Restart the worker process."""
        try:
            logger.info("Restarting worker...")
            
            # Call API endpoint to restart worker
            response = requests.post(f"{self.api_url}/admin/system/restart-worker", timeout=30)
            response.raise_for_status()
            data = response.json()
            
            logger.info(f"Worker restarted: {data.get('message')}")
            logger.info(f"Old PIDs: {data.get('old_pids')}, New PID: {data.get('new_pid')}")
            
            # Wait for worker to initialize
            time.sleep(15)
            
        except Exception as e:
            logger.error(f"Error restarting worker: {e}")
            
            # Fallback: Try to restart manually
            try:
                logger.info("Attempting manual worker restart...")
                
                # Kill old worker
                result = subprocess.run(
                    ["pgrep", "-f", "python -m core.batch_app.worker"],
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    pids = result.stdout.strip().split('\n')
                    for pid in pids:
                        if pid:
                            subprocess.run(['kill', '-9', pid])
                            logger.info(f"Killed worker process {pid}")
                
                # Start new worker
                subprocess.Popen(
                    ["python", "-m", "core.batch_app.worker"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True
                )
                
                logger.info("Worker restarted manually")
                time.sleep(15)
                
            except Exception as e2:
                logger.error(f"Manual restart failed: {e2}")
    
    def run(self):
        """Main watchdog loop."""
        logger.info("Worker watchdog started")
        logger.info(f"Check interval: {self.check_interval}s")
        logger.info(f"Heartbeat timeout: {self.heartbeat_timeout}s")
        logger.info(f"Stuck job timeout: {self.stuck_job_timeout}s")
        
        while self.running:
            try:
                # Check worker heartbeat
                if not self.check_worker_heartbeat():
                    logger.warning("Worker heartbeat unhealthy - restarting worker")
                    self.restart_worker()
                
                # Check for stuck jobs
                if self.check_stuck_jobs():
                    logger.warning("Stuck jobs detected - restarting worker")
                    self.restart_worker()
                
                # Sleep until next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Watchdog stopped by user")
                self.running = False
            except Exception as e:
                logger.error(f"Error in watchdog loop: {e}")
                time.sleep(self.check_interval)
    
    def stop(self):
        """Stop the watchdog."""
        self.running = False


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    logger.info("Received shutdown signal")
    sys.exit(0)


if __name__ == "__main__":
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Create logs directory
    Path("logs").mkdir(exist_ok=True)
    
    # Start watchdog
    watchdog = WorkerWatchdog()
    watchdog.run()

