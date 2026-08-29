import os
import uvicorn
from src.api.server import app

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    print("=" * 70)
    print("Starting Self-Healing Cloud Deployment Pipelines Server...")
    print(f"Dashboard UI available at: http://127.0.0.1:{port} or http://localhost:{port}")
    print(f"API Documentation at:    http://127.0.0.1:{port}/docs")
    print("=" * 70)
    uvicorn.run("src.api.server:app", host=host, port=port, reload=False)
