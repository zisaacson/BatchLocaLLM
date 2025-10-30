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

@app.get("/")
async def index():
    """Landing page with download links"""
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

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "healthy",
        "service": "vllm-batch-integration",
        "files_available": [
            "vllm-batch-client.ts",
            "MIGRATION_GUIDE.md",
            "QUICK_START.md"
        ]
    }

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

