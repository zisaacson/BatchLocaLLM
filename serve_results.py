#!/usr/bin/env python3
"""
Simple HTTP server to view benchmark results
"""

import json
import os
import glob
import requests
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path
from datetime import datetime

class ResultsHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

    def send_json(self, data):
        """Helper to send JSON response."""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def query_prometheus(self, query):
        """Query Prometheus for metrics."""
        try:
            prom_url = "http://localhost:4022/api/v1/query"
            resp = requests.get(prom_url, params={"query": query}, timeout=2)
            data = resp.json()
            if data.get("status") == "success" and data.get("data", {}).get("result"):
                return float(data["data"]["result"][0]["value"][1])
            return None
        except Exception as e:
            print(f"Prometheus query error: {e}")
            return None

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)

        # Delegate to do_GET which handles both GET and POST for /api/gold-star
        if parsed_path.path == '/api/gold-star':
            self.do_GET()
        else:
            self.send_response(404)
            self.end_headers()

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
                import re

                # Find all batch input files (exclude result files)
                all_batch_files = glob.glob('batch*.jsonl')
                batch_files = [f for f in all_batch_files if not f.endswith('_results.jsonl')]

                # Find all result files - EXCLUDE batch_5k_optimized_results.jsonl
                result_files = glob.glob('*_results.jsonl') + glob.glob('benchmarks/raw/*.jsonl')
                result_files = [f for f in result_files if 'batch_5k_optimized_results.jsonl' not in f]

                # Group batch files by base name (e.g., batch_5k, batch_100, batch_50k)
                # batch_5k.jsonl, batch_5k_gemma3_4b.jsonl, batch_5k_llama32_1b.jsonl -> all map to "batch_5k"
                base_datasets = {}

                for batch_file in sorted(batch_files):
                    # Extract base name: batch_5k_gemma3_4b.jsonl -> batch_5k
                    # Pattern: batch_XXX or batch_XXXk
                    match = re.match(r'(batch_\d+k?)(?:_.*)?\.jsonl', batch_file)
                    if match:
                        base_name = match.group(1) + '.jsonl'

                        # Count lines in this file
                        try:
                            with open(batch_file, 'r') as f:
                                count = sum(1 for line in f if line.strip())

                            # Use the base name as the dataset key
                            if base_name not in base_datasets:
                                base_datasets[base_name] = {'count': count, 'results': []}
                        except:
                            pass

                # Match results to datasets by count
                for result_file in sorted(result_files):
                    try:
                        with open(result_file, 'r') as f:
                            count = sum(1 for line in f if line.strip())

                        # Extract model name from result file
                        # vllm-native-gemma3-4b-5000-2025-10-28.jsonl -> gemma3-4b
                        model_name = result_file
                        if 'benchmarks/raw/' in result_file:
                            # Extract from benchmark filename
                            parts = result_file.split('/')[-1].replace('.jsonl', '').split('-')
                            if len(parts) >= 3:
                                model_name = '-'.join(parts[2:-2])  # Skip vllm-native and date

                        # Find matching dataset by count
                        for dataset_name, dataset_info in base_datasets.items():
                            if dataset_info['count'] == count:
                                base_datasets[dataset_name]['results'].append({
                                    'file': result_file,
                                    'model': model_name,
                                    'count': count
                                })
                                break
                    except:
                        pass

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(base_datasets).encode())
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

        # API endpoint to get current benchmark status
        elif parsed_path.path == '/api/benchmark-status':
            try:
                status_file = Path('benchmark_status.json')
                if status_file.exists():
                    with open(status_file, 'r') as f:
                        status = json.load(f)
                    self.send_json(status)
                else:
                    self.send_json({'status': 'idle'})
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # NEW: API endpoint to get benchmark results
        elif parsed_path.path == '/api/benchmarks':
            try:
                # Find all benchmark JSON files
                benchmark_files = glob.glob('benchmark_results/*.json')

                benchmarks = []
                for bf in benchmark_files:
                    try:
                        with open(bf, 'r') as f:
                            data = json.load(f)
                            mtime = os.path.getmtime(bf)
                            benchmarks.append({
                                'file': bf,
                                'timestamp': mtime,
                                'timestamp_human': datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                'data': data
                            })
                    except Exception:
                        pass

                # Sort by timestamp (newest first)
                benchmarks.sort(key=lambda x: x['timestamp'], reverse=True)

                self.send_json(benchmarks)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # NEW: API endpoint to get real-time GPU metrics (using pynvml directly)
        elif parsed_path.path == '/api/metrics/gpu':
            try:
                import pynvml
                pynvml.nvmlInit()
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                # Get GPU metrics
                temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                util = pynvml.nvmlDeviceGetUtilizationRates(handle)
                power = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W

                pynvml.nvmlShutdown()

                metrics = {
                    'temperature': temp,
                    'memory_percent': (mem_info.used / mem_info.total) * 100,
                    'memory_used_gb': mem_info.used / (1024**3),
                    'memory_total_gb': mem_info.total / (1024**3),
                    'utilization': util.gpu,
                    'power_watts': power,
                    'timestamp': datetime.now().isoformat()
                }
                self.send_json(metrics)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # NEW: API endpoint to get vLLM metrics (query vLLM server directly)
        elif parsed_path.path == '/api/metrics/vllm':
            try:
                # Query vLLM metrics endpoint
                vllm_resp = requests.get('http://localhost:4080/metrics', timeout=2)
                vllm_metrics_text = vllm_resp.text

                # Parse Prometheus format metrics
                def parse_metric(text, metric_name):
                    for line in text.split('\n'):
                        if line.startswith(metric_name) and not line.startswith('#'):
                            return float(line.split()[-1])
                    return None

                # Extract metrics
                cache_queries = parse_metric(vllm_metrics_text, 'vllm:prefix_cache_queries_total')
                cache_hits = parse_metric(vllm_metrics_text, 'vllm:prefix_cache_hits_total')
                cache_hit_rate = (cache_hits / cache_queries * 100) if cache_queries and cache_hits else None

                metrics = {
                    'active_requests': parse_metric(vllm_metrics_text, 'vllm:num_requests_running'),
                    'queued_requests': parse_metric(vllm_metrics_text, 'vllm:num_requests_waiting'),
                    'kv_cache_usage': parse_metric(vllm_metrics_text, 'vllm:kv_cache_usage_perc'),
                    'generation_tokens_total': parse_metric(vllm_metrics_text, 'vllm:generation_tokens_total'),
                    'prefix_cache_hit_rate': cache_hit_rate,
                    'prefix_cache_queries': cache_queries,
                    'prefix_cache_hits': cache_hits,
                    'timestamp': datetime.now().isoformat()
                }
                self.send_json(metrics)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # API endpoint to gold-star an example
        elif parsed_path.path == '/api/gold-star':
            if self.command == 'POST':
                try:
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    data = json.loads(post_data.decode('utf-8'))

                    # Validate required fields
                    if 'custom_id' not in data:
                        self.send_response(400)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'error': 'custom_id required'}).encode())
                        return

                    # Validate quality_score
                    quality_score = data.get('quality_score')
                    if quality_score is not None:
                        if not isinstance(quality_score, int) or quality_score < 1 or quality_score > 10:
                            self.send_response(400)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps({'error': 'quality_score must be an integer between 1 and 10'}).encode())
                            return

                    # Check for duplicates (optional - warn but allow)
                    starred_file = 'data/gold_star/starred.jsonl'
                    duplicate_found = False
                    if os.path.exists(starred_file):
                        with open(starred_file, 'r') as f:
                            for line in f:
                                if line.strip():
                                    existing = json.loads(line)
                                    if existing.get('custom_id') == data.get('custom_id'):
                                        duplicate_found = True
                                        break

                    # Add timestamp
                    data['starred_at'] = datetime.now().isoformat()

                    # Add duplicate flag if found
                    if duplicate_found:
                        data['is_duplicate'] = True

                    # Create directory if needed
                    os.makedirs('data/gold_star', exist_ok=True)

                    # Append to file
                    with open(starred_file, 'a') as f:
                        f.write(json.dumps(data) + '\n')

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'success', 'message': 'Example starred successfully'}).encode())
                except Exception as e:
                    self.send_response(500)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'error': str(e)}).encode())
            else:
                # GET - return all starred examples
                try:
                    starred = []
                    starred_file = 'data/gold_star/starred.jsonl'

                    if os.path.exists(starred_file):
                        with open(starred_file, 'r') as f:
                            for line in f:
                                if line.strip():
                                    starred.append(json.loads(line))

                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(starred).encode())
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

        # API endpoint to export gold-star dataset
        elif parsed_path.path == '/api/export-gold-star':
            try:
                query = parse_qs(parsed_path.query)
                export_format = query.get('format', ['icl'])[0]
                min_quality = int(query.get('min_quality', ['7'])[0])

                starred_file = 'data/gold_star/starred.jsonl'

                if not os.path.exists(starred_file):
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({
                        'count': 0,
                        'data': [],
                        'filename': f'gold_star_{export_format}.jsonl'
                    }).encode())
                    return

                # Load starred examples
                starred_examples = []
                with open(starred_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            example = json.loads(line)
                            quality = example.get('quality_score', 0)
                            if quality >= min_quality:
                                starred_examples.append(example)

                # Format based on export type
                if export_format == 'icl':
                    # In-Context Learning format: just the examples
                    data = starred_examples
                elif export_format == 'finetuning':
                    # Fine-tuning format: convert to messages format
                    data = []
                    for ex in starred_examples:
                        data.append({
                            'messages': [
                                {'role': 'user', 'content': ex.get('prompt', '')},
                                {'role': 'assistant', 'content': ex.get('response', '')}
                            ],
                            'metadata': {
                                'custom_id': ex.get('custom_id'),
                                'quality_score': ex.get('quality_score'),
                                'notes': ex.get('notes', '')
                            }
                        })
                else:  # raw
                    data = starred_examples

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    'count': len(data),
                    'data': data,
                    'filename': f'gold_star_{export_format}_{len(data)}_examples.jsonl',
                    'format': export_format,
                    'min_quality': min_quality
                }).encode())

            except Exception as e:
                print(f"Export error: {e}")
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        # Serve curation app
        elif parsed_path.path == '/curate' or parsed_path.path == '/curate/':
            try:
                with open('curation_app.html', 'r') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(content.encode())
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'Curation app not found')
        else:
            # Serve static files
            super().do_GET()

if __name__ == '__main__':
    PORT = 8001
    HOST = '0.0.0.0'  # Listen on all interfaces
    print(f"🚀 Starting results viewer server on http://{HOST}:{PORT}")
    print(f"📂 Serving from: {os.getcwd()}")
    print(f"\n✨ Open in browser: http://10.0.0.223:{PORT}/view_results.html\n")

    server = HTTPServer((HOST, PORT), ResultsHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped")

