"""
CLI for vLLM Batch Server management.

Usage:
    vllm-batch worker status
    vllm-batch worker restart
    vllm-batch worker clear-gpu
    vllm-batch worker logs --tail 100
    vllm-batch worker kill
"""

import click
import requests
import subprocess
import sys
from pathlib import Path
from typing import Optional


def get_api_url() -> str:
    """Get API URL from environment or default."""
    import os
    host = os.getenv('BATCH_API_HOST', 'localhost')
    port = os.getenv('BATCH_API_PORT', '4080')
    return f"http://{host}:{port}"


def print_success(message: str):
    """Print success message in green."""
    click.echo(click.style(f"✓ {message}", fg='green'))


def print_error(message: str):
    """Print error message in red."""
    click.echo(click.style(f"✗ {message}", fg='red'), err=True)


def print_warning(message: str):
    """Print warning message in yellow."""
    click.echo(click.style(f"⚠ {message}", fg='yellow'))


def print_info(message: str):
    """Print info message."""
    click.echo(f"ℹ {message}")


@click.group()
def cli():
    """vLLM Batch Server CLI - Manage your local vLLM batch processing server."""
    pass


@cli.group()
def worker():
    """Worker management commands."""
    pass


@worker.command()
def status():
    """Show worker status and system health."""
    try:
        api_url = get_api_url()
        
        # Get system status
        response = requests.get(f"{api_url}/admin/system/status", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        # Print header
        click.echo("\n" + "="*60)
        click.echo("  vLLM Batch Server - System Status")
        click.echo("="*60 + "\n")
        
        # Worker status
        worker_data = data.get('processes', {}).get('worker', {})
        if worker_data.get('running'):
            print_success(f"Worker: RUNNING (PIDs: {', '.join(worker_data.get('pids', []))})")
        else:
            print_error(f"Worker: OFFLINE")
            if 'error' in worker_data:
                print_error(f"  Error: {worker_data['error']}")
        
        # API server status
        api_data = data.get('processes', {}).get('api_server', {})
        if api_data.get('running'):
            print_success(f"API Server: RUNNING (PIDs: {', '.join(api_data.get('pids', []))})")
        else:
            print_error(f"API Server: OFFLINE")
        
        # GPU status
        gpu_data = data.get('gpu', {})
        if 'error' in gpu_data:
            print_warning(f"GPU: {gpu_data['error']}")
        else:
            mem_used = gpu_data.get('memory_used_mb', 0)
            mem_total = gpu_data.get('memory_total_mb', 0)
            mem_pct = gpu_data.get('memory_percent', 0)
            temp = gpu_data.get('temperature_c', 0)
            util = gpu_data.get('utilization_percent', 0)
            
            click.echo(f"\n📊 GPU Status:")
            click.echo(f"  Memory: {mem_used:,} MB / {mem_total:,} MB ({mem_pct:.1f}%)")
            click.echo(f"  Temperature: {temp}°C")
            click.echo(f"  Utilization: {util}%")
        
        # Get worker heartbeat
        response = requests.get(f"{api_url}/health", timeout=5)
        response.raise_for_status()
        health_data = response.json()
        
        worker_info = health_data.get('worker', {})
        if worker_info.get('status') == 'healthy':
            click.echo(f"\n💚 Worker Heartbeat:")
            click.echo(f"  Status: HEALTHY")
            click.echo(f"  Current Model: {worker_info.get('loaded_model', 'None')}")
            click.echo(f"  Last Seen: {worker_info.get('last_seen', 'Unknown')}")
        elif worker_info.get('status') == 'dead':
            print_error(f"\n💔 Worker Heartbeat: DEAD (last seen {worker_info.get('age_seconds', 0)}s ago)")
        else:
            print_warning(f"\n❓ Worker Heartbeat: UNKNOWN")
        
        # Queue status
        queue_data = health_data.get('queue', {})
        click.echo(f"\n📋 Queue Status:")
        click.echo(f"  Active Jobs: {queue_data.get('active_jobs', 0)}")
        click.echo(f"  Queue Available: {queue_data.get('queue_available', 0)}/{queue_data.get('max_queue_depth', 0)}")
        
        click.echo("\n" + "="*60 + "\n")
        
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to API server at {get_api_url()}")
        print_info("Is the server running? Try: docker-compose up -d")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error getting status: {e}")
        sys.exit(1)


@worker.command()
def restart():
    """Restart the worker process (graceful)."""
    try:
        api_url = get_api_url()
        
        print_info("Restarting worker...")
        response = requests.post(f"{api_url}/admin/system/restart-worker", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print_success("Worker restarted successfully!")
        click.echo(f"  Old PIDs: {', '.join(data.get('old_pids', []))}")
        click.echo(f"  New PID: {data.get('new_pid', 'Unknown')}")
        print_warning(data.get('note', 'Wait 10-15 seconds for worker to initialize'))
        
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to API server at {get_api_url()}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error restarting worker: {e}")
        sys.exit(1)


@worker.command()
def clear_gpu():
    """Clear GPU memory by force-killing and restarting worker."""
    try:
        api_url = get_api_url()
        
        print_warning("Force-killing worker to clear GPU memory...")
        response = requests.post(f"{api_url}/admin/system/clear-gpu-memory", timeout=30)
        response.raise_for_status()
        data = response.json()
        
        print_success("GPU memory cleared and worker restarted!")
        click.echo(f"  Old PIDs: {', '.join(data.get('old_pids', []))}")
        click.echo(f"  New PID: {data.get('new_pid', 'Unknown')}")
        print_warning(data.get('note', 'Wait 10-15 seconds for worker to initialize'))
        
    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to API server at {get_api_url()}")
        sys.exit(1)
    except Exception as e:
        print_error(f"Error clearing GPU memory: {e}")
        sys.exit(1)


@worker.command()
@click.option('--tail', default=100, help='Number of lines to show from end of log')
@click.option('--follow', '-f', is_flag=True, help='Follow log output (like tail -f)')
def logs(tail: int, follow: bool):
    """View worker logs."""
    try:
        # Find project root
        project_root = Path(__file__).parent.parent
        log_file = project_root / "logs" / "worker.log"
        
        if not log_file.exists():
            print_error(f"Log file not found: {log_file}")
            print_info("Worker may not have started yet")
            sys.exit(1)
        
        if follow:
            # Use tail -f
            print_info(f"Following {log_file} (Ctrl+C to stop)...")
            subprocess.run(['tail', '-f', str(log_file)])
        else:
            # Show last N lines
            with open(log_file, 'r') as f:
                lines = f.readlines()
                for line in lines[-tail:]:
                    click.echo(line.rstrip())
        
    except KeyboardInterrupt:
        click.echo("\n")
        print_info("Stopped following logs")
    except Exception as e:
        print_error(f"Error reading logs: {e}")
        sys.exit(1)


@worker.command()
@click.confirmation_option(prompt='Are you sure you want to kill the worker?')
def kill():
    """Force-kill the worker process (emergency use only)."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "python -m core.batch_app.worker"],
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            print_warning("No worker process found")
            sys.exit(0)
        
        pids = result.stdout.strip().split('\n')
        for pid in pids:
            if pid:
                print_info(f"Killing worker process {pid}...")
                subprocess.run(['kill', '-9', pid])
        
        print_success("Worker killed")
        print_warning("You may need to restart it manually or use 'vllm-batch worker restart'")
        
    except Exception as e:
        print_error(f"Error killing worker: {e}")
        sys.exit(1)


if __name__ == '__main__':
    cli()

