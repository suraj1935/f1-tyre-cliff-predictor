import pathlib, socket, subprocess, sys, time
import httpx
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def site():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    p = subprocess.Popen([sys.executable, "-m", "uvicorn", "api:app", "--port", str(port)], cwd=ROOT,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(60):
        try:
            if httpx.get(url + "/api/health", timeout=1).status_code == 200:
                break
        except Exception:
            time.sleep(0.5)
    else:
        p.terminate(); pytest.fail("server did not start")
    yield url
    p.terminate()
