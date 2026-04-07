#!/usr/bin/env python3
from __future__ import annotations

import argparse
import getpass
import os
from pathlib import Path

from cores.onboarding import (
    ALLOWED_AUTH_MODES,
    ALLOWED_GOALS,
    ALLOWED_LANGUAGES,
    ALLOWED_SHELLS,
    AuthMode,
    Goal,
    Language,
    OnboardingSelection,
    ShellType,
    apply_scaffolding,
    build_first_success_commands,
    build_manual_edit_instructions,
    build_referral_notes,
    detect_shell,
    has_configured_openai_key,
    onboarding_summary,
    plan_file_writes,
    project_root,
)


GOAL_LABELS: dict[Goal, str] = {
    "quick_demo": "US quick demo (AAPL PDF report)",
    "kr_analysis": "Korean market local analysis",
    "us_analysis": "US market local analysis",
    "docs_only": "Docs only / manual setup path",
}

AUTH_LABELS: dict[AuthMode, str] = {
    "openai_api_key": "OpenAI API key",
    "chatgpt_oauth": "ChatGPT OAuth",
}


def prompt_choice(prompt: str, options: list[tuple[str, str]], default_key: str | None = None) -> str:
    print(prompt)
    for index, (_, label) in enumerate(options, start=1):
        print(f"  {index}. {label}")
    if default_key is not None:
        prompt_text = f"Select an option [default: {default_key}]: "
    else:
        prompt_text = "Select an option: "
    while True:
        raw = input(prompt_text).strip()
        if not raw and default_key is not None:
            return default_key
        if raw.isdigit():
            index = int(raw) - 1
            if 0 <= index < len(options):
                return options[index][0]
        for key, _label in options:
            if raw == key:
                return key
        print("Please choose one of the listed options.")


def prompt_yes_no(prompt: str, default: bool = False) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    raw = input(f"{prompt} {suffix}: ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def print_section(title: str) -> None:
    print()
    print("=" * 72)
    print(title)
    print("=" * 72)


def prompt_hidden_nonempty(prompt: str) -> str:
    while True:
        value = getpass.getpass(prompt).strip()
        if value:
            return value
        print("A non-empty value is required for this step.")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="PRISM-INSIGHT terminal onboarding wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python onboard.py\n"
            "  python onboard.py --auth openai_api_key --goal quick_demo --language en\n"
            "  python onboard.py --auth chatgpt_oauth --goal us_analysis --language ko --print-only\n"
        ),
    )
    parser.add_argument("--goal", choices=ALLOWED_GOALS, help="Preferred onboarding goal")
    parser.add_argument("--auth", choices=ALLOWED_AUTH_MODES, help="Preferred auth branch")
    parser.add_argument("--language", choices=ALLOWED_LANGUAGES, help="Output language for generated commands")
    parser.add_argument("--shell", choices=("auto",) + ALLOWED_SHELLS, default="auto", help="Shell style for rendered commands")
    parser.add_argument("--print-only", action="store_true", help="Do not write files; print manual steps only")
    return parser.parse_args()


