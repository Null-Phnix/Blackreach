"""
Blackreach UI - Terminal Interface Components

Provides:
- Spinners during operations
- Streaming output
- Status bar
- Rich formatting
- Keyboard handling
- Download progress bars
- Better error display
"""

import time
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.spinner import Spinner
from rich.text import Text
from rich.table import Table
from rich.status import Status
from rich.rule import Rule
from rich.style import Style
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TaskProgressColumn,
)
from rich.traceback import Traceback
from rich.syntax import Syntax
from rich.markdown import Markdown

from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.styles import Style as PTStyle
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.shortcuts import radiolist_dialog


# Global console
console = Console()

# Config directory for history
HISTORY_FILE = Path.home() / ".blackreach" / "history"


@dataclass
class Theme:
    """Color theme for the UI."""
    primary = "cyan"
    secondary = "blue"
    success = "green"
    warning = "yellow"
    error = "red"
    muted = "dim white"
    highlight = "bold cyan"


theme = Theme()


# ============================================================================
# Spinners and Progress
# ============================================================================

@contextmanager
def spinner(message: str = "Working..."):
    """Show a spinner while doing work."""
    with console.status(f"[{theme.primary}]{message}[/]", spinner="dots") as status:
        yield status


@contextmanager
def step_spinner(step_name: str):
    """Show a spinner for a specific step."""
    with console.status(f"[{theme.muted}]{step_name}[/]", spinner="dots2") as status:
        yield status


class AgentProgress:
    """Progress display for agent operations."""

    def __init__(self):
        self.live: Optional[Live] = None
        self.current_step = 0
        self.max_steps = 0
        self.current_phase = ""
        self.last_action = ""
        self._step_shown = set()  # Track which steps we've shown headers for

    def start(self, goal: str, max_steps: int):
        """Start the progress display."""
        self.max_steps = max_steps
        self.current_step = 0
        self._step_shown = set()
        console.print()
        console.print(Panel(
            f"[bold]{goal}[/bold]",
            title="[bold cyan]Goal[/bold cyan]",
            border_style=theme.primary,
            padding=(0, 2)
        ))
        console.print()

    def update_step(self, step: int, phase: str, detail: str = ""):
        """Update the current step."""
        self.current_step = step
        self.current_phase = phase

        # Only print step header once per step
        if step not in self._step_shown:
            self._step_shown.add(step)
            # Progress bar style header
            progress_pct = (step / self.max_steps) * 100
            bar_width = 20
            filled = int((step / self.max_steps) * bar_width)
            bar = "█" * filled + "░" * (bar_width - filled)
            console.print(f"\n  [{theme.muted}]Step {step}/{self.max_steps}[/] [{theme.primary}]{bar}[/] [{theme.muted}]{progress_pct:.0f}%[/]")

        # Phase icons
        icons = {
            "observe": "👁 ",
            "think": "🧠",
            "act": "⚡",
            "step": "→",
        }
        icon = icons.get(phase.lower(), "•")

        if phase.lower() != "step":
            phase_text = f"[{theme.primary}]{icon} {phase.upper()}[/]"
            if detail:
                detail_short = detail[:60] + "..." if len(detail) > 60 else detail
                console.print(f"    {phase_text} [{theme.muted}]{detail_short}[/]")

    def update_action(self, action: str, args: dict = None):
        """Show the action being taken."""
        self.last_action = action

        # Action-specific icons
        action_icons = {
            "click": "🖱️ ",
            "type": "⌨️ ",
            "scroll": "📜",
            "navigate": "🌐",
            "download": "📥",
            "back": "◀️ ",
            "wait": "⏳",
            "done": "✅",
        }
        icon = action_icons.get(action.lower(), "→")

        action_text = f"[{theme.success}]{icon} {action}[/]"

        if args and isinstance(args, dict):
            # Format args nicely
            arg_parts = []
            for k, v in list(args.items())[:2]:
                if k in ["action", "done", "error"]:
                    continue
                val = str(v)[:40]
                arg_parts.append(f"{k}={val}")
            if arg_parts:
                console.print(f"      {action_text} [{theme.muted}]({', '.join(arg_parts)})[/]")
            else:
                console.print(f"      {action_text}")
        else:
            console.print(f"      {action_text}")

    def show_error(self, error: str):
        """Show an error."""
        error_short = error[:80] + "..." if len(error) > 80 else error
        console.print(f"      [{theme.error}]✗ Error: {error_short}[/]")

    def complete(self, success: bool, result: dict):
        """Show completion status."""
        console.print()

        downloads = result.get('downloads', [])
        pages = result.get('pages_visited', 0)
        steps = result.get('steps_taken', 0)
        failures = result.get('failures', 0)

        if success and steps > 0:
            # Build summary content
            lines = [f"[{theme.success}]✓ Goal completed[/]", ""]

            # Stats in a mini table format
            stats = []
            if downloads:
                stats.append(f"📥 Downloads: {len(downloads)}")
            stats.append(f"🌐 Pages: {pages}")
            stats.append(f"📊 Steps: {steps}")
            if failures > 0:
                stats.append(f"[{theme.warning}]⚠ Retries: {failures}[/]")

            lines.append("  ".join(stats))

            # List downloads if any
            if downloads:
                lines.append("")
                lines.append("[bold]Downloaded files:[/bold]")
                for dl in downloads[:5]:
                    if isinstance(dl, dict):
                        lines.append(f"  • {dl.get('filename', 'unknown')}")
                    else:
                        lines.append(f"  • {dl}")
                if len(downloads) > 5:
                    lines.append(f"  [dim]... and {len(downloads) - 5} more[/dim]")

            console.print(Panel(
                "\n".join(lines),
                title="[bold green]Success[/bold green]",
                border_style=theme.success,
                padding=(0, 2)
            ))
        else:
            console.print(Panel(
                f"[{theme.warning}]Agent stopped[/]\n\n"
                f"📊 Steps: {steps}\n"
                f"⚠️  Failures: {failures}",
                title="[bold yellow]Incomplete[/bold yellow]",
                border_style=theme.warning,
                padding=(0, 2)
            ))


