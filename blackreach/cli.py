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
from rich.text import Text
from rich.markup import escape
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from datetime import datetime
from pathlib import Path
import subprocess
import sys
import shutil
import signal
import atexit
import time
import os

from blackreach import __version__
from blackreach.config import config_manager, AVAILABLE_MODELS, CONFIG_FILE, validate_config, validate_for_run
from blackreach.exceptions import BlackreachError, SessionNotFoundError
from blackreach.logging import LogLevel
from blackreach.run_status import describe_run

# Global reference to active agent for cleanup
_active_agent = None

def _cleanup_keyboard():
    """Release all keyboard keys on exit to prevent stuck keys."""
    global _active_agent
    if _active_agent and hasattr(_active_agent, 'hand') and _active_agent.hand:
        try:
            _active_agent.hand._release_all_keys()
        except Exception:  # Best-effort cleanup
            pass

def _signal_handler(signum, frame):
    """Let the agent checkpoint on interruption instead of exiting as a success."""
    _cleanup_keyboard()
    raise KeyboardInterrupt

# Register cleanup handlers - but not during testing to avoid interfering with pytest
def _is_running_under_pytest():
    """Check if we're running under pytest."""
    return "pytest" in sys.modules or "_pytest" in sys.modules

atexit.register(_cleanup_keyboard)

# Only register signal handlers when not under pytest
if not _is_running_under_pytest():
    signal.signal(signal.SIGTERM, _signal_handler)
    # SIGINT is handled by KeyboardInterrupt, but register anyway for safety
    try:
        signal.signal(signal.SIGINT, _signal_handler)
    except ValueError:
        pass  # Can't set SIGINT handler in some contexts

console = Console()


def _make_banner():
    v = f"v{__version__}"
    label = f"Autonomous Browser Agent   {v}"
    return f"""[bold cyan]
╔══════════════════════════════════════════════════════════╗
║   ██████╗ ██╗      █████╗  ██████╗██╗  ██╗              ║
║   ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝              ║
║   ██████╔╝██║     ███████║██║     █████╔╝               ║
║   ██╔══██╗██║     ██╔══██║██║     ██╔═██╗               ║
║   ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗              ║
║   ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝              ║
║                                                          ║
║   [white]{label:<55}[/white]║
╚══════════════════════════════════════════════════════════╝[/bold cyan]
"""

BANNER = _make_banner()


def is_first_run() -> bool:
    """Check if this is the first time running Blackreach."""
    return not CONFIG_FILE.exists()


