import time
import requests
import subprocess
import sys

class LocalMlFlowServer:
    
    process: subprocess.Popen | None
    
    def __init__(self):
        self.process = subprocess.Popen([
            sys.executable,
            "-m",
            "mlflow",
            "server",
            "--backend-store-uri", "sqlite:///mlflow.db",
            "--default-artifact-root", "./mlruns",
            "--host", "0.0.0.0",
            "--port", "5000",
        ])
        
        timeout = 30
        url = "http://127.0.0.1:5000"
        start = time.time()
        
        while time.time() - start < timeout:
            try:
                requests.get(url, timeout=1)
                break
            except requests.RequestException:
                time.sleep(1)

if __name__ == "__main__":
    LocalMlFlowServer()
    while True:
        time.sleep(10)