# ============================================================================
# Interactive Prompt
# ============================================================================

class SlashCompleter(Completer):
    """Custom completer for slash commands."""

    def __init__(self):
        self.commands = [
            ('/help', 'Show help'),
            ('/h', 'Show help'),
            ('/model', 'Change AI model'),
            ('/m', 'Change AI model'),
            ('/provider', 'Change AI provider'),
            ('/p', 'Change AI provider'),
            ('/config', 'Open configuration'),
            ('/cfg', 'Open configuration'),
            ('/models', 'List available models'),
            ('/status', 'Show current status'),
            ('/s', 'Show current status'),
            ('/logs', 'Show recent logs'),
            ('/l', 'Show recent logs'),
            ('/plan', 'Preview a plan'),
            ('/clear', 'Clear screen'),
            ('/cls', 'Clear screen'),
            ('/history', 'Show command history'),
            ('/quit', 'Exit Blackreach'),
            ('/q', 'Exit Blackreach'),
        ]

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lower()

        # Complete slash commands
        if text.startswith('/'):
            for cmd, desc in self.commands:
                if cmd.startswith(text):
                    yield Completion(
                        cmd,
                        start_position=-len(text),
                        display=cmd,
                        display_meta=desc
                    )
        # Also suggest starting with / when empty or partial
        elif not text or text == '/':
            for cmd, desc in self.commands:
                yield Completion(
                    cmd,
                    start_position=-len(text),
                    display=cmd,
                    display_meta=desc
                )