def check_playwright_browsers(browser_type: str = "chromium") -> bool:
    """Check the selected SDK revision's executable, without launching a browser."""
    if browser_type not in ("chromium", "firefox", "webkit"):
        return False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as runtime:
            executable = Path(getattr(runtime, browser_type).executable_path)
            return executable.is_file() and os.access(executable, os.X_OK)
    except Exception:
        # Diagnostic only: driver startup and missing-library errors mean not ready.
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
                [sys.executable, "-m", "playwright", "install", "chromium"],
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
    except (ImportError, OSError):
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

    Give it a goal, watch it browse. Blackreach uses AI to autonomously
    navigate websites, search for content, and download files.

    \b
    Quick start:
      blackreach                              Interactive mode
      blackreach run "search for X on Y"      Run with a goal
      blackreach setup                        First-time setup
      blackreach doctor                       Check system health
    """
    if is_first_run() and ctx.invoked_subcommand is None:
        run_first_time_setup()
        return

    if ctx.invoked_subcommand is None:
        interactive_mode()


def _make_llm_config(provider: str, model: str, cfg=None):
    """Pass saved provider settings through every CLI and interactive route."""
    from blackreach.llm import LLMConfig
    cfg = cfg or config_manager.load()
    provider_cfg = getattr(cfg, provider)
    return LLMConfig(
        provider=provider, model=model,
        api_key=config_manager.get_api_key(provider) if provider != "ollama" else None,
        api_base=provider_cfg.base_url or None,
        **provider_cfg.llm_settings(),
    )


def _run_exit_code(result: dict) -> int:
    if result.get('success'):
        return 0
    if result.get('status') == 'interrupted':
        return 130
    return 1 if result.get('status') == 'error' else 2


@cli.command()
@click.argument('goal', required=False)
@click.option('--provider', '-p', type=click.Choice(['ollama', 'openai', 'anthropic', 'google', 'xai']))
@click.option('--model', '-m', help='Model ID to use (account access is separate).')
@click.option('--headless/--no-headless', default=None, help='Run browser headless')
@click.option('--browser', '-b', type=click.Choice(['chromium', 'firefox', 'webkit']), help='Browser to use')
@click.option('--steps', '-s', type=click.IntRange(min=1), help='Total decision budget, including previous decisions on resume')
@click.option('--resume', '-r', type=click.IntRange(min=1), help='Resume a saved session by ID')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--validate', 'do_validate', is_flag=True, help='Validate config before running')
@click.option('--cdp', is_flag=True, help='Use persistent Chrome via CDP (fast reconnects)')
@click.option('--json', 'json_output', is_flag=True, help='Print a structured result; exit 0 success, 1 error, 2 stopped, 130 interrupted')
def run(goal: str, provider: str, model: str, headless: bool, browser: str, steps: int,
        resume: int, verbose: bool, do_validate: bool, cdp: bool, json_output: bool = False):
    """Run a goal or resume saved progress with an explicit decision budget."""
    global _active_agent
    from blackreach.agent import Agent, AgentConfig
    import json

    result = None
    try:
        config = config_manager.load()
        provider = provider or config.default_provider
        if provider not in AVAILABLE_MODELS:
            raise click.ClickException(f"Unsupported provider: {provider}")
        model = model or getattr(config, provider).default_model
        if not goal and not resume:
            raise click.ClickException('Goal is required (or use --resume).')
        if do_validate:
            validation = validate_for_run(provider, model)
            if not validation.valid:
                raise click.ClickException('Configuration validation failed: ' + '; '.join(validation.errors))
            if not json_output:
                for warning in validation.warnings:
                    console.print(Text('Warning: ' + warning, style='yellow'))
        if provider != 'ollama' and not config_manager.has_api_key(provider):
            raise click.ClickException(f'No API key configured for {provider}. Use blackreach config or its provider environment variable.')
        if not json_output:
            console.print(Panel(Text(f"{'Session: #' + str(resume) if resume else 'Goal: ' + goal}\nProvider: {provider}\nModel: {model}"),
                                title='Blackreach', border_style='cyan'))
        agent = Agent(
            llm_config=_make_llm_config(provider, model, config),
            agent_config=AgentConfig(
                max_steps=steps if steps is not None else config.max_steps,
                headless=headless if headless is not None else config.headless,
                download_dir=Path(config.download_dir), browser_type=browser or config.browser_type,
                use_cdp=cdp, keep_browser_alive=cdp,
            ),
        )
        _active_agent = agent
        if resume:
            result = agent.resume(resume, quiet=json_output, max_steps=steps)
        else:
            result = agent.run(goal, quiet=json_output)
    except KeyboardInterrupt:
        result = {'goal': goal, 'success': False, 'status': 'interrupted',
                  'stop_reason': 'interrupted', 'resumable': False,
                  'error': 'Interrupted before a checkpoint was confirmed.'}
    except Exception as exc:
        # Never expose arbitrary request bodies or SDK exception text here.
        safe = str(exc) if isinstance(exc, (BlackreachError, click.ClickException)) else f'{type(exc).__name__}: run could not start; use blackreach doctor.'
        result = {'goal': goal, 'success': False, 'status': 'error',
                  'stop_reason': 'startup_error', 'error': safe, 'resumable': False}
    finally:
        _active_agent = None
    if json_output:
        click.echo(json.dumps(result, ensure_ascii=False, default=str))
    else:
        _show_results(result)
    raise click.exceptions.Exit(_run_exit_code(result))


# ---------------------------------------------------------------------------
# Daemon commands
# ---------------------------------------------------------------------------
@cli.group(name="daemon")
def daemon_group():
    """Manage the persistent Chrome daemon (CDP mode)."""
    pass


@daemon_group.command(name="start")
@click.option('--headless', is_flag=True, help='Start Chrome headless')
@click.option('--port', '-p', type=int, default=9222, help='CDP port (default: 9222)')
def daemon_start(headless: bool, port: int):
    """Start the persistent Chrome daemon."""
    from blackreach.browser_cdp import _find_chromium, _port_open, _cdp_responding
    import json, urllib.request

    if _cdp_responding(timeout=2.0):
        # Already running — just print
        ws_url = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2).read())["webSocketDebuggerUrl"]
        console.print(f"[bold green]✓ Chrome daemon already running[/bold green]")
        console.print(f"  Port: [cyan]{port}[/cyan]")
        console.print(f"  WS:   [dim]{ws_url}[/dim]")
        return

    chrome = _find_chromium()
    data_dir = Path.home() / ".config/blackreach-chrome"
    data_dir.mkdir(parents=True, exist_ok=True)
    pid_file = data_dir / f"chrome.pid.{port}"

    args = [
        chrome,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={data_dir}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-background-networking",
        "--disable-breakpad",
        "--disable-default-apps",
        "--disable-sync",
        "--metrics-recording-only",
        "--enable-automation",
        "--password-store=basic",
        "--use-mock-keychain",
        "--force-color-profile=srgb",
    ]
    if headless:
        args.append("--headless=new")

    # Start detached — survives parent exit
    env = os.environ.copy()
    env.pop("LD_PRELOAD", None)
    proc = subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
        close_fds=True,
        env=env,
    )

    # Wait for CDP to come up
    deadline = time.time() + 30
    while time.time() < deadline:
        if _cdp_responding(timeout=1.0):
            break
        time.sleep(0.3)
    else:
        proc.terminate()
        console.print("[red]Chrome did not expose CDP within 30s[/red]")
        sys.exit(1)

    # Save PID for later kill
    pid_file.write_text(str(proc.pid))

    ws_url = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2).read())["webSocketDebuggerUrl"]
    console.print(f"[bold green]✓ Chrome daemon started[/bold green]")
    console.print(f"  Port: [cyan]{port}[/cyan]")
    console.print(f"  WS:   [dim]{ws_url}[/dim]")
    console.print(f"\n[dim]Use [cyan]blackreach run --cdp \"your goal\"[/cyan] to connect[/dim]")


@daemon_group.command(name="stop")
@click.option('--port', '-p', type=int, default=9222, help='CDP port (default: 9222)')
def daemon_stop(port: int):
    """Stop the persistent Chrome daemon."""
    data_dir = Path.home() / ".config/blackreach-chrome"
    pid_file = data_dir / f"chrome.pid.{port}"

    killed = False
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            killed = True
            for _ in range(20):  # wait up to 2s
                try:
                    os.kill(pid, 0)
                    time.sleep(0.1)
                except ProcessLookupError:
                    break
            pid_file.unlink(missing_ok=True)
        except (ProcessLookupError, ValueError):
            pid_file.unlink(missing_ok=True)

    # Fallback: kill by port
    import shutil
    lsof = shutil.which("lsof")
    if lsof:
        try:
            out = subprocess.check_output([lsof, "-ti", f":{port}"], text=True, stderr=subprocess.DEVNULL)
            for p in out.strip().split("\n"):
                try:
                    os.kill(int(p), signal.SIGKILL)
                    killed = True
                except (ProcessLookupError, ValueError):
                    pass
        except subprocess.CalledProcessError:
            pass

    if killed:
        console.print(f"[bold green]✓ Chrome daemon stopped[/bold green]")
    else:
        console.print(f"[yellow]No daemon found on port {port}[/yellow]")


@daemon_group.command(name="status")
@click.option('--port', '-p', type=int, default=9222, help='CDP port (default: 9222)')
def daemon_status_cmd(port: int):
    """Check Chrome daemon status."""
    from blackreach.browser_cdp import _cdp_responding
    import json, urllib.request

    if _cdp_responding(timeout=2.0):
        ws_url = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2).read())["webSocketDebuggerUrl"]
        console.print(f"[bold green]● Chrome daemon running[/bold green]")
        console.print(f"  Port:  [cyan]{port}[/cyan]")
        console.print(f"  WS:    [dim]{ws_url}[/dim]")
        console.print(f"\n[dim]Use [cyan]blackreach run --cdp \"your goal\"[/cyan] to connect[/dim]")
    else:
        console.print(f"[red]● Chrome daemon not running[/red]")
        console.print(f"  Port:  [dim]{port}[/dim]")
        console.print(f"\n[dim]Start with: [cyan]blackreach daemon start[/cyan][/dim]")


# ---------------------------------------------------------------------------
# Scancode command — preview adaptive routing decisions
# ---------------------------------------------------------------------------
@cli.command(name="scancode")
@click.argument('url')
@click.option('--refresh', is_flag=True, help='Force fresh scan (bypass cache)')
@click.option('--verbose', '-v', is_flag=True, help='Show full details')
def scancode_cmd(url: str, refresh: bool, verbose: bool):
    """Scan a URL and preview routing decision.

    Shows the browser confidence score, selected mode, and estimated cost
    without actually navigating. Useful for testing the adaptive router.

    \\b
    Examples:
        blackreach scancode https://wikipedia.org/wiki/Python
        blackreach scancode https://wikipedia.org/wiki/Python --verbose
        blackreach scancode https://wikipedia.org/wiki/Python --refresh
    """
    from blackreach.adaptive_browser import get_router, BrowserMode

    plan = get_router().plan_for(url, force_refresh=refresh)

    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text

    mode_colours = {
        BrowserMode.LIGHTWEIGHT: "green",
        BrowserMode.HEADLESS: "yellow",
        BrowserMode.FULL_STEALTH: "red",
    }
    colour = mode_colours.get(plan.mode, "white")

    console.print(Panel(
        f"[bold {colour}]{plan.mode.value.upper()}[/bold {colour}]   "
        f"confidence={plan.confidence:.2f}   "
        f"est_cost={plan.estimated_cost_ms}ms",
        title="[bold]Routing Decision[/bold]",
        subtitle=f"[dim]{url[:80]}[/dim]",
        border_style=colour,
    ))

    if verbose:
        table = Table(title="Analysis Details")
        table.add_column("Attribute", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")

        table.add_row("Mode", plan.mode.value)
        table.add_row("Confidence", f"{plan.confidence:.2f}")
        table.add_row("Estimated Cost", f"{plan.estimated_cost_ms}ms")
        table.add_row("JS Required", str(plan.js_required))
        table.add_row("Captcha Expected", str(plan.captcha_expected))
        table.add_row("Proxy Recommended", str(plan.proxy_recommended))

        if plan.reasons:
            table.add_row("Reasons", "\n".join(plan.reasons[:5]))
        if plan.suggested_headers:
            hdrs = "\n".join(f"{k}: {v[:50]}" for k, v in plan.suggested_headers.items())
            table.add_row("Suggested Headers", hdrs)

        console.print(table)
    else:
        reasons = plan.reasons[:3]
        if reasons:
            console.print(f"[dim]Reasons: {', '.join(reasons)}[/dim]")
        console.print(f"\n[dim]Use --verbose for full details[/dim]")


def _show_results(result: dict):
    """Display agent run results."""
    description = describe_run(result)
    color = description['color']
    console.print("\n")

    # Show result text if the agent produced one (research/summarization tasks)
    result_text = result.get('result') or result.get('output') or result.get('summary')
    if result_text and isinstance(result_text, str) and result_text.strip():
        console.print(Panel(
            Text(result_text.strip()),
            title="[bold cyan]Result[/bold cyan]",
            border_style="cyan"
        ))
        console.print("\n")

    lines = (
        f"[bold]Status:[/bold] [{color}]{description['label']}[/{color}]\n"
        f"[bold]Reason:[/bold] {escape(description['reason'])}\n"
        f"[bold]Downloads:[/bold] {len(result.get('downloads', []))}\n"
        f"[bold]Pages Visited:[/bold] {result.get('pages_visited', 0)}\n"
        f"[bold]Decisions:[/bold] {result.get('steps_taken', 0)}\n"
        f"[bold]Actions:[/bold] {result.get('actions_taken', 0)}\n"
        f"[bold]Failures:[/bold] {result.get('failures', 0)}"
    )
    if description['error']:
        lines += f"\n[bold]Error:[/bold] {escape(description['error'])}"
    if result.get('session_id') is not None:
        lines += f"\n[bold]Session:[/bold] #{result['session_id']}"
    console.print(Panel(lines, title="Results", border_style=color))
    if description['hint']:
        console.print(Text(description['hint'], style="dim"))


@cli.command(name="resumable")
def list_resumable():
    """List sessions that can be resumed."""
    from blackreach.memory import PersistentMemory

    try:
        mem = PersistentMemory(Path("./memory.db"))
        resumable = mem.get_resumable_sessions()
        mem.close()
    except (OSError, BlackreachError) as e:
        console.print(f"[red]Error: {e}[/red]")
        return

    if not resumable:
        console.print("[dim]No resumable sessions found[/dim]")
        console.print("[dim]Sessions can be paused with Ctrl+C during execution[/dim]")
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
    console.print("[dim]Known model IDs; API account access is not checked. Custom IDs work with --model or /model.[/dim]")

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

    try:
        from blackreach.memory import PersistentMemory
        mem = PersistentMemory(Path("./memory.db"))
        stats = mem.get_stats()
        mem.close()
    except Exception:  # Best-effort stats display
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
            if CONFIG_FILE.exists():
                CONFIG_FILE.unlink()
            console.print("[green]Settings reset.[/green]\n")

    run_first_time_setup()


@cli.command()
def version():
    """Show version information."""
    import platform
    console.print(f"[bold cyan]Blackreach[/bold cyan] v{__version__}")
    console.print(f"[dim]Python {platform.python_version()} on {platform.system()} {platform.release()}[/dim]")


@cli.command()
@click.option('--force', '-f', is_flag=True, help='Force reinstall even if up to date')
def update(force: bool):
    """Update Blackreach to the latest version from source."""
    import subprocess
    from pathlib import Path

    console.print(BANNER)
    console.print("[bold]Blackreach Updater[/bold]\n")

    # Find the project root (where pyproject.toml is)
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent  # blackreach/cli.py -> blackreach -> project root

    pyproject = project_root / "pyproject.toml"
    if not pyproject.exists():
        console.print("[red]Error: Could not find project root (pyproject.toml)[/red]")
        console.print(f"[dim]Searched in: {project_root}[/dim]")
        return

    console.print(f"[dim]Project root: {project_root}[/dim]")
    console.print(f"[cyan]Current version:[/cyan] {__version__}\n")

    git_dir = project_root / ".git"
    if git_dir.exists():
        console.print("[yellow]Pulling latest changes...[/yellow]")
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=project_root,
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                if "Already up to date" in result.stdout:
                    console.print("[green]Already up to date[/green]")
                    if not force:
                        console.print("[dim]Use --force to reinstall anyway[/dim]")
                        return
                else:
                    console.print(f"[green]{result.stdout.strip()}[/green]")
            else:
                console.print(f"[yellow]Git pull warning: {result.stderr.strip()}[/yellow]")
        except (subprocess.SubprocessError, OSError) as e:
            console.print(f"[yellow]Git pull skipped: {e}[/yellow]")

    # Reinstall package
    console.print("\n[yellow]Reinstalling package...[/yellow]")
    try:
        result = subprocess.run(
            ["pip", "install", "-e", ".", "--quiet"],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=120
        )
        if result.returncode == 0:
            console.print("[green]Package reinstalled successfully[/green]")
        else:
            console.print(f"[red]Install error: {result.stderr.strip()}[/red]")
            return
    except (subprocess.SubprocessError, OSError) as e:
        console.print(f"[red]Install failed: {e}[/red]")
        return

    console.print("\n[bold green]Update complete![/bold green]")
    console.print("\n[yellow]To use the new version, run:[/yellow]")
    console.print("  [cyan]hash -r[/cyan]  (clear shell cache)")
    console.print("  [dim]or just open a new terminal[/dim]")


@cli.command()
@click.option('--fix', is_flag=True, help='Attempt to fix issues automatically')
def validate(fix: bool):
    """Validate configuration and show any issues."""
    console.print(BANNER)
    console.print("[bold]Configuration Validation[/bold]\n")

    config = config_manager.load()
    result = validate_config(config)
    table = Table(title="Current Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_column("Status")

    # Provider
    provider_ok = config.default_provider in AVAILABLE_MODELS
    table.add_row(
        "Provider",
        config.default_provider,
        "[green]OK[/green]" if provider_ok else "[red]Invalid[/red]"
    )

    # Model
    model = getattr(config, config.default_provider).default_model if hasattr(config, config.default_provider) else ""
    known_models = AVAILABLE_MODELS.get(config.default_provider, [])
    model_ok = model in known_models or model == ""
    table.add_row(
        "Model",
        model or "[dim]not set[/dim]",
        "[green]OK[/green]" if model_ok else "[yellow]Custom[/yellow]"
    )

    # API Key (for cloud providers)
    if config.default_provider != "ollama":
        has_key = config_manager.has_api_key(config.default_provider)
        table.add_row(
            "API Key",
            "[green]Set[/green]" if has_key else "[red]Missing[/red]",
            "[green]OK[/green]" if has_key else "[red]Required[/red]"
        )

    # Browser
    valid_browsers = ["chromium", "firefox", "webkit"]
    browser_ok = config.browser_type in valid_browsers
    table.add_row(
        "Browser",
        config.browser_type,
        "[green]OK[/green]" if browser_ok else "[red]Invalid[/red]"
    )

    # Max Steps
    steps_ok = 1 <= config.max_steps <= 1000
    table.add_row(
        "Max Steps",
        str(config.max_steps),
        "[green]OK[/green]" if steps_ok else "[red]Out of range[/red]"
    )

    # Download Dir
    from pathlib import Path
    download_path = Path(config.download_dir)
    try:
        download_path.mkdir(parents=True, exist_ok=True)
        dir_ok = True
    except OSError:
        dir_ok = False
    table.add_row(
        "Download Dir",
        config.download_dir,
        "[green]OK[/green]" if dir_ok else "[red]Cannot create[/red]"
    )

    console.print(table)
    console.print()

    # Show validation results
    if result.errors:
        console.print("[bold red]Errors:[/bold red]")
        for error in result.errors:
            console.print(f"  [red]X[/red] {error}")
        console.print()

    if result.warnings:
        console.print("[bold yellow]Warnings:[/bold yellow]")
        for warning in result.warnings:
            console.print(f"  [yellow]![/yellow] {warning}")
        console.print()

    if result.valid:
        if result.warnings:
            console.print("[green]Configuration is valid (with warnings).[/green]")
        else:
            console.print("[bold green]Configuration is valid![/bold green]")
    else:
        console.print("[red]Configuration has errors. Run 'blackreach config' to fix.[/red]")

    # Attempt auto-fix if requested
    if fix and not result.valid:
        console.print("\n[bold]Attempting to fix issues...[/bold]")
        fixed_count = 0

        # Fix invalid browser
        if config.browser_type not in valid_browsers:
            config.browser_type = "chromium"
            console.print("  [green]Fixed:[/green] Set browser to chromium")
            fixed_count += 1

        # Fix invalid max_steps
        if config.max_steps < 1:
            config.max_steps = 30
            console.print("  [green]Fixed:[/green] Set max_steps to 30")
            fixed_count += 1
        elif config.max_steps > 1000:
            config.max_steps = 100
            console.print("  [green]Fixed:[/green] Set max_steps to 100")
            fixed_count += 1

        if fixed_count > 0:
            config_manager.save()
            console.print(f"\n[green]Fixed {fixed_count} issue(s). Configuration saved.[/green]")
        else:
            console.print("\n[dim]No automatic fixes available for remaining issues.[/dim]")


@cli.command()
@click.option('--domain', '-d', help='Filter by domain')
def actions(domain: str):
    """Show action tracking statistics."""
    from blackreach.memory import PersistentMemory
    from blackreach.action_tracker import ActionTracker

    console.print(BANNER)
    console.print("[bold]Action Tracking Statistics[/bold]\n")

    memory = PersistentMemory()
    tracker = ActionTracker(memory)

    stats = tracker.get_stats_summary()

    # Overview
    overview = Table(title="Overview")
    overview.add_column("Metric", style="cyan")
    overview.add_column("Value", justify="right")

    overview.add_row("Total Tracked Actions", str(stats["total_tracked_actions"]))
    overview.add_row("Total Successes", str(stats["total_successes"]))
    overview.add_row("Overall Success Rate", f"{stats['overall_success_rate']:.1%}")
    overview.add_row("Unique Action Patterns", str(stats["unique_action_patterns"]))
    overview.add_row("Domains Tracked", str(stats["domains_tracked"]))

    console.print(overview)
    console.print()

    # Problem actions (low success rate)
    if stats.get("problem_actions"):
        problems = Table(title="Problem Actions (Low Success Rate)")
        problems.add_column("Domain", style="cyan")
        problems.add_column("Action")
        problems.add_column("Target", max_width=30)
        problems.add_column("Success", justify="right")
        problems.add_column("Failures", justify="right")

        for pa in stats["problem_actions"][:10]:
            problems.add_row(
                pa["domain"][:20] or "-",
                pa["action"],
                pa["target"][:30] if pa["target"] else "-",
                f"{pa['success_rate']:.0%}",
                str(pa["failures"])
            )

        console.print(problems)
        console.print()

    # Domain-specific stats if requested
    if domain:
        domain_stats = tracker.get_domain_summary(domain)
        if domain_stats:
            dom_table = Table(title=f"Actions on {domain}")
            dom_table.add_column("Action Type", style="cyan")
            dom_table.add_column("Success Rate", justify="right")
            dom_table.add_column("Total", justify="right")

            for action_type, data in domain_stats.items():
                dom_table.add_row(
                    action_type,
                    f"{data['success_rate']:.0%}",
                    str(data['total_actions'])
                )

            console.print(dom_table)
            console.print()

            # Good selectors for domain
            good_selectors = tracker.get_good_selectors(domain)
            if good_selectors:
                console.print(f"[bold]Best selectors for {domain}:[/bold]")
                for sel in good_selectors[:5]:
                    console.print(f"  [green]✓[/green] {sel}")
                console.print()


@cli.command()
@click.option('--type', '-t', 'content_type', help='Filter by content type')
def sources(content_type: str):
    """Show content source health and availability."""
    from blackreach.source_manager import get_source_manager, SourceStatus

    console.print(BANNER)
    console.print("[bold]Content Source Status[/bold]\n")

    manager = get_source_manager()
    all_status = manager.get_all_status()

    if not all_status:
        console.print("[dim]No source activity recorded yet.[/dim]")
        console.print("\nRun 'blackreach health' to check source availability.")
        return

    # Status table
    table = Table(title="Source Health")
    table.add_column("Domain", style="cyan", max_width=30)
    table.add_column("Status")
    table.add_column("Success Rate", justify="right")
    table.add_column("Success", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Available")

    status_colors = {
        "healthy": "green",
        "degraded": "yellow",
        "rate_limited": "yellow",
        "blocked": "red",
        "down": "red",
        "unknown": "dim",
    }

    for domain, info in sorted(all_status.items(), key=lambda x: x[1]["success_rate"], reverse=True):
        status = info["status"]
        color = status_colors.get(status, "white")
        status_display = f"[{color}]{status}[/{color}]"

        available = "[green]Yes[/green]" if info["available"] else "[red]No[/red]"

        table.add_row(
            domain[:30],
            status_display,
            f"{info['success_rate']:.0%}",
            str(info["success_count"]),
            str(info["failure_count"]),
            available
        )

    console.print(table)

    # Session summary
    summary = manager.get_session_summary()
    if summary["sources_used"] > 0:
        console.print(f"\n[bold]Session:[/bold] {summary['sources_used']} sources used, {summary['failovers']} failovers")


@cli.command()
@click.option('--browser', type=click.Choice(['chromium', 'firefox', 'webkit']), default='chromium')
@click.option('--offline', is_flag=True, help='Check installed files only; do not contact model services')
@click.option('--json', 'json_output', is_flag=True, help='Print diagnostic data without terminal formatting')
def doctor(browser: str = 'chromium', offline: bool = False, json_output: bool = False):
    """Check this Python environment. A present executable is not a launch test."""
    import json
    import platform
    import importlib.util

    checks = []
    py_version = platform.python_version()
    checks.append(('Python >= 3.10', tuple(map(int, py_version.split('.')[:2])) >= (3, 10), py_version))
    pw_installed = importlib.util.find_spec('playwright') is not None
    checks.append(('Playwright SDK', pw_installed, 'installed in this environment' if pw_installed else 'missing'))
    browser_ok = check_playwright_browsers(browser) if pw_installed else False
    checks.append((f'{browser} executable', browser_ok,
                   'present and executable; launch not tested' if browser_ok else 'required SDK revision is missing or not executable'))
    config_ok = CONFIG_FILE.exists()
    checks.append(('Config file', config_ok, str(CONFIG_FILE) if config_ok else 'not created; defaults available'))
    provider = config_manager.load().default_provider
    ollama_ok = None
    if provider == 'ollama' and not offline:
        ollama_ok = check_ollama_running()
        checks.append(('Ollama running', ollama_ok, 'running' if ollama_ok else 'not reachable'))
    recommendations = []
    if not browser_ok:
        recommendations.append(f'{sys.executable} -m playwright install {browser}')
    if ollama_ok is False:
        recommendations.append('Start the configured Ollama service, or choose a cloud provider with blackreach config.')
    if not config_ok:
        recommendations.append('blackreach setup')
    payload = {'python': sys.executable, 'provider': provider, 'browser': browser,
               'offline': offline, 'provider_access_tested': False, 'browser_launch_tested': False,
               'checks': [{'name': name, 'ok': ok, 'detail': str(detail)} for name, ok, detail in checks],
               'recommendations': recommendations}
    if json_output:
        click.echo(json.dumps(payload))
        return
    console.print(BANNER)
    console.print('[bold]System Check[/bold]')
    table = Table(title='System Status')
    table.add_column('Check', style='cyan')
    table.add_column('Status')
    table.add_column('Details', style='dim')
    for name, ok, detail in checks:
        table.add_row(name, '[green]✓[/green]' if ok else '[yellow]![/yellow]', Text(str(detail)))
    console.print(table)
    for instruction in recommendations:
        console.print(Text('→ ' + instruction, style='yellow'))
    console.print(Text('Provider account access and browser launch are not tested by doctor.', style='dim'))


@cli.command()
def stats():
    """Show agent statistics and performance metrics."""
    from blackreach.memory import PersistentMemory

    console.print(BANNER)
    console.print("[bold]Agent Statistics[/bold]\n")

    memory = PersistentMemory()
    stats = memory.get_detailed_stats()

    # Overview table
    overview = Table(title="Overview")
    overview.add_column("Metric", style="cyan")
    overview.add_column("Value", justify="right")

    overview.add_row("Total Sessions", str(stats["total_sessions"]))
    overview.add_row("Completed Sessions", str(stats.get("completed_sessions", 0)))
    overview.add_row("Success Rate", f"{stats.get('session_success_rate', 0)}%")
    overview.add_row("Total Downloads", str(stats["total_downloads"]))
    overview.add_row("Total Downloaded", stats.get("total_downloaded_size", "0 bytes"))
    overview.add_row("Total Visits", str(stats["total_visits"]))
    overview.add_row("Known Domains", str(stats["known_domains"]))

    console.print(overview)
    console.print()

    # Performance metrics
    perf = Table(title="Performance")
    perf.add_column("Metric", style="cyan")
    perf.add_column("Value", justify="right")

    perf.add_row("Avg Steps/Session", str(stats.get("avg_steps_per_session", 0)))
    perf.add_row("Avg Downloads/Session", str(stats.get("avg_downloads_per_session", 0)))
    perf.add_row("Total Failures", str(stats["total_failures"]))

    console.print(perf)
    console.print()

    # Top sources
    if stats.get("top_sources"):
        sources = Table(title="Top Download Sources")
        sources.add_column("Site", style="cyan")
        sources.add_column("Downloads", justify="right")

        for src in stats["top_sources"]:
            sources.add_row(src["site"], str(src["count"]))

        console.print(sources)
        console.print()

    # Recent sessions
    if stats.get("recent_sessions"):
        recent = Table(title="Recent Sessions")
        recent.add_column("Goal", style="cyan", max_width=40)
        recent.add_column("Status")
        recent.add_column("Steps", justify="right")
        recent.add_column("Downloads", justify="right")

        for session in stats["recent_sessions"]:
            status = "[green]✓[/green]" if session["success"] else "[red]✗[/red]"
            recent.add_row(
                session["goal"],
                status,
                str(session["steps"]),
                str(session["downloads"])
            )

        console.print(recent)

    console.print(f"\n[dim]Database: {stats['db_path']}[/dim]")


@cli.command()
@click.option('--type', '-t', 'content_type', help='Filter by content type (e.g., ebook, wallpaper)')
@click.option('--timeout', default=5.0, help='Request timeout in seconds')
def health(content_type: str, timeout: float):
    """Check health of content sources."""
    from blackreach.knowledge import check_sources_health

    console.print(BANNER)
    console.print("[bold]Content Source Health Check[/bold]\n")

    content_types = [content_type] if content_type else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Checking sources...", total=None)
        health_data = check_sources_health(content_types, timeout)
        progress.remove_task(task)

    if not health_data:
        console.print("[yellow]No sources found for the specified content type.[/yellow]")
        return

    # Create table
    table = Table(title=f"Source Health ({len(health_data)} sources)")
    table.add_column("Source", style="cyan")
    table.add_column("Status")
    table.add_column("Priority", justify="right")
    table.add_column("Types", style="dim")

    online_count = 0
    for name, data in sorted(health_data.items(), key=lambda x: x[1]["priority"], reverse=True):
        if data["reachable"]:
            status = "[green]Online[/green]"
            if data.get("working_mirror"):
                status += " [dim](mirror)[/dim]"
            online_count += 1
        else:
            status = "[red]Offline[/red]"

        types = ", ".join(data["content_types"][:3])
        if len(data["content_types"]) > 3:
            types += "..."

        table.add_row(name, status, str(data["priority"]), types)

    console.print(table)
    console.print(f"\n[bold]{online_count}/{len(health_data)}[/bold] sources online")


@cli.command()
@click.option('--limit', '-n', default=20, help='Number of downloads to show')
@click.option('--all', 'show_all', is_flag=True, help='Show all downloads')
def downloads(limit: int, show_all: bool):
    """Show download history."""
    from blackreach.memory import PersistentMemory

    console.print(BANNER)
    console.print("[bold]Download History[/bold]\n")

    memory = PersistentMemory()

    if show_all:
        limit = 1000  # Reasonable max

    downloads_list = memory.get_downloads(limit)

    if not downloads_list:
        console.print("[dim]No downloads recorded yet.[/dim]")
        return

    table = Table(title=f"Recent Downloads ({len(downloads_list)} shown)")
    table.add_column("Filename", style="cyan", max_width=40)
    table.add_column("Size", justify="right")
    table.add_column("Source", style="dim")
    table.add_column("Date", style="dim")

    total_size = 0
    for dl in downloads_list:
        filename = dl.get("filename", "unknown")
        if len(filename) > 40:
            filename = filename[:37] + "..."

        size = dl.get("file_size", 0)
        total_size += size
        if size > 1024 * 1024:  # MB
            size_str = f"{size / (1024*1024):.1f} MB"
        elif size > 1024:  # KB
            size_str = f"{size / 1024:.0f} KB"
        else:
            size_str = f"{size} B"

        source = dl.get("source_site", "")[:20] or "-"

        date_str = dl.get("downloaded_at", "")
        if date_str:
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                date_str = dt.strftime("%Y-%m-%d %H:%M")
            except (ValueError, TypeError):
                date_str = date_str[:16]

        table.add_row(filename, size_str, source, date_str)

    console.print(table)

    # Summary
    if total_size > 1024 * 1024 * 1024:  # GB
        total_str = f"{total_size / (1024**3):.2f} GB"
    elif total_size > 1024 * 1024:  # MB
        total_str = f"{total_size / (1024**2):.1f} MB"
    else:
        total_str = f"{total_size / 1024:.0f} KB"

    console.print(f"\n[bold]Total:[/bold] {len(downloads_list)} files, {total_str}")


@cli.command()
@click.option('--limit', '-n', default=20, help='Number of sessions to show')
def sessions(limit: int):
    """Show session history."""
    from blackreach.memory import PersistentMemory

    console.print(BANNER)
    console.print("[bold]Session History[/bold]\n")

    memory = PersistentMemory()
    sessions_list = memory.get_sessions(limit)

    if not sessions_list:
        console.print("[dim]No sessions recorded yet.[/dim]")
        return

    table = Table(title=f"Recent Sessions ({len(sessions_list)} shown)")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("Goal", style="cyan", max_width=35)
    table.add_column("Status")
    table.add_column("Steps", justify="right")
    table.add_column("Downloads", justify="right")
    table.add_column("Duration", justify="right")
    table.add_column("Date", style="dim")

    success_count = 0
    for session in sessions_list:
        session_id = str(session.get("id", ""))
        goal = session.get("goal", "unknown")
        if len(goal) > 35:
            goal = goal[:32] + "..."

        success = session.get("success")
        if success is None:
            status = "[yellow]Running[/yellow]"
        elif success:
            status = "[green]Success[/green]"
            success_count += 1
        else:
            status = "[red]Failed[/red]"

        steps = str(session.get("steps_taken", 0))
        downloads = str(session.get("downloads_count", 0))

        # Calculate duration
        start = session.get("start_time", "")
        end = session.get("end_time", "")
        if start and end:
            try:
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                duration_sec = (end_dt - start_dt).total_seconds()
                if duration_sec > 3600:
                    duration = f"{duration_sec / 3600:.1f}h"
                elif duration_sec > 60:
                    duration = f"{duration_sec / 60:.0f}m"
                else:
                    duration = f"{duration_sec:.0f}s"
            except (ValueError, TypeError):
                duration = "-"
        else:
            duration = "-"

        # Format date
        if start:
            try:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                date_str = dt.strftime("%m/%d %H:%M")
            except (ValueError, TypeError):
                date_str = start[:10]
        else:
            date_str = "-"

        table.add_row(session_id, goal, status, steps, downloads, duration, date_str)

    console.print(table)

    completed = len([s for s in sessions_list if s.get("end_time")])
    if completed > 0:
        rate = round(success_count / completed * 100, 1)
        console.print(f"\n[bold]Success rate:[/bold] {rate}% ({success_count}/{completed} completed)")


@cli.command()
@click.option('--logs', 'clear_logs', is_flag=True, help='Clear log files')
@click.option('--days', default=7, help='Keep logs newer than N days (default: 7)')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
def clear(clear_logs: bool, days: int, force: bool):
    """Clear old logs and cached data."""
    from blackreach.logging import cleanup_old_logs, LOG_DIR

    console.print(BANNER)
    console.print("[bold]Data Cleanup[/bold]\n")

    if clear_logs:
        if not force:
            if not Confirm.ask(f"Delete logs older than {days} days?"):
                console.print("[dim]Cancelled.[/dim]")
                return

        # Count files before
        log_files = list(LOG_DIR.glob("session_*.jsonl")) if LOG_DIR.exists() else []
        before_count = len(log_files)

        cleanup_old_logs(keep_days=days)

        # Count after
        log_files = list(LOG_DIR.glob("session_*.jsonl")) if LOG_DIR.exists() else []
        after_count = len(log_files)
        deleted = before_count - after_count

        if deleted > 0:
            console.print(f"[green]Deleted {deleted} log files[/green]")
        else:
            console.print("[dim]No logs to delete[/dim]")
    else:
        console.print("Usage: blackreach clear --logs")
        console.print("  --logs    Clear old log files")
        console.print("  --days N  Keep logs newer than N days (default: 7)")
        console.print("  --force   Skip confirmation")


@cli.command()
@click.option('--limit', '-n', default=5, help='Number of recent logs to show')
@click.option('--id', 'session_id', type=int, help='Show specific session log')
def logs(limit: int, session_id: int):
    """Show recent session logs."""
    from blackreach.logging import get_recent_logs, read_log, LOG_DIR

    console.print(BANNER)
    console.print("[bold]Session Logs[/bold]\n")

    if session_id:
        if LOG_DIR.exists():
            matching = list(LOG_DIR.glob(f"session_{session_id}_*.jsonl"))
            if matching:
                log_file = matching[0]
                entries = read_log(log_file)
                console.print(f"[cyan]Session {session_id}[/cyan] - {log_file.name}\n")

                for entry in entries[:50]:  # Limit entries shown
                    level = entry.get("level", "INFO")
                    event = entry.get("event", "unknown")
                    step = entry.get("step", "")

                    if level == "ERROR":
                        style = "red"
                    elif level == "WARNING":
                        style = "yellow"
                    else:
                        style = "dim"

                    step_str = f"[{step}] " if step else ""
                    console.print(f"[{style}]{step_str}{event}[/{style}]", end="")

                    data = entry.get("data", {})
                    if event == "act":
                        action = data.get("action", "")
                        console.print(f" {action}")
                    elif event == "error":
                        console.print(f" {data.get('error', '')[:50]}")
                    elif event == "download":
                        console.print(f" {data.get('filename', '')}")
                    else:
                        console.print()
            else:
                console.print(f"[red]No log found for session {session_id}[/red]")
        return

    # Show recent logs
    log_files = get_recent_logs(limit)

    if not log_files:
        console.print("[dim]No logs found.[/dim]")
        console.print(f"[dim]Log directory: {LOG_DIR}[/dim]")
        return

    table = Table(title=f"Recent Logs ({len(log_files)} shown)")
    table.add_column("Session", justify="right", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Events", justify="right")
    table.add_column("Status")

    for log_file in log_files:
        parts = log_file.stem.split("_")  # session_ID_TIMESTAMP.jsonl
        sid = parts[1] if len(parts) > 1 else "?"
        timestamp = parts[2] if len(parts) > 2 else ""

        # Format date
        if timestamp:
            try:
                dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S")
                date_str = dt.strftime("%m/%d %H:%M")
            except (ValueError, TypeError):
                date_str = timestamp[:8]
        else:
            date_str = "-"

        entries = read_log(log_file)
        event_count = len(entries)

        has_end = any(e.get("event") == "session_end" for e in entries)
        has_error = any(e.get("level") == "ERROR" for e in entries)

        if has_end:
            end_entry = next((e for e in entries if e.get("event") == "session_end"), {})
            success = end_entry.get("data", {}).get("success", False)
            status = "[green]Success[/green]" if success else "[red]Failed[/red]"
        elif has_error:
            status = "[yellow]Errors[/yellow]"
        else:
            status = "[dim]Running?[/dim]"

        table.add_row(sid, date_str, str(event_count), status)

    console.print(table)
    console.print(f"\n[dim]Log directory: {LOG_DIR}[/dim]")
    console.print("[dim]Use 'blackreach logs --id <session_id>' to view details[/dim]")


def interactive_mode():
    """Interactive REPL mode with full polish."""
    global _active_agent
    from blackreach.agent import Agent, AgentConfig
    from blackreach.llm import LLMConfig
    from blackreach import ui

    ui.print_banner()

    cfg = config_manager.load()
    provider = cfg.default_provider
    model = getattr(cfg, provider).default_model

    try:
        from blackreach.memory import PersistentMemory
        mem = PersistentMemory(Path("./memory.db"))
        stats = mem.get_stats()
        mem.close()
    except Exception:  # Best-effort stats display
        stats = {"total_sessions": 0, "total_downloads": 0}

    ui.print_welcome(provider, model)
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
                except OSError:
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
                        llm_config = _make_llm_config(provider, model, cfg)
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
                except (OSError, BlackreachError) as e:
                    ui.print_error(f"Failed to load sessions: {e}")

            elif cmd_lower.startswith('/resume '):
                # Resume a specific session
                try:
                    session_id = int(cmd.split(' ', 1)[1].strip())
                    from blackreach.agent import Agent, AgentConfig, AgentCallbacks
                    from blackreach.llm import LLMConfig

                    # Check API key
                    if provider != "ollama" and not config_manager.has_api_key(provider):
                        ui.print_error(f"No API key configured for {provider}. Run /config to set it, or /provider to switch.")
                        continue

                    with ui.spinner(f"Resuming session #{session_id}..."):
                        llm_config = _make_llm_config(provider, model, cfg)

                        agent_config = AgentConfig(
                            max_steps=cfg.max_steps,
                            headless=cfg.headless,
                            download_dir=Path(cfg.download_dir),
                            browser_type=cfg.browser_type
                        )

                        agent = Agent(llm_config=llm_config, agent_config=agent_config)
                        _active_agent = agent

                    result = agent.resume(session_id, quiet=False)

                    ui.AgentProgress().complete(result.get('success', False), result)
                    _active_agent = None

                except SessionNotFoundError as e:
                    ui.print_error(str(e))
                except BlackreachError as e:
                    ui.print_error(f"Resume failed: {e}")
                except Exception as e:
                    ui.print_error(f"Unexpected error during resume: {e}")
                finally:
                    _active_agent = None

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
                    ui.print_info("Use /config to set your API key, or /provider to switch providers")
                    ui.print_info(f"Or set the env var: export {provider.upper()}_API_KEY=\"your-key\"")
                    continue

                # Run agent with progress display
                run_agent_with_ui(goal, provider, model, cfg)

        except KeyboardInterrupt:
            console.print()
            ui.print_info("Press Ctrl+C again to exit, or type a command")
            try:
                # Wait briefly for another Ctrl+C (time imported at module level)
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
            llm_config = _make_llm_config(provider, model, cfg)

            agent_config = AgentConfig(
                max_steps=cfg.max_steps,
                headless=cfg.headless,
                download_dir=Path(cfg.download_dir),
                            browser_type=cfg.browser_type
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
    except BlackreachError as e:
        ui.print_error(str(e))
    except Exception as e:
        ui.print_error(f"Unexpected error: {e}")

    finally:
        _active_agent = None


def show_help():
    """Show help message."""
    from blackreach import ui
    ui.print_help()


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind")
@click.option("--port", default=7433, type=int, help="Port to listen on")
def serve(host: str, port: int):
    """Start the REST API server."""
    from blackreach.server import main as server_main
    console.print(BANNER)
    console.print(f"[bold]Starting API server on {host}:{port}[/bold]\n")
    try:
        server_main(host=host, port=port)
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise SystemExit(1) from exc


def main():
    """Entry point."""
    cli()


if __name__ == "__main__":
    main()
