"""
Static File Server for Aris Integration

Serves vLLM batch client and documentation on port 4081
Aris can fetch the client directly from: http://10.0.0.223:4081/vllm-batch-client.ts

Usage:
    python -m batch_app.static_server
"""

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from pathlib import Path

app = FastAPI(title="vLLM Batch Integration Server")

# Enable CORS so Aris can fetch files
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Base directory
BASE_DIR = Path(__file__).parent.parent
INTEGRATION_DIR = BASE_DIR / "aris-integration"

@app.get("/integration")
async def integration_page():
    """Integration page with download links for Aris"""
    return HTMLResponse("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>vLLM Batch Integration - Aris</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            min-height: 100vh;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
        }
        h1 {
            font-size: 42px;
            margin-bottom: 10px;
            background: linear-gradient(90deg, #fff, #e0e0e0);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .subtitle {
            font-size: 18px;
            color: rgba(255, 255, 255, 0.8);
            margin-bottom: 40px;
        }
        .section {
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 30px;
            margin-bottom: 30px;
        }
        h2 {
            font-size: 24px;
            margin-bottom: 20px;
            color: #fff;
        }
        .file-list {
            list-style: none;
        }
        .file-item {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 15px 20px;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            transition: all 0.3s ease;
        }
        .file-item:hover {
            background: rgba(255, 255, 255, 0.2);
            transform: translateX(5px);
        }
        .file-name {
            font-weight: 600;
            font-size: 16px;
        }
        .file-desc {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
            margin-top: 5px;
        }
        .download-btn {
            background: linear-gradient(135deg, #667eea, #764ba2);
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            transition: all 0.3s ease;
            border: 2px solid rgba(255, 255, 255, 0.2);
        }
        .download-btn:hover {
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        .code-block {
            background: rgba(0, 0, 0, 0.3);
            border-radius: 8px;
            padding: 20px;
            font-family: 'Monaco', 'Courier New', monospace;
            font-size: 14px;
            overflow-x: auto;
            margin-top: 15px;
        }
        .copy-btn {
            background: rgba(255, 255, 255, 0.2);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            margin-top: 10px;
            transition: all 0.3s ease;
        }
        .copy-btn:hover {
            background: rgba(255, 255, 255, 0.3);
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .stat-card {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 20px;
            text-align: center;
        }
        .stat-value {
            font-size: 32px;
            font-weight: 700;
            margin-bottom: 5px;
        }
        .stat-label {
            font-size: 14px;
            color: rgba(255, 255, 255, 0.7);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 vLLM Batch Integration</h1>
        <p class="subtitle">Drop-in batch processing client for Aris</p>

        <div class="section">
            <h2>📦 Available Files</h2>
            <ul class="file-list">
                <li class="file-item">
                    <div>
                        <div class="file-name">vllm-batch-client.ts</div>
                        <div class="file-desc">TypeScript client for vLLM batch processing</div>
                    </div>
                    <a href="/vllm-batch-client.ts" class="download-btn" download>Download</a>
                </li>
                <li class="file-item">
                    <div>
                        <div class="file-name">MIGRATION_GUIDE.md</div>
                        <div class="file-desc">Complete migration guide from Ollama</div>
                    </div>
                    <a href="/MIGRATION_GUIDE.md" class="download-btn" download>Download</a>
                </li>
                <li class="file-item">
                    <div>
                        <div class="file-name">QUICK_START.md</div>
                        <div class="file-desc">5-minute quick start guide</div>
                    </div>
                    <a href="/QUICK_START.md" class="download-btn" download>Download</a>
                </li>
            </ul>
        </div>

        <div class="section">
            <h2>⚡ Quick Install</h2>
            <div class="code-block" id="install-code">curl http://10.0.0.223:4081/vllm-batch-client.ts > src/lib/inference/vllm-batch-client.ts</div>
            <button class="copy-btn" onclick="copyInstall()">Copy Command</button>
        </div>

        <div class="section">
            <h2>🔧 Configuration</h2>
            <div class="code-block" id="config-code"># Add to .env.local
VLLM_BATCH_URL=http://10.0.0.223:4080
VLLM_WEBHOOK_URL=http://10.0.0.223:4000/api/ml/batch/webhook
INFERENCE_PROVIDER=vllm-batch</div>
            <button class="copy-btn" onclick="copyConfig()">Copy Config</button>
        </div>

        <div class="section">
            <h2>📊 Performance Stats</h2>
            <div class="stats">
                <div class="stat-card">
                    <div class="stat-value">$0</div>
                    <div class="stat-label">Cost per 5K candidates</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">3.47</div>
                    <div class="stat-label">Requests per second</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">24 min</div>
                    <div class="stat-label">Time for 5K candidates</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value">50K</div>
                    <div class="stat-label">Max batch size</div>
                </div>
            </div>
        </div>

        <div class="section">
            <h2>🎯 Use Cases</h2>
            <ul style="list-style: none; padding: 0;">
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    ✅ <strong>Prompt Development</strong> - Test prompts with cheap 4B models
                </li>
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    ✅ <strong>Model Comparison</strong> - Compare Gemma vs Qwen vs Llama
                </li>
                <li style="padding: 10px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                    ✅ <strong>Training Data Curation</strong> - Review and gold-star examples
                </li>
                <li style="padding: 10px 0;">
                    ✅ <strong>Development Testing</strong> - Free inference for development
                </li>
            </ul>
        </div>
    </div>

    <script>
        function copyInstall() {
            const code = document.getElementById('install-code').textContent;
            navigator.clipboard.writeText(code);
            alert('Install command copied!');
        }

        function copyConfig() {
            const code = document.getElementById('config-code').textContent;
            navigator.clipboard.writeText(code);
            alert('Config copied!');
        }
    </script>
</body>
</html>
    """)

@app.get("/vllm-batch-client.ts")
async def get_client():
    """Serve the TypeScript client"""
    file_path = INTEGRATION_DIR / "vllm-batch-client.ts"
    if not file_path.exists():
        return {"error": "File not found"}
    return FileResponse(
        file_path,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=vllm-batch-client.ts"}
    )

@app.get("/MIGRATION_GUIDE.md")
async def get_migration_guide():
    """Serve the migration guide"""
    file_path = INTEGRATION_DIR / "MIGRATION_GUIDE.md"
    if not file_path.exists():
        return {"error": "File not found"}
    return FileResponse(
        file_path,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=MIGRATION_GUIDE.md"}
    )

@app.get("/QUICK_START.md")
async def get_quick_start():
    """Serve the quick start guide"""
    file_path = INTEGRATION_DIR / "QUICK_START.md"
    if not file_path.exists():
        return {"error": "File not found"}
    return FileResponse(
        file_path,
        media_type="text/plain",
        headers={"Content-Disposition": "attachment; filename=QUICK_START.md"}
    )

@app.get("/")
async def index():
    """Documentation index for engineers and AI agents (main landing page)"""
    return HTMLResponse("""
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Aristotle System - Build Guide</title><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);min-height:100vh;padding:2rem}
.container{max-width:1400px;margin:0 auto}
.header{background:white;border-radius:1rem;padding:2rem;margin-bottom:2rem;box-shadow:0 10px 30px rgba(0,0,0,0.2)}
.header h1{font-size:2.5rem;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;margin-bottom:0.5rem}
.header p{color:#666;font-size:1.1rem;margin-bottom:0.5rem}
.status{display:inline-block;background:#10b981;color:white;padding:0.5rem 1rem;border-radius:0.5rem;font-weight:600;margin-top:1rem;font-size:0.9rem}
.flow{background:white;border-radius:1rem;padding:2rem;margin-bottom:2rem;box-shadow:0 4px 6px rgba(0,0,0,0.1)}
.flow h2{color:#667eea;margin-bottom:1.5rem;font-size:1.8rem}
.flow-diagram{background:#f8fafc;border-radius:0.5rem;padding:2rem;font-family:monospace;font-size:0.95rem;line-height:1.8;color:#334155;overflow-x:auto}
.flow-step{margin:0.5rem 0;padding:0.75rem;background:white;border-left:4px solid #667eea;border-radius:0.25rem}
.flow-arrow{color:#667eea;font-weight:bold;margin:0.25rem 0}
.category{background:white;border-radius:1rem;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 4px 6px rgba(0,0,0,0.1)}
.category h2{color:#667eea;margin-bottom:1rem;font-size:1.5rem}
.category h3{color:#475569;margin:1.5rem 0 0.75rem 0;font-size:1.2rem}
.category p{color:#64748b;line-height:1.6;margin-bottom:1rem}
.doc-list{list-style:none}
.doc-item{margin-bottom:0.75rem}
.doc-link{display:block;padding:1rem;background:linear-gradient(135deg,#f5f7fa 0%,#c3cfe2 100%);border-radius:0.5rem;text-decoration:none;color:#333;transition:all 0.3s ease;border-left:4px solid #667eea}
.doc-link:hover{transform:translateX(5px);box-shadow:0 4px 12px rgba(102,126,234,0.4)}
.doc-link.priority-1{border-left-color:#ef4444;background:linear-gradient(135deg,#fee2e2 0%,#fecaca 100%)}
.doc-title{font-weight:600;font-size:1.1rem}
.priority-badge{display:inline-block;background:#ef4444;color:white;padding:0.25rem 0.5rem;border-radius:0.25rem;font-size:0.75rem;font-weight:600;margin-left:0.5rem}
.env-vars{background:#1e293b;color:#e2e8f0;padding:1.5rem;border-radius:0.5rem;font-family:monospace;font-size:0.9rem;margin:1rem 0;overflow-x:auto}
.env-var{margin:0.5rem 0}
.env-key{color:#38bdf8}
.env-val{color:#a78bfa}
.env-comment{color:#94a3b8}
.api-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;margin-top:1rem}
.api-card{background:linear-gradient(135deg,#667eea,#764ba2);color:white;padding:1.5rem;border-radius:0.5rem;text-decoration:none;transition:all 0.3s ease;display:block}
.api-card:hover{transform:translateY(-4px);box-shadow:0 8px 16px rgba(0,0,0,0.2)}
.api-card h3{font-size:1.2rem;margin-bottom:0.5rem}
.api-card p{font-size:0.9rem;opacity:0.9}
.code-block{background:#1e293b;color:#e2e8f0;padding:1rem;border-radius:0.5rem;font-family:monospace;font-size:0.85rem;margin:1rem 0;overflow-x:auto}
</style></head><body><div class="container">

<div class="header">
<h1>🎯 Aristotle System - Build Guide</h1>
<p><strong>vLLM Batch Processing + Label Studio Curation</strong></p>
<p>Complete data flow from Aris → vLLM → Curation → Gold-Star Datasets</p>
<span class="status">✅ Documentation Server Running on Port 4081</span>
</div>

<div class="flow">
<h2>📊 How Data Flows Through the System</h2>
<div class="flow-diagram">
<div class="flow-step"><strong>1. ARIS WEB APP</strong> (Next.js on remote machine)<br>   → Sends 5K candidate conquests via HTTP</div>
<div class="flow-arrow">   ↓</div>
<div class="flow-step"><strong>2. vLLM BATCH API</strong> (Port 4080 - this machine)<br>   → OpenAI-compatible batch endpoint<br>   → Queues job in SQLite database</div>
<div class="flow-arrow">   ↓</div>
<div class="flow-step"><strong>3. BATCH WORKER</strong> (Background process)<br>   → Picks up job from queue<br>   → Processes with vLLM on RTX 4080 GPU<br>   → Saves results incrementally</div>
<div class="flow-arrow">   ↓</div>
<div class="flow-step"><strong>4. AUTO-IMPORT</strong> (Worker auto-triggers)<br>   → Sends results to Curation API<br>   → Includes LLM predictions + input data</div>
<div class="flow-arrow">   ↓</div>
<div class="flow-step"><strong>5. LABEL STUDIO</strong> (Port 4015 - PostgreSQL backend)<br>   → Stores tasks, annotations, predictions<br>   → Enterprise-grade data labeling platform</div>
<div class="flow-arrow">   ↓</div>
<div class="flow-step"><strong>6. CURATION UI</strong> (Port 8001 - Custom web app)<br>   → Beautiful gradient UI for viewing/editing<br>   → Shows candidate data + LLM responses<br>   → Mark gold-stars, export datasets</div>
<div class="flow-arrow">   ↓</div>
<div class="flow-step"><strong>7. ARISTOTLE WEB APP</strong> (Optional - simpler view)<br>   → Basic gold-star marking from Aris<br>   → Deep curation happens in port 8001</div>
<div class="flow-arrow">   ↓</div>
<div class="flow-step"><strong>8. GOLD-STAR DATASETS</strong><br>   → Export for ICL / fine-tuning<br>   → Feed into Eidos training system</div>
</div>
</div>

<div class="category">
<h2>🏗️ Architecture - The Backbone</h2>
<p><strong>We leverage two enterprise systems as our backbone:</strong></p>
<h3>1. vLLM Server (Inference Engine)</h3>
<p>• Runs on RTX 4080 GPU (this machine)<br>
• Processes 5K+ requests in batches<br>
• OpenAI-compatible API<br>
• Models: Gemma 3 4B, Qwen 2.5 3B, Llama 3.2 3B</p>
<h3>2. Label Studio (Data Backbone)</h3>
<p>• PostgreSQL database (not SQLite!)<br>
• Stores all tasks, annotations, predictions<br>
• Active learning support (LLM pre-fills)<br>
• Agreement tracking (human vs LLM)</p>
<h3>3. Custom Layers We Built</h3>
<p>• <strong>Curation API</strong> (port 8001): Schema-driven wrapper around Label Studio<br>
• <strong>Curation UI</strong>: Beautiful web interface for deep data curation<br>
• <strong>Auto-Import</strong>: Automatic pipeline from vLLM → Label Studio<br>
• <strong>Aristotle Integration</strong>: Simple gold-star marking from Aris app</p>
</div>

<div class="category">
<h2>⚙️ Environment Variables</h2>
<p><strong>For Aris App</strong> (add to <code>.env.local</code>):</p>
<div class="env-vars">
<div class="env-var"><span class="env-comment"># vLLM Batch API endpoint</span></div>
<div class="env-var"><span class="env-key">VLLM_BATCH_URL</span>=<span class="env-val">http://10.0.0.223:4080</span></div>
<div class="env-var"><span class="env-comment"># Webhook for batch completion notifications</span></div>
<div class="env-var"><span class="env-key">VLLM_WEBHOOK_URL</span>=<span class="env-val">http://10.0.0.223:4000/api/ml/batch/webhook</span></div>
<div class="env-var"><span class="env-comment"># Curation API for gold-star marking</span></div>
<div class="env-var"><span class="env-key">CURATION_API_URL</span>=<span class="env-val">http://10.0.0.223:8001</span></div>
</div>
<p><strong>For This Machine</strong> (already configured in systemd services):</p>
<div class="env-vars">
<div class="env-var"><span class="env-comment"># Batch API settings</span></div>
<div class="env-var"><span class="env-key">PORT</span>=<span class="env-val">4080</span></div>
<div class="env-var"><span class="env-key">MAX_REQUESTS_PER_JOB</span>=<span class="env-val">50000</span></div>
<div class="env-var"><span class="env-comment"># Label Studio connection</span></div>
<div class="env-var"><span class="env-key">LABEL_STUDIO_URL</span>=<span class="env-val">http://localhost:4015</span></div>
<div class="env-var"><span class="env-key">LABEL_STUDIO_API_KEY</span>=<span class="env-val">(auto-generated)</span></div>
</div>
</div>

<div class="category">
<h2>🚀 Quick Access - All Services</h2>
<div class="api-grid">
<a href="http://localhost:4080/docs" class="api-card" target="_blank">
<h3>📡 Batch API</h3>
<p>Port 4080 • Submit batch jobs</p>
</a>
<a href="http://localhost:8001" class="api-card" target="_blank">
<h3>🎨 Curation UI</h3>
<p>Port 8001 • Deep data curation</p>
</a>
<a href="http://localhost:4015" class="api-card" target="_blank">
<h3>🏷️ Label Studio</h3>
<p>Port 4015 • Data backbone</p>
</a>
<a href="http://localhost:3000" class="api-card" target="_blank">
<h3>📊 Grafana</h3>
<p>Port 3000 • Monitoring</p>
</a>
</div>
</div>

<div class="category">
<h2>🏗️ WHAT TO BUILD (Start Here!)</h2>
<ul class="doc-list">
<li class="doc-item"><a href="/BUILD_THIS.md" class="doc-link priority-1"><div class="doc-title">🎯 BUILD THIS - Step-by-Step Instructions<span class="priority-badge">START HERE</span></div></a></li>
<li class="doc-item"><a href="/AUDIT_FINAL_ANSWER.md" class="doc-link priority-1"><div class="doc-title">✅ System Audit - What Works & What's Missing<span class="priority-badge">READ THIS</span></div></a></li>
<li class="doc-item"><a href="/SELF_AUDIT_COMPLETE.md" class="doc-link priority-1"><div class="doc-title">🔍 Self-Audit - Did We Do It Right?<span class="priority-badge">VERIFIED</span></div></a></li>
</ul>
<p style="margin-top:1rem;color:#64748b"><strong>Time to complete:</strong> 4-6 hours • <strong>Difficulty:</strong> Medium • <strong>Tasks:</strong> 3</p>
</div>

<div class="category">
<h2>📚 Reference Documentation</h2>
<ul class="doc-list">
<li class="doc-item"><a href="/COMPLETE_DATA_FLOW_IMPLEMENTATION.md" class="doc-link"><div class="doc-title">📊 Complete Data Flow Architecture</div></a></li>
<li class="doc-item"><a href="/AUTO_IMPORT_COMPLETE.md" class="doc-link"><div class="doc-title">✅ Auto-Import System Guide</div></a></li>
<li class="doc-item"><a href="/README_CURATION_SYSTEM.md" class="doc-link"><div class="doc-title">📝 Curation System Documentation</div></a></li>
<li class="doc-item"><a href="/CONQUEST_TEMPLATE_GUIDE.md" class="doc-link"><div class="doc-title">📋 Conquest Schema Templates</div></a></li>
<li class="doc-item"><a href="/FIRST_PRINCIPLES_WIN.md" class="doc-link"><div class="doc-title">🎯 First Principles Design</div></a></li>
</ul>
</div>

<div class="category">
<h2>🤖 For AI Agents</h2>
<p>Point your LLM to these URLs to read build instructions:</p>
<div class="code-block">curl http://localhost:4081/BUILD_THIS.md
curl http://localhost:4081/AUDIT_FINAL_ANSWER.md
curl http://localhost:4081/COMPLETE_DATA_FLOW_IMPLEMENTATION.md</div>
</div>

</div></body></html>
    """)

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "aristotle-docs-and-integration",
        "port": 4081,
        "docs_available": True,
        "files_available": [
            "vllm-batch-client.ts",
            "MIGRATION_GUIDE.md",
            "QUICK_START.md",
            "START_HERE.md",
            "ARISTOTLE_BUILD_INSTRUCTIONS.md"
        ]
    }

@app.get("/{filename}")
async def serve_doc(filename: str):
    """Serve markdown documentation files (catch-all route - must be last!)"""
    # Security: only serve .md files from project root
    if not filename.endswith('.md'):
        return {"error": "Only markdown files allowed"}

    file_path = BASE_DIR / filename
    if not file_path.exists():
        return {"error": f"File not found: {filename}"}

    return FileResponse(file_path, media_type="text/plain")

if __name__ == "__main__":
    print("🚀 Starting vLLM Batch Integration Server")
    print("📦 Serving files at: http://10.0.0.223:4081")
    print("📄 Landing page: http://10.0.0.223:4081")
    print("📥 Download client: http://10.0.0.223:4081/vllm-batch-client.ts")
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=4081,
        log_level="info"
    )

