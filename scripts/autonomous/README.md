# Autonomous Claude Work Daemon

**The sauce nobody shares for free.**

Force Claude to work for REAL wall-clock time, not just "finish as fast as possible".

## How It Works

1. **daemon.py** - The orchestrator that:
   - Launches multiple Claude agents with specific tasks
   - Monitors their progress every 60 seconds
   - **Resumes agents if they finish early** ← This is the key
   - Tracks findings count and demands more if below target
   - Keeps looping until wall-clock time expires

2. **Time Enforcement** - The secret sauce:
   - Claude wants to finish fast. We don't let it.
   - If agent completes before time → automatically resume with "go deeper"
   - If findings < target → resume with "you need X more findings"
   - External timer is the enforcer, not Claude's internal sense of "done"

## Usage

### Quick Start (10-hour sprint)
```bash
./launch.sh 10
```

### Check Status
```bash
./status.sh
```

### Stop Daemon
```bash
./stop.sh
```

### Custom Configuration
```bash
python daemon.py --hours 5 --agents security performance
python daemon.py --hours 2 --check-interval 30 --quiet
```

## Available Agents

- **performance** - Find slow paths, memory issues, optimization opportunities
- **security** - Find vulnerabilities, injection points, credential exposure
- **code_quality** - Code smells, naming issues, missing docs, dead code
- **test_gaps** - Missing tests, weak assertions, uncovered code

## Output

All findings written to:
```
deep_work_logs/
├── daemon.log              # Daemon activity log
├── daemon.pid              # PID file for daemon
├── performance_findings.md # Performance agent findings
├── security_findings.md    # Security agent findings
├── code_quality_findings.md
├── test_gap_findings.md
└── session_summary.json    # Final summary
```

## The Philosophy

LLMs are trained to be efficient - they want to "finish" tasks quickly.
But real human developers spend HOURS on code review, security audits, etc.

This daemon forces that behavior:
- **Minimum findings** = Can't finish until you find enough
- **Time enforcement** = Can't finish until clock says so
- **Auto-resume** = Get sent back to work if you stop early

The result: Thorough, exhaustive analysis instead of quick surface passes.

## Running While AFK

This runs on your 24/7 server. Launch and disconnect:

```bash
./launch.sh 10  # Launch 10-hour sprint
# Now disconnect from SSH - daemon keeps running
```

Check later:
```bash
./status.sh
cat deep_work_logs/session_summary.json
```

## No Third-Party Tools Required

Just:
- Claude Code CLI (which you already have)
- Python 3 (standard on Linux)
- Bash (standard on Linux)

That's it. No paid services, no installations, no API keys beyond what Claude Code already uses.
