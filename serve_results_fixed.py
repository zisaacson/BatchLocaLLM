#!/usr/bin/env python3
"""
Fixed results viewer server with ACCURATE GPU status
- Only shows ACTUALLY running processes (checks PIDs)
- Real-time GPU stats
- No stale log file data
"""

import json
import os
import subprocess
import psutil
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

class ResultsHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()
    
    def do_GET(self):
        parsed_path = urlparse(self.path)

        # API endpoint to get results
        if parsed_path.path == '/api/results':
            query = parse_qs(parsed_path.query)
            model = query.get('model', ['llama32_3b_5k_results.jsonl'])[0]

            try:
                # Load results
                results = []
                with open(model, 'r') as f:
                    for line in f:
                        if line.strip():
                            results.append(json.loads(line))

                # Load original batch file to get candidate info
                batch_file = 'batch_5k.jsonl'
                batch_requests = {}
                
                if Path(batch_file).exists():
                    with open(batch_file, 'r') as f:
                        for line in f:
                            if line.strip():
                                req = json.loads(line)
                                batch_requests[req['custom_id']] = req
                
                # Join results with original requests
                enriched_results = []
                for result in results:
                    custom_id = result.get('custom_id')
                    enriched = result.copy()
                    
                    # Add original request body if available
                    if custom_id and custom_id in batch_requests:
                        enriched['body'] = batch_requests[custom_id].get('body', {})
                    
                    enriched_results.append(enriched)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(enriched_results).encode())
            except FileNotFoundError:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'File not found: {model}'}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # API endpoint to get GPU status (FIXED - only shows REAL running jobs)
        elif parsed_path.path == '/api/gpu':
            try:
                # Get GPU stats
                gpu_result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu',
                     '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=5
                )
                
                if gpu_result.returncode == 0:
                    parts = gpu_result.stdout.strip().split(', ')
                    gpu_data = {
                        'name': parts[0],
                        'utilization': int(parts[1]),
                        'memory_used': int(parts[2]),
                        'memory_total': int(parts[3]),
                        'temperature': int(parts[4])
                    }
                else:
                    gpu_data = {'error': 'nvidia-smi failed'}

                # Find ACTUALLY running Python processes (not stale logs!)
                running_jobs = []
                
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                    try:
                        if proc.info['name'] == 'python3' or proc.info['name'] == 'python':
                            cmdline = ' '.join(proc.info['cmdline'] or [])
                            
                            # Skip this server
                            if 'serve_results' in cmdline:
                                continue
                            
                            # Check if it's a vLLM or batch process
                            if any(keyword in cmdline for keyword in ['vllm', 'test_', 'batch', 'benchmark']):
                                running_jobs.append({
                                    'pid': proc.info['pid'],
                                    'command': cmdline[:100],  # Truncate long commands
                                    'runtime_seconds': int(psutil.time.time() - proc.info['create_time'])
                                })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'gpu': gpu_data,
                    'running_jobs': running_jobs,
                    'job_count': len(running_jobs)
                }).encode())
                
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # API endpoint to get metadata
        elif parsed_path.path == '/api/metadata':
            try:
                metadata_file = Path('results/metadata.json')
                if metadata_file.exists():
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(metadata).encode())
                else:
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': 'Metadata file not found'}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # Serve static files
        else:
            return SimpleHTTPRequestHandler.do_GET(self)

def main():
    port = 8001
    server = HTTPServer(('0.0.0.0', port), ResultsHandler)
    
    print(f"🚀 Starting FIXED results viewer server on http://localhost:{port}")
    print(f"📂 Serving from: {os.getcwd()}")
    print()
    print(f"✨ Open in browser: http://localhost:{port}/compare_models.html")
    print()
    print("✅ GPU status now shows ONLY actually running processes!")
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

if __name__ == '__main__':
    main()