class InteractivePrompt:
    """Advanced interactive prompt with history and completion."""

    def __init__(self):
        # Ensure history directory exists
        HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Create slash command completer
        self.completer = SlashCompleter()

        # Prompt style
        self.style = PTStyle.from_dict({
            'prompt': '#00d7ff bold',  # Cyan
            'arrow': '#00d7ff',
            'completion-menu': 'bg:#1a1a2e #ffffff',
            'completion-menu.completion': 'bg:#1a1a2e #ffffff',
            'completion-menu.completion.current': 'bg:#00d7ff #000000',
            'completion-menu.meta': 'bg:#1a1a2e #888888',
            'completion-menu.meta.current': 'bg:#00d7ff #333333',
        })

        # Key bindings
        self.kb = KeyBindings()

        @self.kb.add(Keys.ControlL)
        def _(event):
            """Clear screen on Ctrl+L."""
            clear_screen()
            print_banner()

        # Create session with history
        self.session = PromptSession(
            history=FileHistory(str(HISTORY_FILE)),
            auto_suggest=AutoSuggestFromHistory(),
            completer=self.completer,
            style=self.style,
            complete_while_typing=True,
            key_bindings=self.kb,
        )

    def prompt(self, provider: str = "", model: str = "") -> str:
        """Get input from user with rich prompt."""
        # Build prompt text
        prompt_parts = []
        if provider:
            prompt_parts.append(f"[{provider}]")
        prompt_text = HTML('<prompt>blackreach</prompt> <arrow>›</arrow> ')

        try:
            return self.session.prompt(prompt_text)
        except KeyboardInterrupt:
            return ""
        except EOFError:
            return "quit"

    def prompt_simple(self, message: str, default: str = "") -> str:
        """Simple prompt without history."""
        try:
            return self.session.prompt(HTML(f'<prompt>{message}</prompt> '), default=default)
        except (KeyboardInterrupt, EOFError):
            return default


# ============================================================================
# Status Bar
# ============================================================================

class StatusBar:
    """Persistent status bar at the bottom of the terminal."""

    def __init__(self):
        self.provider = "ollama"
        self.model = "qwen2.5:7b"
        self.sessions = 0
        self.downloads = 0

    def update(self, provider: str = None, model: str = None,
               sessions: int = None, downloads: int = None):
        """Update status bar values."""
        if provider:
            self.provider = provider
        if model:
            self.model = model
        if sessions is not None:
            self.sessions = sessions
        if downloads is not None:
            self.downloads = downloads

    def render(self) -> str:
        """Render the status bar."""
        parts = [
            f"[{theme.primary}]{self.provider}[/]",
            f"[{theme.muted}]{self.model}[/]",
            f"[{theme.muted}]sessions:{self.sessions}[/]",
            f"[{theme.muted}]downloads:{self.downloads}[/]",
        ]
        return " │ ".join(parts)

    def print(self):
        """Print the status bar."""
        console.print(Rule(self.render(), style=theme.muted))


# ============================================================================
# Formatted Output
# ============================================================================

def print_banner():
    """Print the Blackreach banner."""
    banner = """[bold cyan]
╔══════════════════════════════════════════════════════════╗
║   ██████╗ ██╗      █████╗  ██████╗██╗  ██╗              ║
║   ██╔══██╗██║     ██╔══██╗██╔════╝██║ ██╔╝              ║
║   ██████╔╝██║     ███████║██║     █████╔╝               ║
║   ██╔══██╗██║     ██╔══██║██║     ██╔═██╗               ║
║   ██████╔╝███████╗██║  ██║╚██████╗██║  ██╗              ║
║   ╚═════╝ ╚══════╝╚═╝  ╚═╝ ╚═════╝╚═╝  ╚═╝              ║
║                                                          ║
║   [white]Autonomous Browser Agent[/white]              [dim]v2.0.0[/dim]   ║
╚══════════════════════════════════════════════════════════╝[/bold cyan]
"""
    console.print(banner)


def print_welcome(provider: str, model: str):
    """Print welcome message."""
    console.print(f"\n[{theme.muted}]Provider: {provider} │ Model: {model}[/]")
    console.print(f"[{theme.muted}]Type a goal to start, or /help for commands[/]")
    console.print(f"[{theme.muted}]Tab to autocomplete │ Ctrl+C cancel │ Ctrl+D exit[/]\n")


