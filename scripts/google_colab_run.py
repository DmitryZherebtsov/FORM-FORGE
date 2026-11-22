import glob
import json
import os
import re
import subprocess
import threading
import time
import urllib.request

# 1. Installing zstd, Ollama, and cloudflared
print("⏳ [1/5] Setting up zstd, Ollama, and cloudflared...")
subprocess.run(["pkill", "-f", "cloudflared"], check=False)
subprocess.run("apt-get update -qq && apt-get install -y -qq zstd > /dev/null", shell=True, check=True)
if not os.path.exists("/usr/local/bin/ollama"):
    subprocess.run("curl -fsSL https://ollama.com/install.sh | sh > /dev/null 2>&1", shell=True, check=True)
if not os.path.exists("/usr/local/bin/cloudflared"):
    subprocess.run(
        "curl -sL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared",
        shell=True,
        check=True,
    )
print("✅ [1/5] Dependencies installed.")

# 2. Launching the Ollama server in the background
print("⏳ [2/5] Starting Ollama server on 0.0.0.0:11434...")
try:
    urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
    print("✅ [2/5] Ollama server is already running.")
except Exception:
    ollama_env = os.environ.copy()
    ollama_env.update({"OLLAMA_HOST": "0.0.0.0:11434", "OLLAMA_ORIGINS": "*"})
    ollama_proc = subprocess.Popen(
        ["ollama", "serve"],
        env=ollama_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        try:
            urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=2)
            break
        except Exception:
            time.sleep(1)
    else:
        raise RuntimeError("Ollama server failed to start on 127.0.0.1:11434.")
    print("✅ [2/5] Ollama server started.")

# 3. Loading Polish Bielik-11B from Hugging Face (with automatic fallback to Qwen 2.5 7B)
CANDIDATE_MODELS = [
    "hf.co/speakleash/Bielik-11B-v3.0-Instruct-GGUF:Q4_K_M",
    "qwen2.5:7b",
]

active_model = None
for candidate in CANDIDATE_MODELS:
    print(f"⏳ [3/5] Pulling model {candidate}...")
    pull_proc = subprocess.Popen(
        ["ollama", "pull", candidate],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    last_bytes = -1
    stalled_sec = 0
    while pull_proc.poll() is None:
        time.sleep(10)
        partials = glob.glob("/root/.ollama/models/blobs/*partial*")
        cur_bytes = sum(os.path.getsize(p) for p in partials if os.path.exists(p))
        if cur_bytes > 0:
            print(f"   ...downloaded {cur_bytes / (1024**3):.2f} GB")
        if cur_bytes == last_bytes:
            stalled_sec += 10
        else:
            last_bytes = cur_bytes
            stalled_sec = 0
        if stalled_sec >= 90:
            print(f"⚠️ Download stalled for {candidate}, terminating and trying fallback...")
            pull_proc.terminate()
            break

    if pull_proc.returncode == 0:
        active_model = candidate
        print(f"✅ [3/5] Model {active_model} pulled successfully.")
        break
    print(f"⚠️ Could not pull {candidate}, trying fallback...")

if not active_model:
    raise RuntimeError("Failed to pull any LLM model.")

# 4. Warming up the model in T4 video memory
print(f"⏳ [4/5] Loading {active_model} into GPU VRAM (keep_alive=-1)...")
req = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps({"model": active_model, "prompt": "OK", "stream": False, "keep_alive": -1}).encode(),
    headers={"Content-Type": "application/json"},
)
urllib.request.urlopen(req, timeout=180).read()
print(f"✅ [4/5] Model {active_model} is loaded into VRAM and ready!")

# 5. Set up an HTTPS tunnel and output the public URL
print("⏳ [5/5] Starting Cloudflare quick tunnel and waiting for edge registration...")
tunnel_proc = subprocess.Popen(
    [
        "cloudflared",
        "tunnel",
        "--url",
        "http://127.0.0.1:11434",
        "--http-host-header",
        "localhost:11434",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
)

tunnel_url = None
registered = threading.Event()
recent_logs: list[str] = []


def _drain_tunnel_logs() -> None:
    global tunnel_url
    assert tunnel_proc.stdout is not None
    for line in tunnel_proc.stdout:
        clean = line.strip()
        if clean:
            recent_logs.append(clean)
            if len(recent_logs) > 20:
                recent_logs.pop(0)
        match = re.search(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", line)
        if match and not tunnel_url:
            tunnel_url = match.group(0)
            print(f"🔗 Tunnel URL assigned: {tunnel_url}")
        if "Registered tunnel connection" in line:
            registered.set()


threading.Thread(target=_drain_tunnel_logs, daemon=True).start()

if not registered.wait(timeout=45) or not tunnel_url:
    tunnel_proc.terminate()
    tail = "\n".join(recent_logs[-5:])
    raise RuntimeError(f"Cloudflare tunnel failed to register within 45s.\nRecent logs:\n{tail}")

print("✅ [5/5] Tunnel connection registered with Cloudflare edge!")
print("\n" + "=" * 60)
print(f"AI_BASE_URL={tunnel_url}")
print(f"AI_MODEL_NAME={active_model}")
print("=" * 60 + "\n")
print("🟢 Keep this cell running while testing. Stop & disconnect runtime when done to save GPU quota.")

# Keep the cell active during demo
while tunnel_proc.poll() is None:
    time.sleep(30)

raise RuntimeError("Cloudflare tunnel process exited unexpectedly.")
