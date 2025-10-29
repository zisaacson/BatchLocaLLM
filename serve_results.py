#!/usr/bin/env python3
"""
Simple HTTP server to view benchmark results
"""

import json
import os
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

        # API endpoint to get original candidate data
        elif parsed_path.path == '/api/candidates':
            query = parse_qs(parsed_path.query)
            dataset = query.get('dataset', ['batch_5k.jsonl'])[0]

            try:
                candidates = []
                with open(dataset, 'r') as f:
                    for line in f:
                        if line.strip():
                            candidates.append(json.loads(line))

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(candidates).encode())
            except FileNotFoundError:
                self.send_response(404)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': f'File not found: {dataset}'}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # API endpoint to discover available datasets and results
        elif parsed_path.path == '/api/discover':
            try:
                import glob

                # Find all batch input files (exclude result files)
                all_batch_files = glob.glob('batch*.jsonl')
                batch_files = [f for f in all_batch_files if not f.endswith('_results.jsonl')]

                # Find all result files - EXCLUDE batch_5k_optimized_results.jsonl
                result_files = glob.glob('*_results.jsonl') + glob.glob('benchmarks/raw/*.jsonl')
                result_files = [f for f in result_files if 'batch_5k_optimized_results.jsonl' not in f]

                # Count lines in each file
                datasets = {}
                for batch_file in sorted(batch_files):
                    try:
                        with open(batch_file, 'r') as f:
                            count = sum(1 for line in f if line.strip())
                        datasets[batch_file] = {'count': count, 'results': []}
                    except:
                        pass

                # Match results to datasets by count
                for result_file in sorted(result_files):
                    try:
                        with open(result_file, 'r') as f:
                            count = sum(1 for line in f if line.strip())

                        # Find matching dataset
                        for dataset_name, dataset_info in datasets.items():
                            if dataset_info['count'] == count:
                                datasets[dataset_name]['results'].append({
                                    'file': result_file,
                                    'count': count
                                })
                    except:
                        pass

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(datasets).encode())
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
                    self.wfile.write(json.dumps({'error': 'Metadata not found. Run migrate_results.py first.'}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # API endpoint to get GPU status
        elif parsed_path.path == '/api/gpu':
            try:
                import subprocess

                # Get GPU stats
                gpu_result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu', '--format=csv,noheader,nounits'],
                    capture_output=True, text=True, timeout=5
                )

                # Get running processes
                ps_result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True, text=True, timeout=5
                )

                # Parse GPU info
                gpu_lines = gpu_result.stdout.strip().split('\n')
                gpus = []
                for line in gpu_lines:
                    if line.strip():
                        parts = [p.strip() for p in line.split(',')]
                        if len(parts) >= 6:
                            gpus.append({
                                'index': parts[0],
                                'name': parts[1],
                                'utilization': parts[2],
                                'memory_used': parts[3],
                                'memory_total': parts[4],
                                'temperature': parts[5]
                            })

                # Find vLLM/test processes
                processes = []
                for line in ps_result.stdout.split('\n'):
                    if 'python' in line.lower() and ('test_' in line or 'vllm' in line or 'EngineCore' in line):
                        processes.append(line)

                # Try to get latest log progress from all offline batch logs
                log_files = [
                    'qwen3_4b_5k_offline.log',
                    'gemma3_4b_5k_offline.log',
                    'llama32_3b_5k_offline.log',
                    'llama32_1b_5k_offline.log',
                    # Legacy logs (may be stale)
                    'qwen3_4b_5k_test.log',
                    'olmo2_7b_100_test.log'
                ]
                progress = {}
                for log_file in log_files:
                    try:
                        tail_result = subprocess.run(
                            ['tail', '-3', log_file],
                            capture_output=True, text=True, timeout=2
                        )
                        # Support both old format (Processed prompts) and new format (Running batch)
                        if 'Processed prompts' in tail_result.stdout or 'Running batch' in tail_result.stdout:
                            progress[log_file] = tail_result.stdout.strip().split('\n')[-1]
                    except:
                        pass

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'gpus': gpus,
                    'processes': processes,
                    'progress': progress
                }).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())
        else:
            # Serve static files
            super().do_GET()

if __name__ == '__main__':
    PORT = 8001
    print(f"🚀 Starting results viewer server on http://localhost:{PORT}")
    print(f"📂 Serving from: {os.getcwd()}")
    print(f"\n✨ Open in browser: http://localhost:{PORT}/view_results.html\n")

    server = HTTPServer(('localhost', PORT), ResultsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")