def print_help():
    """Print help message."""
    # Slash commands table
    cmd_table = Table(show_header=False, box=None, padding=(0, 2))
    cmd_table.add_column("Command", style=theme.primary)
    cmd_table.add_column("Description", style="white")

    commands = [
        ("/model, /m", "Select AI model (interactive menu)"),
        ("/provider, /p", "Select AI provider (interactive menu)"),
        ("/config, /cfg", "Open configuration"),
        ("/models", "List all available models"),
        ("/status, /s", "Show current status"),
        ("/logs, /l", "Show recent session logs"),
        ("/plan <goal>", "Preview plan without executing"),
        ("/clear, /cls", "Clear screen"),
        ("/history", "Show command history"),
        ("/help, /h, ?", "Show this help"),
        ("/quit, /q", "Exit Blackreach"),
    ]

    for cmd, desc in commands:
        cmd_table.add_row(cmd, desc)

    console.print(Panel(
        cmd_table,
        title="[bold]Slash Commands[/bold]",
        border_style=theme.secondary,
        padding=(1, 2)
    ))

    # Keyboard shortcuts
    kb_table = Table(show_header=False, box=None, padding=(0, 2))
    kb_table.add_column("Key", style=theme.primary)
    kb_table.add_column("Action", style="white")

    shortcuts = [
        ("Tab", "Show command completions"),
        ("↑ / ↓", "Navigate history / completions"),
        ("Ctrl+L", "Clear screen"),
        ("Ctrl+C", "Cancel current operation"),
        ("Ctrl+D", "Exit Blackreach"),
    ]

    for key, action in shortcuts:
        kb_table.add_row(key, action)

    console.print(Panel(
        kb_table,
        title="[bold]Keyboard Shortcuts[/bold]",
        border_style=theme.muted,
        padding=(0, 2)
    ))

    # Usage
    console.print(f"\n[bold]Usage:[/bold]")
    console.print(f"  Type a goal to run the browser agent, or use slash commands.")
    console.print(f"\n[bold]Examples:[/bold]")
    console.print(f"  [{theme.muted}]go to wikipedia and search for AI[/]")
    console.print(f"  [{theme.muted}]download the first PDF from arxiv about transformers[/]")
    console.print(f"  [{theme.muted}]navigate to github.com and find python projects[/]")
    console.print()


def print_error(message: str):
    """Print an error message."""
    console.print(f"[{theme.error}]Error: {message}[/]")


def print_success(message: str):
    """Print a success message."""
    console.print(f"[{theme.success}]✓ {message}[/]")


def print_warning(message: str):
    """Print a warning message."""
    console.print(f"[{theme.warning}]⚠ {message}[/]")


def print_info(message: str):
    """Print an info message."""
    console.print(f"[{theme.muted}]{message}[/]")


def clear_screen():
    """Clear the terminal screen."""
    console.clear()


def print_thinking(message: str):
    """Print a thinking/reasoning message."""
    console.print(f"  [{theme.muted}]💭 {message}[/]")


def print_observation(message: str):
    """Print an observation message."""
    short = message[:100] + "..." if len(message) > 100 else message
    console.print(f"  [{theme.muted}]👁 {short}[/]")


def print_action(action: str, args: dict = None):
    """Print an action message."""
    if args:
        args_str = ", ".join(f"{k}={v}" for k, v in list(args.items())[:2])
        console.print(f"  [{theme.success}]⚡ {action}[/] [{theme.muted}]({args_str})[/]")
    else:
        console.print(f"  [{theme.success}]⚡ {action}[/]")


# ============================================================================
# Streaming
# ============================================================================

def stream_text(text: str, delay: float = 0.01):
    """Stream text character by character."""
    for char in text:
        console.print(char, end="", highlight=False)
        time.sleep(delay)
    console.print()  # Newline at end


# ============================================================================
# Confirmation Prompts
# ============================================================================

