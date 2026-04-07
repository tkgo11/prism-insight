from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cores.onboarding import (
    OnboardingSelection,
    apply_scaffolding,
    build_first_success_commands,
    build_manual_edit_instructions,
    build_shell_command,
    plan_file_writes,
    upsert_env_values,
)


def make_selection(**overrides):
    base = dict(
        goal="quick_demo",
        auth_mode="openai_api_key",
        language="en",
        shell="bash",
        write_files=True,
        persist_auth_mode=False,
        configure_telegram=False,
        configure_kis=False,
        openai_api_key="sk-test",
    )
    base.update(overrides)
    return OnboardingSelection(**base)


def write_example_files(root: Path) -> None:
    (root / "mcp_agent.secrets.yaml.example").write_text(
        "$schema: ../../schema/mcp-agent.config.schema.json\n\nopenai:\n  api_key: example key\nanthropic:\n  api_key: example key\n",
        encoding="utf-8",
    )
    (root / "mcp_agent.config.yaml.example").write_text(
        "execution_engine: asyncio\nopenai:\n  default_model: gpt-5.1\n",
        encoding="utf-8",
    )
    (root / ".env.example").write_text("TELEGRAM_BOT_TOKEN=your_bot_token\n", encoding="utf-8")
    kis_dir = root / "trading" / "config"
    kis_dir.mkdir(parents=True, exist_ok=True)
    (kis_dir / "kis_devlp.yaml.example").write_text("default_unit_amount: 10000\n", encoding="utf-8")


def test_build_first_success_commands_for_openai_demo():
    selection = make_selection()
    assert build_first_success_commands(selection) == ["python3 demo.py AAPL --language en"]


def test_build_first_success_commands_for_oauth_powershell():
    selection = make_selection(
        auth_mode="chatgpt_oauth",
        shell="powershell",
        goal="us_analysis",
        openai_api_key=None,
    )
    commands = build_first_success_commands(selection)
    assert commands[0] == "python -m cores.chatgpt_proxy.oauth_login"
    assert "PRISM_OPENAI_AUTH_MODE" in commands[1]
    assert commands[1].startswith("$env:PRISM_OPENAI_AUTH_MODE='chatgpt_oauth';")


def test_plan_file_writes_respects_scope(tmp_path: Path):
    write_example_files(tmp_path)
    selection = make_selection(configure_telegram=True, configure_kis=True)
    writes = plan_file_writes(tmp_path, selection)
    relative_paths = {item.path.relative_to(tmp_path).as_posix() for item in writes}
    assert "mcp_agent.config.yaml" in relative_paths
    assert "mcp_agent.secrets.yaml" in relative_paths
    assert ".env" in relative_paths
    assert "trading/config/kis_devlp.yaml" in relative_paths


def test_apply_scaffolding_writes_nested_openai_key(tmp_path: Path):
    write_example_files(tmp_path)
    selection = make_selection(configure_telegram=True, persist_auth_mode=False)
    changed = apply_scaffolding(tmp_path, selection)
    assert {path.name for path in changed} >= {"mcp_agent.config.yaml", "mcp_agent.secrets.yaml", ".env"}

    secrets = yaml.safe_load((tmp_path / "mcp_agent.secrets.yaml").read_text(encoding="utf-8"))
    assert secrets["openai"]["api_key"] == "sk-test"


def test_apply_scaffolding_persists_oauth_env(tmp_path: Path):
    write_example_files(tmp_path)
    selection = make_selection(
        auth_mode="chatgpt_oauth",
        goal="us_analysis",
        openai_api_key=None,
        persist_auth_mode=True,
    )
    apply_scaffolding(tmp_path, selection)
    env_text = (tmp_path / ".env").read_text(encoding="utf-8")
    assert "PRISM_OPENAI_AUTH_MODE=chatgpt_oauth" in env_text


def test_upsert_env_values_replaces_existing_key(tmp_path: Path):
    env_path = tmp_path / ".env"
    env_path.write_text("PRISM_OPENAI_AUTH_MODE=api_key\nOTHER=value\n", encoding="utf-8")
    upsert_env_values(env_path, {"PRISM_OPENAI_AUTH_MODE": "chatgpt_oauth"})
    env_text = env_path.read_text(encoding="utf-8")
    assert "PRISM_OPENAI_AUTH_MODE=chatgpt_oauth" in env_text
    assert "OTHER=value" in env_text


def test_build_shell_command_for_cmd():
    rendered = build_shell_command(
        "cmd",
        "python stock_analysis_orchestrator.py --mode morning --no-telegram --language en",
        {"PRISM_OPENAI_AUTH_MODE": "chatgpt_oauth"},
    )
    assert rendered.startswith("set PRISM_OPENAI_AUTH_MODE=chatgpt_oauth &&")


def test_manual_edit_instructions_use_cmd_copy_when_requested():
    selection = make_selection(shell="cmd", write_files=False)
    instructions = build_manual_edit_instructions(selection)
    assert any(line.strip().startswith("- copy mcp_agent.config.yaml.example") for line in instructions)
