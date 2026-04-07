from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
from typing import Literal

import yaml


AuthMode = Literal["openai_api_key", "chatgpt_oauth"]
Goal = Literal["quick_demo", "kr_analysis", "us_analysis", "docs_only"]
ShellType = Literal["bash", "powershell", "cmd"]
Language = Literal["ko", "en"]


ALLOWED_LANGUAGES: tuple[Language, ...] = ("ko", "en")
ALLOWED_GOALS: tuple[Goal, ...] = ("quick_demo", "kr_analysis", "us_analysis", "docs_only")
ALLOWED_AUTH_MODES: tuple[AuthMode, ...] = ("openai_api_key", "chatgpt_oauth")
ALLOWED_SHELLS: tuple[ShellType, ...] = ("bash", "powershell", "cmd")


@dataclass(frozen=True)
class OnboardingSelection:
    goal: Goal
    auth_mode: AuthMode
    language: Language
    shell: ShellType
    write_files: bool
    persist_auth_mode: bool = False
    configure_telegram: bool = False
    configure_kis: bool = False
    openai_api_key: str | None = None


@dataclass(frozen=True)
class PlannedWrite:
    path: Path
    description: str


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def detect_shell() -> ShellType:
    if os.name == "nt":
        if os.environ.get("PSModulePath") or os.environ.get("POWERSHELL_DISTRIBUTION_CHANNEL"):
            return "powershell"
        comspec = os.environ.get("ComSpec", "").lower()
        if "cmd.exe" in comspec:
            return "cmd"
        return "powershell"

    shell = os.environ.get("SHELL", "").lower()
    return "bash" if shell else "bash"


def default_python_command(shell: ShellType | None = None) -> str:
    shell = shell or detect_shell()
    return "python" if shell in {"powershell", "cmd"} else "python3"


def ensure_nested_mapping(data: dict, *keys: str) -> dict:
    cursor = data
    for key in keys:
        current = cursor.get(key)
        if not isinstance(current, dict):
            current = {}
            cursor[key] = current
        cursor = current
    return cursor


def set_nested_value(data: dict, dotted_path: str, value: str) -> None:
    parts = dotted_path.split(".")
    parent = ensure_nested_mapping(data, *parts[:-1])
    parent[parts[-1]] = value


def is_placeholder_value(value: str | None) -> bool:
    if value is None:
        return True
    normalized = value.strip().lower()
    return normalized in {"", "example key", "your-api-key", "your_api_key"}


def read_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def load_yaml_from_target_or_example(target: Path, example: Path) -> dict:
    if target.exists():
        return read_yaml(target)
    if example.exists():
        return read_yaml(example)
    return {}


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def copy_if_missing(target: Path, example: Path) -> bool:
    if target.exists() or not example.exists():
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(example, target)
    return True


def has_configured_openai_key(path: Path) -> bool:
    data = read_yaml(path)
    openai = data.get("openai", {})
    if not isinstance(openai, dict):
        return False
    return not is_placeholder_value(openai.get("api_key"))