def confirm(message: str, default: bool = True) -> bool:
    """Ask for confirmation."""
    from rich.prompt import Confirm
    return Confirm.ask(message, default=default)


def choose(message: str, choices: list, default: str = None) -> str:
    """Ask user to choose from options."""
    from rich.prompt import Prompt
    return Prompt.ask(message, choices=choices, default=default or choices[0])


# ============================================================================
# Interactive Menus (Claude Code style)
# ============================================================================

def show_menu(title: str, options: list, current: str = None) -> Optional[str]:
    """
    Show an interactive menu for selection.

    Args:
        title: Menu title
        options: List of (value, label) tuples
        current: Currently selected value (will be marked)

    Returns:
        Selected value or None if cancelled
    """
    try:
        # Build the options list with current marker
        menu_options = []
        for value, label in options:
            if value == current:
                menu_options.append((value, f"{label} (current)"))
            else:
                menu_options.append((value, label))

        result = radiolist_dialog(
            title=title,
            text="Use arrow keys to navigate, Enter to select, Esc to cancel",
            values=menu_options,
            default=current,
            style=PTStyle.from_dict({
                'dialog': 'bg:#1a1a2e',
                'dialog.body': 'bg:#1a1a2e #ffffff',
                'dialog frame.label': 'bg:#00d7ff #000000',
                'dialog.body label': '#00d7ff',
                'radiolist': 'bg:#1a1a2e',
                'button': 'bg:#00d7ff #000000',
                'button.focused': 'bg:#00ffff #000000 bold',
            })
        ).run()
        return result
    except Exception:
        # Fallback to simple numbered list if dialog fails
        return show_simple_menu(title, options, current)


def show_simple_menu(title: str, options: list, current: str = None) -> Optional[str]:
    """Simple numbered menu fallback."""
    console.print(f"\n[bold]{title}[/bold]\n")

    for i, (value, label) in enumerate(options, 1):
        marker = " [cyan](current)[/cyan]" if value == current else ""
        console.print(f"  [{theme.primary}]{i}[/] {label}{marker}")

    console.print(f"  [{theme.muted}]0[/] Cancel\n")

    try:
        from rich.prompt import Prompt
        choice = Prompt.ask("Select", default="0")

        if choice == "0" or choice == "":
            return None

        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx][0]
    except (ValueError, IndexError):
        pass

    return None


def show_provider_menu(current_provider: str = None) -> Optional[str]:
    """Show provider selection menu."""
    from blackreach.config import AVAILABLE_MODELS

    options = [
        ("ollama", "Ollama - Local, free, private"),
        ("xai", "xAI - Grok-4, fast reasoning"),
        ("openai", "OpenAI - GPT-4o, GPT-4"),
        ("anthropic", "Anthropic - Claude 3.5"),
        ("google", "Google - Gemini 2.5"),
    ]

    return show_simple_menu("Select Provider", options, current_provider)


def show_model_menu(current_provider: str, current_model: str = None) -> Optional[tuple]:
    """
    Show model selection menu grouped by provider.

    Returns:
        Tuple of (provider, model) or None if cancelled
    """
    from blackreach.config import AVAILABLE_MODELS

    # Build flat list with provider groupings
    options = []

    # Show current provider's models first
    if current_provider in AVAILABLE_MODELS:
        for model in AVAILABLE_MODELS[current_provider]:
            label = f"[{current_provider}] {model}"
            options.append(((current_provider, model), label))

    # Then other providers
    for provider, models in AVAILABLE_MODELS.items():
        if provider == current_provider:
            continue
        for model in models[:3]:  # Show top 3 from each
            label = f"[{provider}] {model}"
            options.append(((provider, model), label))

    console.print(f"\n[bold]Select Model[/bold]")
    console.print(f"[{theme.muted}]Current: {current_provider} / {current_model}[/]\n")

    for i, ((prov, mod), label) in enumerate(options, 1):
        marker = " [cyan](current)[/cyan]" if mod == current_model and prov == current_provider else ""
        console.print(f"  [{theme.primary}]{i:2}[/] {label}{marker}")

    console.print(f"\n  [{theme.muted}] 0[/] Cancel\n")

    try:
        from rich.prompt import Prompt
        choice = Prompt.ask("Select", default="0")

        if choice == "0" or choice == "":
            return None

        idx = int(choice) - 1
        if 0 <= idx < len(options):
            return options[idx][0]  # Returns (provider, model) tuple
    except (ValueError, IndexError):
        pass

    return None


