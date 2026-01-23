#!/usr/bin/env python3
"""
Blackreach CLI - Interactive Browser Agent

Usage:
    blackreach                           # Interactive mode
    blackreach run "go to wikipedia"     # Run with goal
    blackreach config                    # Configure settings
    blackreach models                    # List models
    blackreach setup                     # First-time setup
"""

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from pathlib import Path
import subprocess
import sys
import shutil
import signal
import atexit

from blackreach.config import config_manager, AVAILABLE_MODELS, CONFIG_FILE
from blackreach.exceptions import SessionNotFoundError

# Global reference to active agent for cleanup
_active_agent = None

def _cleanup_keyboard():
    """Release all keyboard keys on exit to prevent stuck keys."""
    global _active_agent
    if _active_agent and hasattr(_active_agent, 'hand') and _active_agent.hand:
        try:
            _active_agent.hand._release_all_keys()
        except Exception:
            pass

def _signal_handler(signum, frame):
    """Handle termination signals by cleaning up keyboard state."""
    _cleanup_keyboard()
    sys.exit(0)

# Register cleanup handlers
atexit.register(_cleanup_keyboard)
signal.signal(signal.SIGTERM, _signal_handler)
# SIGINT is handled by KeyboardInterrupt, but register anyway for safety
try:
    signal.signal(signal.SIGINT, _signal_handler)
except ValueError:
    pass  # Can't set SIGINT handler in some contexts

console = Console()

# Version
__version__ = "0.3.0"


BANNER = """[bold cyan]
╔══════════════════════════════════════════════════════════╗
║   ██████╗ ██╗      █████╗  ██████╗██╗  ██╗              ║
║   ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝              ║
║   ██████╔╝██║     ███████║██║     █████╔╝               ║
║   ██╔══██╗██║     ██╔══██║██║     ██╔═██╗               ║
║   ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗              ║
║   ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝              ║
║                                                          ║
║   [white]Autonomous Browser Agent[/white]              [dim]v0.3.0[/dim]   ║
╚══════════════════════════════════════════════════════════╝[/bold cyan]
"""


def is_first_run() -> bool:
    """Check if this is the first time running Blackreach."""
    return not CONFIG_FILE.exists()


def check_playwright_browsers() -> bool:
    """Check if Playwright browsers are installed."""
    try:
        # Check if chromium exists in playwright cache
        result = subprocess.run(
            ["playwright", "install", "--dry-run", "chromium"],
            capture_output=True,
            text=True
        )
        return "already installed" in result.stdout.lower() or result.returncode == 0
    except FileNotFoundError:
        return False


def install_playwright_browsers():
    """Install Playwright browsers."""
    console.print("\n[yellow]Installing browser (this may take a minute)...[/yellow]")
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Installing Chromium...", total=None)
        try:
            subprocess.run(
                ["playwright", "install", "chromium"],
                capture_output=True,
                check=True
            )
            progress.update(task, description="[green]Chromium installed![/green]")
        except subprocess.CalledProcessError as e:
            progress.update(task, description="[red]Failed to install browser[/red]")
            console.print(f"[red]Error: {e.stderr}[/red]")
            console.print("[yellow]Try running: playwright install chromium[/yellow]")
            return False
    return True


def check_ollama_running() -> bool:
    """Check if Ollama is running."""
    try:
        import ollama
        ollama.list()
        return True
    except Exception:
        return False


