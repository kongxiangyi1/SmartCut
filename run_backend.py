import sys
import os

os.environ["USE_SIMPLE_TASK_RUNNER"] = "true"
os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ["TORCH_DISTRIBUTED_DEBUG"] = "OFF"
os.environ["NCCL_DEBUG"] = "WARN"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import uvicorn
    from backend.main import app

    print("Starting AutoClip Backend Server...")
    print("Python path:", sys.executable)
    print("Working directory:", os.getcwd())

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000,
        log_level="info",
        access_log=True
    )