def show_slash_menu() -> Optional[str]:
    """Show the slash command menu."""
    options = [
        ("/model", "Change AI model"),
        ("/provider", "Change AI provider"),
        ("/config", "Open configuration"),
        ("/status", "Show current status"),
        ("/models", "List all available models"),
        ("/clear", "Clear screen"),
        ("/history", "Show command history"),
        ("/help", "Show help"),
        ("/quit", "Exit Blackreach"),
    ]

    return show_simple_menu("Commands", options)


# ============================================================================
# Download Progress Display
# ============================================================================

class DownloadProgressUI:
    """
    Enhanced download progress display with rich progress bars.

    Shows:
    - Real-time download speed
    - Estimated time remaining
    - File size progress
    - Multiple concurrent downloads
    """

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self._progress: Optional[Progress] = None
        self._downloads: Dict[str, Any] = {}

    def create_progress(self) -> Progress:
        """Create a configured Progress instance for downloads."""
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.fields[filename]}", justify="left"),
            BarColumn(bar_width=30, complete_style="cyan", finished_style="green"),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=self.console,
            expand=False,
        )

    def start(self) -> None:
        """Start the progress display."""
        if self._progress is None:
            self._progress = self.create_progress()
            self._progress.start()

    def stop(self) -> None:
        """Stop the progress display."""
        if self._progress:
            self._progress.stop()
            self._progress = None

    def add_download(self, url: str, filename: str, total: int = None) -> int:
        """Add a download to track and return task ID."""
        if self._progress is None:
            self.start()

        display_name = filename[:35] + "..." if len(filename) > 35 else filename
        task_id = self._progress.add_task(
            f"[cyan]{display_name}",
            total=total,
            filename=display_name,
        )
        self._downloads[url] = {
            "task_id": task_id,
            "filename": filename,
            "total": total,
        }
        return task_id

    def update(self, url: str, completed: int, total: int = None) -> None:
        """Update download progress."""
        if url not in self._downloads or self._progress is None:
            return

        info = self._downloads[url]
        task_id = info["task_id"]

        update_kwargs = {"completed": completed}
        if total is not None:
            update_kwargs["total"] = total
            info["total"] = total

        self._progress.update(task_id, **update_kwargs)

    def complete(self, url: str, success: bool = True, error: str = None) -> None:
        """Mark a download as complete."""
        if url not in self._downloads or self._progress is None:
            return

        info = self._downloads[url]
        task_id = info["task_id"]

        if success:
            # Ensure progress shows 100%
            total = info.get("total", 100)
            self._progress.update(task_id, completed=total, total=total)
        else:
            # Show failure
            display_name = info["filename"][:30]
            self._progress.update(
                task_id,
                description=f"[red]FAILED: {display_name}",
            )

    @contextmanager
    def track_download(self, url: str, filename: str, total: int = None):
        """
        Context manager for tracking a single download.

        Usage:
            with progress_ui.track_download(url, filename) as update:
                # ... download logic ...
                update(bytes_downloaded, total_bytes)
        """
        task_id = self.add_download(url, filename, total)

        def update_func(completed: int, new_total: int = None):
            self.update(url, completed, new_total)

        try:
            yield update_func
            self.complete(url, success=True)
        except Exception as e:
            self.complete(url, success=False, error=str(e))
            raise


