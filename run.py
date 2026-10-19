import os
from waitress import serve
from app import create_app

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    print(f"Factora: http://localhost:{port}", flush=True)
    serve(create_app(), host=os.environ.get("HOST", "127.0.0.1"), port=port, threads=8)
