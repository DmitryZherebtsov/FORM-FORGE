"""Bootstrap, run, and verify the COI Form Digitization project."""

import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"
ENV_FILE = ROOT_DIR / ".env"
ENV_TEMPLATE = ROOT_DIR / "_documentation" / ".env.example"
TOKEN_CODE = (
    "from coi_form_digitization.infrastructure.config import Settings; "
    "from coi_form_digitization.infrastructure.jwt_service import JwtTokenService; "
    "print(JwtTokenService(Settings()).issue('developer'))"
)

_STOP_REQUESTED = False


def _node_command(command: str, *arguments: str) -> list[str]:
    if os.name == "nt" and command in {"npm", "npx"}:
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", command, *arguments]
    return [command, *arguments]


def _run_checked(command: list[str], cwd: Path) -> None:
    print(f"\n$ {' '.join(command)}  [{cwd.relative_to(ROOT_DIR)}]", flush=True)
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise SystemExit(result.returncode)


def _ensure_env() -> None:
    if ENV_FILE.exists():
        return
    if not ENV_TEMPLATE.is_file():
        raise SystemExit(f"Environment template not found: {ENV_TEMPLATE}")

    lines = ENV_TEMPLATE.read_text(encoding="utf-8").splitlines()
    secrets_by_name = {
        "JWT_SECRET_KEY": secrets.token_hex(32),
        "DEMO_ACCESS_KEY": secrets.token_hex(24),
    }
    replaced: set[str] = set()
    for index, line in enumerate(lines):
        for name, value in secrets_by_name.items():
            if line.startswith(f"{name}="):
                lines[index] = f"{name}={value}"
                replaced.add(name)
    missing = set(secrets_by_name) - replaced
    if missing:
        raise SystemExit(f"Environment template is missing: {', '.join(sorted(missing))}")

    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Created .env with fresh local development secrets.")


def _bootstrap_local() -> None:
    _ensure_env()
    if not (BACKEND_DIR / ".venv").is_dir():
        _run_checked(["uv", "sync"], BACKEND_DIR)
    if not (FRONTEND_DIR / "node_modules").is_dir():
        _run_checked(_node_command("npm", "install"), FRONTEND_DIR)


def _request_shutdown(_signum: int, _frame: object) -> None:
    global _STOP_REQUESTED
    _STOP_REQUESTED = True


def _start_child(
    command: list[str], cwd: Path, environment: dict[str, str] | None = None
) -> subprocess.Popen:
    print(f"\n$ {' '.join(command)}  [{cwd.relative_to(ROOT_DIR)}]", flush=True)
    options: dict[str, object] = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    child_environment = os.environ.copy()
    if environment:
        child_environment.update(environment)
    return subprocess.Popen(command, cwd=cwd, env=child_environment, **options)


def _stop_children(children: list[tuple[str, subprocess.Popen]]) -> None:
    for _name, process in children:
        try:
            if os.name == "nt":
                if process.poll() is None:
                    process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                os.killpg(process.pid, signal.SIGTERM)
        except (OSError, ProcessLookupError):
            if process.poll() is None:
                process.terminate()

    for _name, process in children:
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    check=False,
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            process.wait()


def _wait_for_health(
    url: str,
    timeout_seconds: int = 120,
    children: list[tuple[str, subprocess.Popen]] | None = None,
) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while not _STOP_REQUESTED and time.monotonic() < deadline:
        if children:
            for name, process in children:
                exit_code = process.poll()
                if exit_code is not None:
                    raise RuntimeError(f"{name} exited before the backend became healthy (code {exit_code}).")
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return True
        except OSError:
            pass
        time.sleep(1)
    return False


def _print_token(command: list[str], cwd: Path) -> str:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode:
        if result.stderr:
            print(result.stderr, file=sys.stderr, end="")
        raise SystemExit(result.returncode)
    token = result.stdout.strip()
    if not token:
        raise SystemExit("JWT token generation returned no token.")
    print("\nReady-to-paste JWT token (valid for 24 hours):\n")
    print(token)
    return token


def _serve_local() -> int:
    global _STOP_REQUESTED
    _STOP_REQUESTED = False
    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)
    children: list[tuple[str, subprocess.Popen]] = []
    try:
        children.append(
            (
                "Backend",
                _start_child(
                    [
                        "uv",
                        "run",
                        "uvicorn",
                        "coi_form_digitization.main:app",
                        "--reload",
                        "--host",
                        "0.0.0.0",
                        "--port",
                        "8000",
                    ],
                    BACKEND_DIR,
                ),
            )
        )
        token = _print_token(["uv", "run", "python", "-c", TOKEN_CODE], BACKEND_DIR)
        children.append(
            (
                "Frontend",
                _start_child(
                    _node_command("npm", "run", "dev"),
                    FRONTEND_DIR,
                    {"VITE_DEV_TOKEN": token},
                ),
            )
        )

        print("\nWaiting for http://127.0.0.1:8000/api/v1/health ...", flush=True)
        if not _wait_for_health(
            "http://127.0.0.1:8000/api/v1/health", children=children
        ):
            return 130 if _STOP_REQUESTED else 1

        print("\nApplication ready: http://localhost:5173", flush=True)
        webbrowser.open("http://localhost:5173")

        while not _STOP_REQUESTED:
            for name, process in children:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"{name} exited with code {exit_code}; stopping the other process.")
                    return exit_code or 1
            time.sleep(0.5)
        return 130
    except OSError as exc:
        print(f"Could not start local services: {exc}", file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    finally:
        _stop_children(children)


def _run_docker() -> int:
    _ensure_env()
    if not shutil.which("docker"):
        print("Docker was not found on PATH.", file=sys.stderr)
        return 1
    _run_checked(["docker", "compose", "up", "--build", "-d"], ROOT_DIR)
    print("\nWaiting for http://127.0.0.1:8080/api/v1/health ...", flush=True)
    if not _wait_for_health("http://127.0.0.1:8080/api/v1/health"):
        print("Docker application did not become healthy within 120 seconds.", file=sys.stderr)
        return 1

    token = _print_token(
        ["docker", "compose", "exec", "-T", "backend", "python", "-c", TOKEN_CODE],
        ROOT_DIR,
    )
    print("\nApplication ready: http://localhost:8080", flush=True)
    webbrowser.open(f"http://localhost:8080/#token={token}")
    return 0


def _run_tests() -> int:
    commands = [
        (["uv", "run", "ruff", "check", "src", "tests"], BACKEND_DIR),
        (["uv", "run", "pytest"], BACKEND_DIR),
        (_node_command("npx", "tsc", "--noEmit"), FRONTEND_DIR),
        (_node_command("npm", "run", "build"), FRONTEND_DIR),
    ]
    for command, cwd in commands:
        _run_checked(command, cwd)
    return 0


def main(arguments: list[str]) -> int:
    if arguments == ["--test"]:
        return _run_tests()
    if arguments == ["--docker"]:
        return _run_docker()
    if arguments:
        print("Usage: python scripts/run.py [--docker | --test]", file=sys.stderr)
        return 2

    _bootstrap_local()
    return _serve_local()


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except KeyboardInterrupt:
        raise SystemExit(130) from None