class MultiDownloadProgress:
    """
    Display progress for multiple downloads in a table format.

    Good for showing a summary of many downloads.
    """

    def __init__(self, console: Console = None):
        self.console = console or Console()
        self._downloads: List[Dict] = []
        self._live: Optional[Live] = None

    def add(self, filename: str, url: str = "", status: str = "pending") -> int:
        """Add a download entry and return its index."""
        entry = {
            "filename": filename,
            "url": url,
            "status": status,
            "progress": 0,
            "total": 0,
            "speed": "",
            "eta": "",
        }
        self._downloads.append(entry)
        return len(self._downloads) - 1

    def update(
        self,
        index: int,
        status: str = None,
        progress: int = None,
        total: int = None,
        speed: str = None,
        eta: str = None,
    ) -> None:
        """Update a download entry."""
        if index >= len(self._downloads):
            return

        entry = self._downloads[index]
        if status is not None:
            entry["status"] = status
        if progress is not None:
            entry["progress"] = progress
        if total is not None:
            entry["total"] = total
        if speed is not None:
            entry["speed"] = speed
        if eta is not None:
            entry["eta"] = eta

        self._refresh()

    def _create_table(self) -> Table:
        """Create the progress table."""
        table = Table(title="Downloads", expand=False)
        table.add_column("File", style="cyan", max_width=35)
        table.add_column("Status", justify="center")
        table.add_column("Progress", justify="right")
        table.add_column("Speed", justify="right")
        table.add_column("ETA", justify="right")

        for entry in self._downloads:
            # Status styling
            status = entry["status"]
            if status == "complete":
                status_display = "[green]Done[/green]"
            elif status == "downloading":
                status_display = "[cyan]...[/cyan]"
            elif status == "failed":
                status_display = "[red]Failed[/red]"
            else:
                status_display = f"[dim]{status}[/dim]"

            # Progress
            if entry["total"] > 0:
                pct = int((entry["progress"] / entry["total"]) * 100)
                progress_display = f"{pct}%"
            else:
                progress_display = "-"

            table.add_row(
                entry["filename"][:35],
                status_display,
                progress_display,
                entry["speed"] or "-",
                entry["eta"] or "-",
            )

        return table

    def _refresh(self) -> None:
        """Refresh the live display."""
        if self._live:
            self._live.update(self._create_table())

    def start(self) -> None:
        """Start the live display."""
        self._live = Live(self._create_table(), console=self.console, refresh_per_second=4)
        self._live.start()

    def stop(self) -> None:
        """Stop the live display."""
        if self._live:
            self._live.stop()
            self._live = None


# ============================================================================
# Error Display
# ============================================================================

def print_error_detail(
    error: Exception,
    title: str = "Error",
    show_traceback: bool = False,
    suggestion: str = None,
) -> None:
    """
    Display a detailed error message with optional traceback.

    Args:
        error: The exception that occurred
        title: Title for the error panel
        show_traceback: Whether to show full traceback
        suggestion: Optional suggestion for fixing the error
    """
    # Build error content
    lines = []
    lines.append(f"[bold red]{type(error).__name__}[/bold red]")
    lines.append(f"[red]{str(error)}[/red]")

    if suggestion:
        lines.append("")
        lines.append(f"[yellow]Suggestion:[/yellow] {suggestion}")

    content = "\n".join(lines)

    console.print(Panel(
        content,
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
        padding=(1, 2),
    ))

    if show_traceback:
        console.print(Traceback.from_exception(type(error), error, error.__traceback__))


def print_validation_result(result: "ValidationResult") -> None:
    """
    Display configuration validation results.

    Args:
        result: ValidationResult from config validation
    """
    from blackreach.config import ValidationResult  # Import here to avoid circular

    if result.valid and not result.warnings:
        console.print("[green]Configuration is valid.[/green]")
        return

    if result.errors:
        console.print(Panel(
            "\n".join([f"[red]X[/red] {e}" for e in result.errors]),
            title="[bold red]Configuration Errors[/bold red]",
            border_style="red",
        ))

    if result.warnings:
        console.print(Panel(
            "\n".join([f"[yellow]![/yellow] {w}" for w in result.warnings]),
            title="[bold yellow]Warnings[/bold yellow]",
            border_style="yellow",
        ))

    if result.valid:
        console.print("[green]Configuration is valid (with warnings).[/green]")
    else:
        console.print("[red]Configuration has errors. Please fix them before running.[/red]")