def run_first_time_setup():
    """Run the first-time setup wizard."""
    console.print(BANNER)
    console.print("[bold green]Welcome to Blackreach![/bold green]\n")
    console.print("Let's get you set up. This will only take a moment.\n")

    # Step 1: Check/Install Playwright
    console.print("[bold]Step 1/3: Browser Setup[/bold]")
    if not check_playwright_browsers():
        if Confirm.ask("Blackreach needs a browser. Install Chromium?", default=True):
            if not install_playwright_browsers():
                console.print("[red]Browser installation failed. You can try later with:[/red]")
                console.print("  playwright install chromium")
        else:
            console.print("[yellow]Skipped. Run 'playwright install chromium' when ready.[/yellow]")
    else:
        console.print("[green]✓ Browser already installed[/green]")

    # Step 2: Choose provider
    console.print("\n[bold]Step 2/3: Choose AI Provider[/bold]")
    console.print("  [cyan]1[/cyan] - Ollama (local, free, private)")
    console.print("  [cyan]2[/cyan] - xAI (cloud, Grok-2)")
    console.print("  [cyan]3[/cyan] - OpenAI (cloud, paid)")
    console.print("  [cyan]4[/cyan] - Anthropic (cloud, paid)")
    console.print("  [cyan]5[/cyan] - Google (cloud, Gemini 2.5)")

    choice = Prompt.ask("Select provider", choices=["1", "2", "3", "4", "5"], default="1")

    provider_map = {"1": "ollama", "2": "xai", "3": "openai", "4": "anthropic", "5": "google"}
    provider = provider_map[choice]

    # Create initial config
    config_manager.load()  # Creates default config
    config_manager.set_default_provider(provider)

    # Step 3: API key if needed
    console.print(f"\n[bold]Step 3/3: Configure {provider.capitalize()}[/bold]")

    if provider == "ollama":
        if check_ollama_running():
            console.print("[green]✓ Ollama is running[/green]")
        else:
            console.print("[yellow]Ollama not detected. Make sure to start it:[/yellow]")
            console.print("  ollama serve")

        # Ask which model
        console.print("\nAvailable Ollama models: qwen2.5:7b, llama3.2:3b, mistral:7b")
        model = Prompt.ask("Default model", default="qwen2.5:7b")
        config_manager.set_default_model("ollama", model)

    else:
        # Cloud provider - need API key
        key_urls = {
            "xai": "https://console.x.ai/",
            "openai": "https://platform.openai.com/api-keys",
            "anthropic": "https://console.anthropic.com/settings/keys",
            "google": "https://aistudio.google.com/app/apikey"
        }
        console.print(f"Get your API key at: [link]{key_urls[provider]}[/link]")
        api_key = Prompt.ask("API key", password=True)

        if api_key:
            config_manager.set_api_key(provider, api_key)
            console.print("[green]✓ API key saved[/green]")

    # Done!
    console.print("\n" + "─" * 50)
    console.print("[bold green]Setup complete![/bold green]\n")
    console.print("You can now use Blackreach:")
    console.print("  [cyan]blackreach[/cyan]                    - Interactive mode")
    console.print("  [cyan]blackreach run \"your goal\"[/cyan]   - Run with a goal")
    console.print("  [cyan]blackreach config[/cyan]             - Change settings")
    console.print("  [cyan]blackreach --help[/cyan]             - Show all commands")
    console.print()

    return True


@click.group(invoke_without_command=True)
@click.pass_context
@click.version_option(version=__version__, prog_name="blackreach")
def cli(ctx):
    """Blackreach - Autonomous Browser Agent

    Run without arguments for interactive mode.
    """
    # Check for first run
    if is_first_run() and ctx.invoked_subcommand is None:
        run_first_time_setup()
        return

    if ctx.invoked_subcommand is None:
        interactive_mode()