def upsert_env_values(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    changed_keys: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        replaced = False
        for key, value in values.items():
            if re.match(rf"^\s*{re.escape(key)}=", line):
                new_lines.append(f"{key}={value}")
                changed_keys.add(key)
                replaced = True
                break
        if not replaced:
            new_lines.append(line)
    for key, value in values.items():
        if key not in changed_keys:
            new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def build_shell_command(shell: ShellType, base_command: str, env: dict[str, str] | None = None) -> str:
    env = env or {}
    if not env:
        return base_command
    if shell == "powershell":
        prefix = "; ".join(f"$env:{key}='{value}'" for key, value in env.items())
        return f"{prefix}; {base_command}"
    if shell == "cmd":
        prefix = " && ".join(f"set {key}={value}" for key, value in env.items())
        return f"{prefix} && {base_command}"
    prefix = " ".join(f"{key}={value}" for key, value in env.items())
    return f"{prefix} {base_command}"


def build_first_success_commands(selection: OnboardingSelection) -> list[str]:
    python_cmd = default_python_command(selection.shell)
    commands: list[str] = []

    if selection.auth_mode == "openai_api_key":
        if selection.goal == "quick_demo":
            commands.append(f"{python_cmd} demo.py AAPL --language {selection.language}")
        elif selection.goal == "us_analysis":
            commands.append(
                f"{python_cmd} prism-us/us_stock_analysis_orchestrator.py --mode morning --no-telegram --language {selection.language}"
            )
        elif selection.goal == "kr_analysis":
            commands.append(
                f"{python_cmd} stock_analysis_orchestrator.py --mode morning --no-telegram --language {selection.language}"
            )
        return commands

    commands.append(f"{python_cmd} -m cores.chatgpt_proxy.oauth_login")
    if selection.goal == "docs_only":
        return commands

    if selection.goal == "kr_analysis":
        base = f"{python_cmd} stock_analysis_orchestrator.py --mode morning --no-telegram --language {selection.language}"
    else:
        base = (
            f"{python_cmd} prism-us/us_stock_analysis_orchestrator.py --mode morning --no-telegram --language {selection.language}"
        )
    commands.append(build_shell_command(selection.shell, base, {"PRISM_OPENAI_AUTH_MODE": "chatgpt_oauth"}))
    return commands


def build_manual_edit_instructions(selection: OnboardingSelection) -> list[str]:
    if selection.shell == "powershell":
        copy_config = "Copy-Item mcp_agent.config.yaml.example mcp_agent.config.yaml"
        copy_secrets = "Copy-Item mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml"
    elif selection.shell == "cmd":
        copy_config = r"copy mcp_agent.config.yaml.example mcp_agent.config.yaml"
        copy_secrets = r"copy mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml"
    else:
        copy_config = "cp mcp_agent.config.yaml.example mcp_agent.config.yaml"
        copy_secrets = "cp mcp_agent.secrets.yaml.example mcp_agent.secrets.yaml"

    instructions = [
        "Manual edits:",
        "1. Copy example configs if they do not exist yet:",
        f"   - {copy_config}",
        f"   - {copy_secrets}",
    ]
    if selection.auth_mode == "openai_api_key":
        instructions.append("2. Set `openai.api_key` in `mcp_agent.secrets.yaml`.")
    else:
        instructions.extend(
            [
                "2. Run ChatGPT OAuth login:",
                f"   - {default_python_command(selection.shell)} -m cores.chatgpt_proxy.oauth_login",
                "3. Optionally persist `PRISM_OPENAI_AUTH_MODE=chatgpt_oauth` in `.env`.",
            ]
        )
    if selection.configure_telegram:
        instructions.append("4. Fill Telegram values in `.env` if you want messaging later.")
    if selection.configure_kis:
        instructions.append("5. Copy and fill `trading/config/kis_devlp.yaml.example` for advanced KIS setup.")
    return instructions


def build_referral_notes(selection: OnboardingSelection) -> list[str]:
    notes = []
    if selection.goal == "docs_only":
        notes.append("See docs/SETUP.md (or docs/SETUP_ko.md) for full platform setup.")
    notes.append("Docker onboarding remains in README_DOCKER.md / README_DOCKER_ko.md.")
    notes.append("Cron setup remains in utils/setup_crontab.sh and utils/setup_us_crontab.sh.")
    if selection.configure_kis:
        notes.append("KIS is advanced and not required for first success.")
    return notes


def plan_file_writes(root: Path, selection: OnboardingSelection) -> list[PlannedWrite]:
    writes: list[PlannedWrite] = []
    if not selection.write_files:
        return writes

    config_target = root / "mcp_agent.config.yaml"
    if not config_target.exists():
        writes.append(PlannedWrite(config_target, "Copy MCP config scaffold from example"))

    if selection.auth_mode == "openai_api_key" and (
        selection.openai_api_key or not has_configured_openai_key(root / "mcp_agent.secrets.yaml")
    ):
        writes.append(
            PlannedWrite(root / "mcp_agent.secrets.yaml", "Set nested `openai.api_key` in secrets config")
        )
    if selection.persist_auth_mode or selection.configure_telegram:
        writes.append(PlannedWrite(root / ".env", "Update runtime env file"))
    if selection.configure_kis:
        target = root / "trading" / "config" / "kis_devlp.yaml"
        if not target.exists():
            writes.append(PlannedWrite(target, "Copy KIS example config for optional advanced setup"))
    return writes


def apply_scaffolding(root: Path, selection: OnboardingSelection) -> list[Path]:
    changed: list[Path] = []
    config_target = root / "mcp_agent.config.yaml"
    config_example = root / "mcp_agent.config.yaml.example"
    if copy_if_missing(config_target, config_example):
        changed.append(config_target)

    if selection.auth_mode == "openai_api_key" and selection.openai_api_key:
        secrets_target = root / "mcp_agent.secrets.yaml"
        secrets_example = root / "mcp_agent.secrets.yaml.example"
        secrets_data = load_yaml_from_target_or_example(secrets_target, secrets_example)
        set_nested_value(secrets_data, "openai.api_key", selection.openai_api_key)
        write_yaml(secrets_target, secrets_data)
        changed.append(secrets_target)

    env_updates: dict[str, str] = {}
    if selection.persist_auth_mode:
        env_updates["PRISM_OPENAI_AUTH_MODE"] = "chatgpt_oauth"
    if selection.configure_telegram:
        env_target = root / ".env"
        env_example = root / ".env.example"
        if copy_if_missing(env_target, env_example):
            changed.append(env_target)
        env_updates.setdefault("TELEGRAM_BOT_TOKEN", "your_bot_token")
        env_updates.setdefault("TELEGRAM_CHANNEL_ID", "your_channel_id")
        upsert_env_values(env_target, env_updates)
        if env_target not in changed:
            changed.append(env_target)
    elif env_updates:
        env_target = root / ".env"
        upsert_env_values(env_target, env_updates)
        changed.append(env_target)

    if selection.configure_kis:
        kis_target = root / "trading" / "config" / "kis_devlp.yaml"
        kis_example = root / "trading" / "config" / "kis_devlp.yaml.example"
        if copy_if_missing(kis_target, kis_example):
            changed.append(kis_target)

    return changed


def onboarding_summary(selection: OnboardingSelection) -> list[str]:
    summary = [
        f"Goal: {selection.goal}",
        f"Auth: {selection.auth_mode}",
        f"Language: {selection.language}",
        f"Shell: {selection.shell}",
        f"Write local files: {'yes' if selection.write_files else 'no'}",
    ]
    if selection.persist_auth_mode:
        summary.append("Persist auth mode to .env: yes")
    if selection.configure_telegram:
        summary.append("Telegram placeholders: yes")
    if selection.configure_kis:
        summary.append("KIS example scaffold: yes")
    return summary
