"""
start.py -- AI Document Analyzer launcher.
Auto-finds a free port (8000 -> 8001 -> 8002 -> 8003) and starts uvicorn.
Run: python start.py
"""
import socket
import subprocess
import sys
import os

PREFERRED_PORTS = [8000, 8001, 8002, 8003, 8004, 8005]


def find_free_port(candidates):
    for port in candidates:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                # SO_EXCLUSIVEADDRUSE (Windows) mirrors what uvicorn uses internally.
                # This correctly rejects ghost/TIME_WAIT sockets unlike SO_REUSEADDR.
                if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                s.bind(("127.0.0.1", port))
            return port
        except OSError:
            print(f"[INFO] Port {port} is busy, trying next...", flush=True)
    raise RuntimeError("No free port found in range 8000-8005.")


def main():
    print("="*52, flush=True)
    print("  AI Document Analyzer  --  Launcher", flush=True)
    print("="*52, flush=True)

    port = find_free_port(PREFERRED_PORTS)
    print(f"[INFO] Running on port {port}", flush=True)
    print(f"[INFO] API:      http://127.0.0.1:{port}/", flush=True)
    print(f"[INFO] Docs:     http://127.0.0.1:{port}/docs", flush=True)
    print(f"[INFO] Frontend: http://127.0.0.1:{port}/app", flush=True)
    print("[INFO] Press Ctrl+C to stop.\n", flush=True)

    # Write the active port to a small file so other tools can read it
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    with open(".active_port", "w") as f:
        f.write(str(port))

    subprocess.run([
        sys.executable, "-m", "uvicorn",
        "src.main:app",
        "--host", "127.0.0.1",
        "--port", str(port),
    ])


if __name__ == "__main__":
    main()