@cli.command()
@click.argument('goal', required=False)
@click.option('--provider', '-p', help='LLM provider (ollama, openai, anthropic, google, xai)')
@click.option('--model', '-m', help='Model to use')
@click.option('--headless/--no-headless', default=None, help='Run browser headless')
@click.option('--steps', '-s', type=int, help='Maximum steps')
@click.option('--resume', '-r', type=int, help='Resume a paused session by ID')
def run(goal: str, provider: str, model: str, headless: bool, steps: int, resume: int):
    """Run the agent with a goal.

    Example: blackreach run "go to wikipedia and search for AI"
    Resume:  blackreach run --resume 42
    """
    global _active_agent
    from blackreach.agent import Agent, AgentConfig
    from blackreach.llm import LLMConfig

    config = config_manager.load()

    # Use provided values or defaults
    provider = provider or config.default_provider
    model = model or getattr(config, provider).default_model
    headless = headless if headless is not None else config.headless
    max_steps = steps or config.max_steps

    # Check API key for non-local providers
    if provider != "ollama" and not config_manager.has_api_key(provider):
        console.print(f"[red]Error: No API key configured for {provider}[/red]")
        console.print(f"Run [cyan]blackreach config[/cyan] to set up API keys")
        sys.exit(1)

    # Handle resume
    if resume:
        console.print(Panel(
            f"[bold]Resuming Session:[/bold] #{resume}\n"
            f"[bold]Provider:[/bold] {provider}\n"
            f"[bold]Model:[/bold] {model}",
            title="[bold cyan]Blackreach Resume[/bold cyan]",
            border_style="cyan"
        ))

        try:
            llm_config = LLMConfig(
                provider=provider,
                model=model,
                api_key=config_manager.get_api_key(provider) if provider != "ollama" else None
            )

            agent_config = AgentConfig(
                max_steps=max_steps,
                headless=headless,
                download_dir=Path(config.download_dir)
            )

            agent = Agent(llm_config=llm_config, agent_config=agent_config)
            _active_agent = agent
            result = agent.resume(resume)

            # Show results
            _show_results(result)

        except SessionNotFoundError as e:
            console.print(f"[red]Error: {e}[/red]")
            console.print("Use [cyan]blackreach sessions[/cyan] to see resumable sessions")
            sys.exit(1)
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted - session state saved[/yellow]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            sys.exit(1)
        return

    # Regular run - goal is required
    if not goal:
        console.print("[red]Error: Goal is required (or use --resume)[/red]")
        console.print("Example: blackreach run \"find and download papers about AI\"")
        sys.exit(1)

    console.print(Panel(
        f"[bold]Goal:[/bold] {goal}\n"
        f"[bold]Provider:[/bold] {provider}\n"
        f"[bold]Model:[/bold] {model}\n"
        f"[bold]Headless:[/bold] {headless}",
        title="[bold cyan]Blackreach Agent[/bold cyan]",
        border_style="cyan"
    ))

    try:
        llm_config = LLMConfig(
            provider=provider,
            model=model,
            api_key=config_manager.get_api_key(provider) if provider != "ollama" else None
        )

        agent_config = AgentConfig(
            max_steps=max_steps,
            headless=headless,
            download_dir=Path(config.download_dir)
        )

        agent = Agent(llm_config=llm_config, agent_config=agent_config)
        _active_agent = agent
        result = agent.run(goal)

        # Show results
        _show_results(result)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted - session state saved for resume[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


def _show_results(result: dict):
    """Display agent run results."""
    status = "[bold green]Success[/bold green]" if result.get('success') else "[bold yellow]Incomplete[/bold yellow]"
    if result.get('paused'):
        status = "[bold blue]Paused[/bold blue]"

    console.print("\n")
    console.print(Panel(
        f"[bold]Status:[/bold] {status}\n"
        f"[bold]Downloads:[/bold] {len(result.get('downloads', []))}\n"
        f"[bold]Pages Visited:[/bold] {result.get('pages_visited', 0)}\n"
        f"[bold]Steps Taken:[/bold] {result.get('steps_taken', 0)}\n"
        f"[bold]Failures:[/bold] {result.get('failures', 0)}",
        title="[bold green]Results[/bold green]",
        border_style="green"
    ))

    if result.get('paused'):
        console.print(f"\n[dim]Resume with: blackreach run --resume {result.get('session_id')}[/dim]")


@cli.command()
def sessions():
    """List resumable sessions."""
    from blackreach.memory import PersistentMemory

    try:
        mem = PersistentMemory(Path("./memory.db"))
        resumable = mem.get_resumable_sessions()
        mem.close()
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not resumable:
        console.print("[dim]No resumable sessions found[/dim]")
        return

    table = Table(title="Resumable Sessions")
    table.add_column("ID", style="cyan")
    table.add_column("Goal", style="white")
    table.add_column("Step", style="yellow")
    table.add_column("Status", style="green")
    table.add_column("Saved", style="dim")

    for session in resumable:
        goal = session.get("goal", "")[:50]
        if len(session.get("goal", "")) > 50:
            goal += "..."
        table.add_row(
            str(session["session_id"]),
            goal,
            str(session.get("current_step", 0)),
            session.get("status", "unknown"),
            session.get("saved_at", "")[:19]
        )

    console.print(table)
    console.print("\n[dim]Resume with: blackreach run --resume <ID>[/dim]")


@cli.command()
def config():
    """Configure API keys and settings."""
    console.print(BANNER)
    console.print("\n[bold]Configuration Setup[/bold]\n")

    cfg = config_manager.load()

    # Show current config
    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Config File", str(CONFIG_FILE))
    table.add_row("Default Provider", cfg.default_provider)
    table.add_row("Default Model", config_manager.get_current_model())
    table.add_row("Headless", str(cfg.headless))
    table.add_row("Max Steps", str(cfg.max_steps))

    console.print(table)
    console.print()

    # API Keys status
    key_table = Table(title="API Keys")
    key_table.add_column("Provider", style="cyan")
    key_table.add_column("Status")
    key_table.add_column("Default Model")

    for provider in ["ollama", "openai", "anthropic", "google", "xai"]:
        if provider == "ollama":
            status = "[green]Local[/green]"
        elif config_manager.has_api_key(provider):
            status = "[green]✓ Configured[/green]"
        else:
            status = "[dim]Not set[/dim]"

        model = getattr(cfg, provider).default_model or "[dim]none[/dim]"
        key_table.add_row(provider, status, model)

    console.print(key_table)
    console.print()

    # Configuration menu
    while True:
        console.print("\n[bold]What would you like to configure?[/bold]")
        console.print("  [cyan]1[/cyan] - Set default provider")
        console.print("  [cyan]2[/cyan] - Set API key")
        console.print("  [cyan]3[/cyan] - Set default model")
        console.print("  [cyan]4[/cyan] - Toggle headless mode")
        console.print("  [cyan]5[/cyan] - Set max steps")
        console.print("  [cyan]q[/cyan] - Quit")

        choice = Prompt.ask("\nChoice", choices=["1", "2", "3", "4", "5", "q"], default="q")

        if choice == "q":
            break

        elif choice == "1":
            providers = list(AVAILABLE_MODELS.keys())
            console.print(f"\nAvailable: {', '.join(providers)}")
            provider = Prompt.ask("Default provider", choices=providers, default=cfg.default_provider)
            config_manager.set_default_provider(provider)
            console.print(f"[green]✓ Default provider: {provider}[/green]")

        elif choice == "2":
            provider = Prompt.ask("Provider", choices=["openai", "anthropic", "google", "xai"])
            key = Prompt.ask(f"API key for {provider}", password=True)
            config_manager.set_api_key(provider, key)
            console.print(f"[green]✓ API key saved for {provider}[/green]")

        elif choice == "3":
            provider = Prompt.ask("Provider", choices=list(AVAILABLE_MODELS.keys()))
            models = AVAILABLE_MODELS[provider]
            console.print(f"\nAvailable: {', '.join(models[:5])}...")
            model = Prompt.ask("Model", default=models[0])
            config_manager.set_default_model(provider, model)
            console.print(f"[green]✓ Default model for {provider}: {model}[/green]")

        elif choice == "4":
            cfg = config_manager.load()
            cfg.headless = not cfg.headless
            config_manager.save()
            console.print(f"[green]✓ Headless mode: {cfg.headless}[/green]")

        elif choice == "5":
            steps = Prompt.ask("Max steps", default=str(cfg.max_steps))
            cfg = config_manager.load()
            cfg.max_steps = int(steps)
            config_manager.save()
            console.print(f"[green]✓ Max steps: {steps}[/green]")


@cli.command()
@click.option('--provider', '-p', help='Show models for specific provider')
def models(provider: str):
    """List available models."""
    console.print("\n[bold]Available Models[/bold]\n")

    providers_to_show = [provider] if provider else AVAILABLE_MODELS.keys()

    for prov in providers_to_show:
        if prov not in AVAILABLE_MODELS:
            console.print(f"[red]Unknown provider: {prov}[/red]")
            continue

        table = Table(title=f"{prov.capitalize()}")
        table.add_column("Model", style="cyan")

        for model in AVAILABLE_MODELS[prov]:
            table.add_row(model)

        console.print(table)
        console.print()


@cli.command()
def status():
    """Show current status and memory stats."""
    config = config_manager.load()
    provider = config.default_provider
    model = getattr(config, provider).default_model

    # Get memory stats
    try:
        from blackreach.memory import PersistentMemory
        mem = PersistentMemory(Path("./memory.db"))
        stats = mem.get_stats()
        mem.close()
    except Exception:
        stats = {"total_sessions": 0, "total_downloads": 0, "total_visits": 0}

    console.print(Panel(
        f"[bold]Provider:[/bold] {provider}\n"
        f"[bold]Model:[/bold] {model}\n"
        f"[bold]Headless:[/bold] {config.headless}\n"
        f"[bold]Max Steps:[/bold] {config.max_steps}\n"
        f"\n[bold]Memory Stats:[/bold]\n"
        f"  Sessions: {stats.get('total_sessions', 0)}\n"
        f"  Downloads: {stats.get('total_downloads', 0)}\n"
        f"  Visits: {stats.get('total_visits', 0)}",
        title="[bold cyan]Status[/bold cyan]",
        border_style="cyan"
    ))


@cli.command()
@click.option('--reset', is_flag=True, help='Reset all settings to defaults')
def setup(reset: bool):
    """Run the setup wizard."""
    if reset:
        if Confirm.ask("[yellow]This will reset all settings. Continue?[/yellow]", default=False):
            # Remove config file
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
            console.print("[green]Settings reset.[/green]\n")

    run_first_time_setup()


@cli.command()
def doctor():
    """Check system requirements and diagnose issues."""
    console.print(BANNER)
    console.print("[bold]System Check[/bold]\n")

    checks = []

    # Check Python version
    import platform
    py_version = platform.python_version()
    py_ok = tuple(map(int, py_version.split('.')[:2])) >= (3, 10)
    checks.append(("Python >= 3.10", py_ok, py_version))

    # Check Playwright
    pw_installed = shutil.which("playwright") is not None
    checks.append(("Playwright CLI", pw_installed, "installed" if pw_installed else "not found"))

    # Check Playwright browsers
    browser_ok = check_playwright_browsers() if pw_installed else False
    checks.append(("Chromium browser", browser_ok, "installed" if browser_ok else "not installed"))

    # Check Ollama
    ollama_ok = check_ollama_running()
    checks.append(("Ollama running", ollama_ok, "running" if ollama_ok else "not running"))

    # Check config
    config_ok = CONFIG_FILE.exists()
    checks.append(("Config file", config_ok, str(CONFIG_FILE) if config_ok else "not created"))

    # Display results
    table = Table(title="System Status")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Details", style="dim")

    for name, ok, detail in checks:
        status = "[green]✓[/green]" if ok else "[red]✗[/red]"
        table.add_row(name, status, detail)

    console.print(table)

    # Recommendations
    console.print()
    if not browser_ok:
        console.print("[yellow]→ Run: playwright install chromium[/yellow]")
    if not ollama_ok:
        console.print("[yellow]→ Run: ollama serve[/yellow]")
    if not config_ok:
        console.print("[yellow]→ Run: blackreach setup[/yellow]")

    all_ok = all(ok for _, ok, _ in checks)
    if all_ok:
        console.print("\n[bold green]All checks passed![/bold green]")


def interactive_mode():
    """Interactive REPL mode with full polish."""
    global _active_agent
    from blackreach.agent import Agent, AgentConfig
    from blackreach.llm import LLMConfig
    from blackreach import ui

    # Print banner
    ui.print_banner()

    # Load config
    cfg = config_manager.load()
    provider = cfg.default_provider
    model = getattr(cfg, provider).default_model

    # Get memory stats
    try:
        from blackreach.memory import PersistentMemory
        mem = PersistentMemory(Path("./memory.db"))
        stats = mem.get_stats()
        mem.close()
    except Exception:
        stats = {"total_sessions": 0, "total_downloads": 0}

    # Welcome message
    ui.print_welcome(provider, model)

    # Create interactive prompt with history
    prompt = ui.InteractivePrompt()

    # Main loop
    while True:
        try:
            # Get input with history and completion
            goal = prompt.prompt(provider, model)

            if not goal.strip():
                continue

            cmd = goal.strip()
            cmd_lower = cmd.lower()

            # Slash commands (Claude Code style) with short aliases
            if cmd_lower in ['/quit', '/exit', '/q', 'quit', 'exit', 'q']:
                ui.print_info("Goodbye!")
                break

            elif cmd_lower in ['/help', '/h', 'help', '?']:
                ui.print_help()

            elif cmd_lower in ['/clear', '/cls', 'clear']:
                ui.clear_screen()
                ui.print_banner()
                ui.print_welcome(provider, model)

            elif cmd_lower in ['/history', 'history']:
                # Show recent history
                try:
                    history_lines = ui.HISTORY_FILE.read_text().strip().split('\n')[-10:]
                    console.print("\n[bold]Recent commands:[/bold]")
                    for i, line in enumerate(history_lines, 1):
                        console.print(f"  [dim]{i}.[/dim] {line}")
                    console.print()
                except Exception:
                    ui.print_info("No history yet")

            elif cmd_lower in ['/config', '/cfg', 'config']:
                config()
                # Reload config after changes
                cfg = config_manager.load()
                provider = cfg.default_provider
                model = getattr(cfg, provider).default_model

            elif cmd_lower in ['/models', 'models']:
                models(None)

            elif cmd_lower in ['/status', '/s', 'status']:
                status()

            elif cmd_lower.startswith('/plan '):
                # Preview a plan without executing
                goal = cmd[6:].strip()
                if not goal:
                    ui.print_error("Usage: /plan <goal>")
                else:
                    from blackreach.planner import Planner
                    from blackreach.llm import LLMConfig

                    with ui.spinner("Planning..."):
                        llm_config = LLMConfig(
                            provider=provider,
                            model=model,
                            api_key=config_manager.get_api_key(provider) if provider != "ollama" else None
                        )
                        planner = Planner(llm_config)

                        if planner.is_simple_goal(goal):
                            ui.print_info(f"Goal is simple - will run directly without planning")
                        else:
                            plan = planner.plan(goal)
                            if plan:
                                console.print(f"\n[bold]Plan Preview:[/bold]")
                                console.print(planner.format_plan(plan))
                                console.print(f"\n[dim]Run the goal directly to execute this plan[/dim]")

            elif cmd_lower in ['/logs', '/l', 'logs']:
                # Show recent session logs
                from blackreach.logging import get_recent_logs, read_log
                logs = get_recent_logs(5)
                if not logs:
                    ui.print_info("No logs yet")
                else:
                    console.print("\n[bold]Recent Sessions:[/bold]")
                    for log_file in logs:
                        entries = read_log(log_file)
                        if entries:
                            start = entries[0]
                            end = entries[-1] if entries[-1].get("event") == "session_end" else None
                            goal = start.get("data", {}).get("goal", "Unknown")[:50]
                            session_id = start.get("session_id", "?")
                            if end:
                                success = "[green]OK[/green]" if end.get("data", {}).get("success") else "[red]FAIL[/red]"
                                duration = end.get("data", {}).get("duration_seconds", "?")
                                console.print(f"  #{session_id}: {goal}... {success} ({duration}s)")
                            else:
                                console.print(f"  #{session_id}: {goal}... [yellow]incomplete[/yellow]")
                    console.print(f"\n  [dim]Logs: ~/.blackreach/logs/[/dim]")

            elif cmd_lower in ['/sessions', '/resume', 'sessions']:
                # Show resumable sessions
                from blackreach.memory import PersistentMemory
                try:
                    mem = PersistentMemory(Path("./memory.db"))
                    resumable = mem.get_resumable_sessions()
                    mem.close()

                    if not resumable:
                        ui.print_info("No resumable sessions")
                    else:
                        console.print("\n[bold]Resumable Sessions:[/bold]")
                        for session in resumable:
                            goal = session.get("goal", "")[:40]
                            if len(session.get("goal", "")) > 40:
                                goal += "..."
                            status_icon = "⏸" if session.get("status") == "paused" else "⚡"
                            console.print(f"  {status_icon} [cyan]#{session['session_id']}[/cyan]: {goal} (step {session.get('current_step', 0)})")
                        console.print("\n  [dim]Type /resume <ID> to continue a session[/dim]")
                except Exception as e:
                    ui.print_error(f"Failed to load sessions: {e}")

            elif cmd_lower.startswith('/resume '):
                # Resume a specific session
                try:
                    session_id = int(cmd.split(' ', 1)[1].strip())
                    from blackreach.agent import Agent, AgentConfig, AgentCallbacks
                    from blackreach.llm import LLMConfig

                    # Check API key
                    if provider != "ollama" and not config_manager.has_api_key(provider):
                        ui.print_error(f"No API key configured for {provider}")
                        continue

                    with ui.spinner(f"Resuming session #{session_id}..."):
                        llm_config = LLMConfig(
                            provider=provider,
                            model=model,
                            api_key=config_manager.get_api_key(provider) if provider != "ollama" else None
                        )

                        agent_config = AgentConfig(
                            max_steps=cfg.max_steps,
                            headless=cfg.headless,
                            download_dir=Path(cfg.download_dir)
                        )

                        agent = Agent(llm_config=llm_config, agent_config=agent_config)
                        _active_agent = agent

                    result = agent.resume(session_id, quiet=False)

                    # Show completion
                    if result.get('success'):
                        ui.print_success(f"Session completed! Downloaded {len(result.get('downloads', []))} files")
                    elif result.get('paused'):
                        ui.print_info(f"Session paused. Resume with: /resume {result.get('session_id')}")
                    else:
                        ui.print_warning("Session ended without completing goal")

                except SessionNotFoundError as e:
                    ui.print_error(str(e))
                except Exception as e:
                    ui.print_error(f"Resume failed: {e}")

            elif cmd_lower in ['/provider', '/p', 'provider']:
                # Interactive provider selection menu
                result = ui.show_provider_menu(provider)
                if result:
                    config_manager.set_default_provider(result)
                    provider = result
                    model = getattr(config_manager.load(), provider).default_model
                    ui.print_success(f"Switched to {provider} ({model})")

                    # Check API key for cloud providers
                    if provider != "ollama" and not config_manager.has_api_key(provider):
                        ui.print_warning(f"No API key configured for {provider}")
                        ui.print_info("Use /config to set your API key")

            elif cmd_lower in ['/model', '/m', 'model']:
                # Interactive model selection menu
                result = ui.show_model_menu(provider, model)
                if result:
                    new_provider, new_model = result
                    # Switch provider if needed
                    if new_provider != provider:
                        config_manager.set_default_provider(new_provider)
                        provider = new_provider
                    config_manager.set_default_model(provider, new_model)
                    model = new_model
                    ui.print_success(f"Switched to {provider} / {model}")

                    # Check API key for cloud providers
                    if provider != "ollama" and not config_manager.has_api_key(provider):
                        ui.print_warning(f"No API key configured for {provider}")
                        ui.print_info("Use /config to set your API key")

            elif cmd_lower.startswith('/provider ') or cmd_lower.startswith('provider '):
                # Direct provider switch: /provider ollama
                new_provider = cmd.split(' ', 1)[1].strip().lower()
                if new_provider in AVAILABLE_MODELS:
                    config_manager.set_default_provider(new_provider)
                    provider = new_provider
                    model = getattr(config_manager.load(), provider).default_model
                    ui.print_success(f"Switched to {provider} ({model})")
                else:
                    ui.print_error(f"Unknown provider: {new_provider}")
                    ui.print_info(f"Available: {', '.join(AVAILABLE_MODELS.keys())}")

            elif cmd_lower.startswith('/model ') or cmd_lower.startswith('model '):
                # Direct model switch: /model gpt-4o
                new_model = cmd.split(' ', 1)[1].strip()

                # Find which provider this model belongs to
                found_provider = None
                for prov, prov_models in AVAILABLE_MODELS.items():
                    if new_model in prov_models:
                        found_provider = prov
                        break

                if found_provider:
                    # Switch both provider and model
                    if found_provider != provider:
                        config_manager.set_default_provider(found_provider)
                        provider = found_provider
                    config_manager.set_default_model(provider, new_model)
                    model = new_model
                    ui.print_success(f"Switched to {provider} / {model}")

                    # Check API key
                    if provider != "ollama" and not config_manager.has_api_key(provider):
                        ui.print_warning(f"No API key configured for {provider}")
                        ui.print_info("Use /config to set your API key")
                else:
                    # Model not in known list, but allow it anyway (could be custom)
                    config_manager.set_default_model(provider, new_model)
                    model = new_model
                    ui.print_success(f"Model set to: {model} (on {provider})")
                    ui.print_warning(f"Note: '{new_model}' not in known models for {provider}")

            elif cmd.startswith('/'):
                # Unknown slash command
                ui.print_error(f"Unknown command: {cmd}")
                ui.print_info("Type /help for available commands")

            else:
                # Run the agent with the goal
                if provider != "ollama" and not config_manager.has_api_key(provider):
                    ui.print_error(f"No API key configured for {provider}")
                    ui.print_info("Use /config to set your API key, or /provider to switch")
                    continue

                # Run agent with progress display
                run_agent_with_ui(goal, provider, model, cfg)

        except KeyboardInterrupt:
            console.print()
            ui.print_info("Press Ctrl+C again to exit, or type a command")
            try:
                # Wait briefly for another Ctrl+C
                import time
                time.sleep(0.5)
            except KeyboardInterrupt:
                ui.print_info("Goodbye!")
                break
        except EOFError:
            ui.print_info("Goodbye!")
            break


def run_agent_with_ui(goal: str, provider: str, model: str, cfg):
    """Run agent with polished UI output."""
    global _active_agent
    from blackreach.agent import Agent, AgentConfig, AgentCallbacks
    from blackreach.llm import LLMConfig
    from blackreach import ui

    progress = ui.AgentProgress()

    # Create callbacks for UI updates
    def on_step(step, max_steps, phase, detail):
        progress.update_step(step, phase, detail)

    def on_action(action, args):
        progress.update_action(action, args)

    def on_observe(observation):
        ui.print_observation(observation)

    def on_think(thought):
        ui.print_thinking(thought)

    def on_error(error):
        progress.show_error(error)

    callbacks = AgentCallbacks(
        on_step=on_step,
        on_action=on_action,
        on_observe=on_observe,
        on_think=on_think,
        on_error=on_error,
    )

    try:
        # Show starting message
        with ui.spinner("Initializing browser..."):
            llm_config = LLMConfig(
                provider=provider,
                model=model,
                api_key=config_manager.get_api_key(provider) if provider != "ollama" else None
            )

            agent_config = AgentConfig(
                max_steps=cfg.max_steps,
                headless=cfg.headless,
                download_dir=Path(cfg.download_dir)
            )

            agent = Agent(
                llm_config=llm_config,
                agent_config=agent_config,
                callbacks=callbacks
            )
            _active_agent = agent

        # Start progress display
        progress.start(goal, cfg.max_steps)

        # Run the agent with callbacks and quiet mode
        result = agent.run(goal, quiet=True)

        # Show completion (use actual success flag from agent)
        progress.complete(
            success=result.get('success', False),
            result=result
        )

    except KeyboardInterrupt:
        console.print("\n")
        ui.print_warning("Agent interrupted")
    except Exception as e:
        ui.print_error(str(e))


def show_help():
    """Show help message."""
    from blackreach import ui
    ui.print_help()


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