def resolve_selection(args: argparse.Namespace, root: Path) -> OnboardingSelection:
    shell: ShellType = detect_shell() if args.shell == "auto" else args.shell

    print_section("PRISM-INSIGHT CUI Onboarding")
    print("This wizard is intentionally narrow.")
    print("- It helps you decide, scaffold safe config files, and print next commands.")
    print("- It does not run Docker, cron installs, or heavy dependency installers.")
    print("- Safe first success avoids Telegram, KIS, and real trading by default.")

    goal: Goal = args.goal or prompt_choice(
        "Choose your onboarding goal:",
        [(item, GOAL_LABELS[item]) for item in ALLOWED_GOALS],
        default_key="quick_demo",
    )
    auth_mode: AuthMode = args.auth or prompt_choice(
        "Choose your auth path:",
        [(item, AUTH_LABELS[item]) for item in ALLOWED_AUTH_MODES],
        default_key="openai_api_key",
    )
    language: Language = args.language or prompt_choice(
        "Choose the output language for generated commands:",
        [(item, item) for item in ALLOWED_LANGUAGES],
        default_key="en",
    )

    configure_telegram = prompt_yes_no("Prepare optional Telegram placeholders in .env?", default=False)
    configure_kis = prompt_yes_no("Prepare optional KIS example config for advanced trading later?", default=False)
    persist_auth_mode = False
    if auth_mode == "chatgpt_oauth":
        persist_auth_mode = prompt_yes_no(
            "Persist PRISM_OPENAI_AUTH_MODE=chatgpt_oauth to .env for later sessions?",
            default=False,
        )

    write_files = False if args.print_only else prompt_yes_no(
        "Scaffold local files now (with confirmation before writes)?",
        default=True,
    )

    openai_api_key = None
    if auth_mode == "openai_api_key" and write_files:
        secrets_path = root / "mcp_agent.secrets.yaml"
        if has_configured_openai_key(secrets_path):
            if prompt_yes_no("A configured OpenAI API key already exists. Keep it and skip rewriting secrets?", default=True):
                openai_api_key = None
            else:
                openai_api_key = prompt_hidden_nonempty("Enter your OpenAI API key (hidden input): ")
        elif prompt_yes_no("Reuse OPENAI_API_KEY from your current environment if available?", default=True):
            openai_api_key = (os.environ.get("OPENAI_API_KEY") or "").strip() or None
            if openai_api_key is None:
                openai_api_key = prompt_hidden_nonempty("Enter your OpenAI API key (hidden input): ")
        else:
            openai_api_key = prompt_hidden_nonempty("Enter your OpenAI API key (hidden input): ")

    return OnboardingSelection(
        goal=goal,
        auth_mode=auth_mode,
        language=language,
        shell=shell,
        write_files=write_files,
        persist_auth_mode=persist_auth_mode,
        configure_telegram=configure_telegram,
        configure_kis=configure_kis,
        openai_api_key=openai_api_key,
    )


def print_plan(root: Path, selection: OnboardingSelection) -> None:
    print_section("Planned onboarding summary")
    for line in onboarding_summary(selection):
        print(f"- {line}")

    planned_writes = plan_file_writes(root, selection)
    if planned_writes:
        print("\nPlanned file changes:")
        for item in planned_writes:
            relative = item.path.relative_to(root)
            print(f"- {relative}: {item.description}")
    else:
        print("\nPlanned file changes: none (print-only/manual path)")

    print("\nConfig mapping table:")
    print("- OpenAI API key -> mcp_agent.secrets.yaml -> openai.api_key")
    print("- Runtime auth mode -> .env -> PRISM_OPENAI_AUTH_MODE")
    print("- Telegram placeholders -> .env -> TELEGRAM_*")
    print("- KIS scaffold -> trading/config/kis_devlp.yaml -> example copy only")


def finish(selection: OnboardingSelection, changed_files: list[Path]) -> None:
    root = project_root()
    print_section("Safe next commands")
    for command in build_first_success_commands(selection):
        print(command)

    print_section("Manual follow-ups")
    for line in build_manual_edit_instructions(selection):
        print(line)

    print_section("Referral-only surfaces")
    for note in build_referral_notes(selection):
        print(f"- {note}")

    if changed_files:
        print_section("Files changed")
        for path in changed_files:
            print(f"- {path.relative_to(root)}")


def main() -> int:
    args = parse_args()
    root = project_root()
    selection = resolve_selection(args, root)
    print_plan(root, selection)

    changed_files: list[Path] = []
    if selection.write_files:
        if prompt_yes_no("Apply these file changes?", default=True):
            changed_files = apply_scaffolding(root, selection)
            print("\nApplied scaffolding changes.")
        else:
            print("\nNo files were changed. Switching to manual instructions.")
    else:
        print("\nPrint-only mode selected. No files will be changed.")

    finish(selection, changed_files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
