"""Generated local assistant and device profile."""

from __future__ import annotations

import getpass
import os
import platform
import socket
from datetime import UTC, datetime
from pathlib import Path

from sage.contracts import AssistantProfile, DeviceProfile


def generate_assistant_profile() -> AssistantProfile:
    now = datetime.now(UTC)
    return AssistantProfile(
        assistant_name=os.environ.get("SAGE_ASSISTANT_NAME", "SAGE"),
        assistant_role=os.environ.get(
            "SAGE_ASSISTANT_ROLE",
            "Local-first voice command layer for this laptop.",
        ),
        user_display_name=os.environ.get("SAGE_USER_NAME") or getpass.getuser(),
        device=generate_device_profile(now),
        updated_at=now,
    )


def generate_device_profile(generated_at: datetime | None = None) -> DeviceProfile:
    os_release = _read_os_release()
    return DeviceProfile(
        hostname=socket.gethostname(),
        username=getpass.getuser(),
        home_dir=Path.home(),
        os_name=os_release.get("PRETTY_NAME") or platform.platform(),
        kernel=platform.release(),
        machine=platform.machine(),
        desktop=os.environ.get("XDG_CURRENT_DESKTOP"),
        session_type=os.environ.get("XDG_SESSION_TYPE"),
        shell=os.environ.get("SHELL"),
        cpu_model=_cpu_model(),
        cpu_count=os.cpu_count(),
        ram_total_gib=_ram_total_gib(),
        generated_at=generated_at or datetime.now(UTC),
    )


def _read_os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text(errors="ignore").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value.strip().strip('"')
    return values


def _cpu_model() -> str | None:
    path = Path("/proc/cpuinfo")
    if not path.exists():
        return None
    for line in path.read_text(errors="ignore").splitlines():
        if line.lower().startswith("model name") and ":" in line:
            return line.split(":", 1)[1].strip()
    return None


def _ram_total_gib() -> float | None:
    path = Path("/proc/meminfo")
    if not path.exists():
        return None
    for line in path.read_text(errors="ignore").splitlines():
        if line.startswith("MemTotal:"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    return int(parts[1]) / 1024 / 1024
                except ValueError:
                    return None
    return None