# ============================================================================
# Session Display
# ============================================================================

def print_session_info(
    session_id: int,
    goal: str,
    step: int,
    max_steps: int,
    status: str = "running",
    downloads: int = 0,
) -> None:
    """Display session information panel."""
    status_colors = {
        "running": "cyan",
        "paused": "yellow",
        "completed": "green",
        "failed": "red",
    }
    color = status_colors.get(status, "white")

    content = f"""[bold]Session:[/bold] #{session_id}
[bold]Goal:[/bold] {goal[:50]}{"..." if len(goal) > 50 else ""}
[bold]Progress:[/bold] Step {step}/{max_steps}
[bold]Status:[/bold] [{color}]{status.upper()}[/{color}]
[bold]Downloads:[/bold] {downloads}"""

    console.print(Panel(
        content,
        title="[bold cyan]Session Info[/bold cyan]",
        border_style="cyan",
    ))


def print_resume_options(sessions: List[Dict]) -> None:
    """Display resumable sessions in a nice table."""
    if not sessions:
        console.print("[dim]No resumable sessions found.[/dim]")
        return

    table = Table(title="Resumable Sessions", expand=False)
    table.add_column("ID", style="cyan", justify="right")
    table.add_column("Goal", max_width=40)
    table.add_column("Step", justify="right")
    table.add_column("Status")
    table.add_column("Saved", style="dim")

    for session in sessions:
        goal = session.get("goal", "")
        if len(goal) > 40:
            goal = goal[:37] + "..."

        status = session.get("status", "paused")
        status_display = f"[yellow]{status}[/yellow]" if status == "paused" else status

        saved_at = session.get("saved_at", "")[:16]  # Trim to date+time

        table.add_row(
            str(session.get("session_id", "?")),
            goal,
            str(session.get("current_step", 0)),
            status_display,
            saved_at,
        )

    console.print(table)
    console.print("\n[dim]Resume with: /resume <ID>[/dim]")


# ============================================================================
# Log Display
# ============================================================================

def print_log_entries(
    entries: List[Dict],
    title: str = "Log Entries",
    max_entries: int = 20,
) -> None:
    """
    Display log entries in a formatted table.

    Args:
        entries: List of log entry dicts
        title: Table title
        max_entries: Maximum entries to display
    """
    if not entries:
        console.print("[dim]No log entries found.[/dim]")
        return

    table = Table(title=title, expand=False)
    table.add_column("Time", style="dim", width=8)
    table.add_column("Level", width=8)
    table.add_column("Event", style="cyan")
    table.add_column("Details", max_width=40)

    level_styles = {
        "DEBUG": "dim",
        "INFO": "cyan",
        "WARNING": "yellow",
        "ERROR": "red",
        "CRITICAL": "red bold",
    }

    for entry in entries[:max_entries]:
        # Extract time (HH:MM:SS)
        timestamp = entry.get("timestamp", "")
        time_str = timestamp[11:19] if len(timestamp) > 19 else timestamp[:8]

        # Level with styling
        level = entry.get("level", "INFO")
        style = level_styles.get(level, "")
        level_display = f"[{style}]{level}[/{style}]"

        # Event
        event = entry.get("event", "")

        # Details from data
        data = entry.get("data", {})
        if data:
            # Format key details
            details_parts = []
            for k in ["action", "error", "filename", "url"]:
                if k in data:
                    v = str(data[k])[:25]
                    details_parts.append(f"{k}={v}")
            details = ", ".join(details_parts[:2])
        else:
            details = ""

        table.add_row(time_str, level_display, event, details)

    console.print(table)

    if len(entries) > max_entries:
        console.print(f"[dim]... and {len(entries) - max_entries} more entries[/dim]")
