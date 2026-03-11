# AI Browser MVP Build Plan (4 Weeks)

## Architecture Overview

```
┌─────────────────────────────────────────┐
│  Electron App (Frontend)                │
│  - React UI (sidebar like Arc)          │
│  - Voice commands (Web Speech API)      │
│  - LLM selector dropdown                │
│  - Task logs display                    │
└─────────────┬───────────────────────────┘
              │ HTTP/WebSocket
              ↓
┌─────────────────────────────────────────┐
│  FastAPI Server (Backend)               │
│  - Runs Blackreach agent                │
│  - Handles LLM API routing              │
│  - Manages browser sessions             │
│  - WebSocket for real-time updates      │
└─────────────┬───────────────────────────┘
              │
              ↓
┌─────────────────────────────────────────┐
│  Blackreach (Python Core)               │
│  - Browser automation (Playwright)      │
│  - Cloudflare bypass                    │
│  - Multi-LLM support                    │
│  - Download manager                     │
└─────────────────────────────────────────┘
```

---

## Week 1: Backend API Wrapper

### Day 1-2: FastAPI Wrapper Around Blackreach

**Goal:** Expose Blackreach as an API service

```python
# File: blackreach_server/main.py

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from blackreach.agent import Agent
from blackreach.config import Config
import asyncio

app = FastAPI()

# Allow Electron app to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Electron dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active agent sessions
sessions = {}

@app.post("/api/task/start")
async def start_task(goal: str, llm_provider: str, api_key: str):
    """Start a new agent task"""
    session_id = str(uuid.uuid4())

    # Configure Blackreach to use selected LLM
    config = Config()
    config.set_llm_provider(llm_provider, api_key)

    # Create agent
    agent = Agent(config=config, goal=goal)
    sessions[session_id] = agent

    # Run agent in background
    asyncio.create_task(agent.run_async())

    return {"session_id": session_id, "status": "started"}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """Stream agent logs in real-time"""
    await websocket.accept()
    agent = sessions.get(session_id)

    while True:
        # Send agent status updates
        status = agent.get_status()
        await websocket.send_json(status)
        await asyncio.sleep(0.5)

@app.get("/api/task/{session_id}/status")
async def get_status(session_id: str):
    """Get current task status"""
    agent = sessions.get(session_id)
    return agent.get_status() if agent else {"error": "Not found"}
```

**Test:** `curl -X POST http://localhost:8000/api/task/start -d '{"goal": "test", "llm_provider": "openai", "api_key": "..."}'`

---

### Day 3-4: Add Multi-LLM Routing

**Goal:** Let users switch between OpenAI, Claude, Grok, Ollama

```python
# File: blackreach_server/llm_router.py

class LLMRouter:
    """Route requests to different LLM providers"""

    PROVIDERS = {
        "openai": {"models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"]},
        "anthropic": {"models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"]},
        "xai": {"models": ["grok-beta"]},
        "ollama": {"models": ["llama3", "mistral", "phi3"], "local": True}
    }

    @staticmethod
    def get_client(provider: str, api_key: str = None):
        if provider == "openai":
            return openai.OpenAI(api_key=api_key)
        elif provider == "anthropic":
            return anthropic.Anthropic(api_key=api_key)
        elif provider == "xai":
            return openai.OpenAI(
                base_url="https://api.x.ai/v1",
                api_key=api_key
            )
        elif provider == "ollama":
            return openai.OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama"  # Local, no key needed
            )
```

**Add to Blackreach config:**
```python
# File: blackreach/config.py (modify existing)

def set_llm_provider(self, provider: str, api_key: str = None, model: str = None):
    """Dynamically set LLM provider"""
    self._config['llm']['provider'] = provider
    if api_key:
        self._config['llm']['api_key'] = api_key
    if model:
        self._config['llm']['model'] = model
```

---

### Day 5-7: Voice Command Processing

**Goal:** "Find me Python jobs on Indeed" → parsed into task

```python
# File: blackreach_server/voice_processor.py

import re
from dataclasses import dataclass

@dataclass
class VoiceCommand:
    action: str  # "search", "download", "research", "scrape"
    target: str  # "jobs", "papers", "repos"
    query: str   # "Python jobs"
    source: str  # "Indeed", "arXiv", "GitHub"

class VoiceParser:
    PATTERNS = {
        "job_search": r"find.*(jobs?|positions?|roles?).*on (Indeed|LinkedIn|AngelList)",
        "research": r"research (.*) (on|from) (arXiv|Google Scholar|PubMed)",
        "download": r"download (.*) from (.*)",
        "scrape": r"(scrape|extract|get) (.*) from (.*)",
    }

    @staticmethod
    def parse(voice_input: str) -> VoiceCommand:
        voice_input = voice_input.lower()

        # Match against patterns
        for action, pattern in VoiceParser.PATTERNS.items():
            match = re.search(pattern, voice_input, re.IGNORECASE)
            if match:
                return VoiceCommand(
                    action=action,
                    query=match.group(1) if match.groups() else "",
                    source=match.group(2) if len(match.groups()) > 1 else "",
                    target=action.split("_")[0]
                )

        # Fallback: treat as generic goal
        return VoiceCommand(
            action="general",
            query=voice_input,
            source="web",
            target="search"
        )

@app.post("/api/voice/parse")
async def parse_voice(voice_input: str):
    """Parse voice command into structured task"""
    command = VoiceParser.parse(voice_input)
    return command
```

**Test:** `curl -X POST http://localhost:8000/api/voice/parse -d '"find me Python jobs on Indeed"'`

---

## Week 2: Electron Frontend

### Day 8-10: Electron Boilerplate + UI

**Goal:** Desktop app with sidebar UI like Arc

```bash
# Initialize Electron app
npx create-electron-app blackreach-browser
cd blackreach-browser
npm install react react-dom
npm install @mui/material @emotion/react @emotion/styled  # Material UI
npm install axios socket.io-client  # API calls
```

**File: src/App.jsx**
```jsx
import React, { useState } from 'react';
import { Box, TextField, Button, Select, MenuItem, Paper } from '@mui/material';
import MicIcon from '@mui/icons-material/Mic';

function App() {
  const [goal, setGoal] = useState('');
  const [llmProvider, setLlmProvider] = useState('openai');
  const [logs, setLogs] = useState([]);
  const [isRunning, setIsRunning] = useState(false);

  const providers = {
    openai: 'OpenAI (GPT-4)',
    anthropic: 'Anthropic (Claude)',
    xai: 'xAI (Grok)',
    ollama: 'Ollama (Local)'
  };

  const startTask = async () => {
    setIsRunning(true);

    // Call backend API
    const response = await fetch('http://localhost:8000/api/task/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        goal,
        llm_provider: llmProvider,
        api_key: localStorage.getItem(`${llmProvider}_api_key`)
      })
    });

    const { session_id } = await response.json();

    // Connect WebSocket for real-time logs
    const ws = new WebSocket(`ws://localhost:8000/ws/${session_id}`);
    ws.onmessage = (event) => {
      const status = JSON.parse(event.data);
      setLogs(prev => [...prev, status.current_action]);
    };
  };

  return (
    <Box sx={{ display: 'flex', height: '100vh' }}>
      {/* Sidebar (like Arc) */}
      <Paper sx={{ width: 320, p: 2, overflow: 'auto' }}>
        <h2>Blackreach AI</h2>

        {/* LLM Selector */}
        <Select
          value={llmProvider}
          onChange={(e) => setLlmProvider(e.target.value)}
          fullWidth
          sx={{ mb: 2 }}
        >
          {Object.entries(providers).map(([key, label]) => (
            <MenuItem key={key} value={key}>{label}</MenuItem>
          ))}
        </Select>

        {/* Voice/Text Input */}
        <TextField
          fullWidth
          multiline
          rows={3}
          value={goal}
          onChange={(e) => setGoal(e.target.value)}
          placeholder="What would you like me to do?"
          sx={{ mb: 2 }}
        />

        <Button
          variant="contained"
          fullWidth
          onClick={startTask}
          disabled={isRunning}
          startIcon={<MicIcon />}
        >
          {isRunning ? 'Running...' : 'Start Task'}
        </Button>

        {/* Live Logs */}
        <Box sx={{ mt: 3 }}>
          <h3>Activity</h3>
          {logs.map((log, i) => (
            <p key={i} style={{ fontSize: 12, color: '#666' }}>{log}</p>
          ))}
        </Box>
      </Paper>

      {/* Main Browser View */}
      <Box sx={{ flex: 1, bgcolor: '#f5f5f5' }}>
        <webview
          src="about:blank"
          style={{ width: '100%', height: '100%' }}
        />
      </Box>
    </Box>
  );
}

export default App;
```

---

### Day 11-12: Voice Input (Web Speech API)

```jsx
// Add to App.jsx

const [isListening, setIsListening] = useState(false);

const startVoiceInput = () => {
  const recognition = new window.webkitSpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => setIsListening(true);
  recognition.onend = () => setIsListening(false);

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    setGoal(transcript);
  };

  recognition.start();
};

// Update button
<Button
  variant="outlined"
  onClick={startVoiceInput}
  startIcon={<MicIcon />}
  sx={{ mb: 1 }}
>
  {isListening ? '🎤 Listening...' : 'Voice Command'}
</Button>
```

---

### Day 13-14: Settings Panel (API Keys)

```jsx
// File: src/Settings.jsx

function Settings() {
  const [apiKeys, setApiKeys] = useState({
    openai: localStorage.getItem('openai_api_key') || '',
    anthropic: localStorage.getItem('anthropic_api_key') || '',
    xai: localStorage.getItem('xai_api_key') || ''
  });

  const saveKeys = () => {
    Object.entries(apiKeys).forEach(([provider, key]) => {
      localStorage.setItem(`${provider}_api_key`, key);
    });
    alert('API keys saved!');
  };

  return (
    <Box sx={{ p: 3 }}>
      <h2>Settings</h2>

      <TextField
        fullWidth
        label="OpenAI API Key"
        type="password"
        value={apiKeys.openai}
        onChange={(e) => setApiKeys({...apiKeys, openai: e.target.value})}
        sx={{ mb: 2 }}
      />

      <TextField
        fullWidth
        label="Anthropic API Key"
        type="password"
        value={apiKeys.anthropic}
        onChange={(e) => setApiKeys({...apiKeys, anthropic: e.target.value})}
        sx={{ mb: 2 }}
      />

      <TextField
        fullWidth
        label="xAI API Key"
        type="password"
        value={apiKeys.xai}
        onChange={(e) => setApiKeys({...apiKeys, xai: e.target.value})}
        sx={{ mb: 2 }}
      />

      <Button variant="contained" onClick={saveKeys}>
        Save API Keys
      </Button>

      <p style={{ marginTop: 20, fontSize: 12, color: '#666' }}>
        💡 For Ollama (local models), no API key needed - just install Ollama
      </p>
    </Box>
  );
}
```

---

## Week 3: Integration + Polish

### Day 15-17: Connect Frontend ↔ Backend

**Test the full flow:**
1. User types "Find Python jobs on Indeed"
2. Frontend sends to backend API
3. Backend starts Blackreach agent
4. Agent navigates Indeed, extracts jobs
5. Frontend shows real-time logs via WebSocket
6. Results appear in sidebar

**Add download manager UI:**
```jsx
// Show downloads in sidebar
<Box sx={{ mt: 2 }}>
  <h3>Downloads</h3>
  {downloads.map(file => (
    <Paper sx={{ p: 1, mb: 1 }}>
      <p>{file.name}</p>
      <LinearProgress variant="determinate" value={file.progress} />
    </Paper>
  ))}
</Box>
```

---

### Day 18-19: Keyboard Shortcuts

```jsx
// Add to App.jsx

useEffect(() => {
  const handleKeyPress = (e) => {
    // Cmd+K or Ctrl+K: Focus input
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      document.querySelector('textarea').focus();
    }

    // Cmd+Enter: Start task
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      startTask();
    }

    // Cmd+1/2/3/4: Switch LLM
    if ((e.metaKey || e.ctrlKey) && ['1','2','3','4'].includes(e.key)) {
      const providers = ['openai', 'anthropic', 'xai', 'ollama'];
      setLlmProvider(providers[parseInt(e.key) - 1]);
    }
  };

  window.addEventListener('keydown', handleKeyPress);
  return () => window.removeEventListener('keydown', handleKeyPress);
}, []);
```

---

### Day 20-21: Error Handling + Polish

**Add error states:**
```jsx
const [error, setError] = useState(null);

// In startTask():
try {
  // ... API call
} catch (err) {
  setError(`Failed: ${err.message}`);
  setIsRunning(false);
}

// Show errors
{error && (
  <Alert severity="error" onClose={() => setError(null)}>
    {error}
  </Alert>
)}
```

**Add loading states, animations, better UX**

---

## Week 4: Testing + Launch Prep

### Day 22-24: User Testing

**Recruit 5-10 beta testers:**
- Post on r/MacApps, r/SideProject
- DM friends/colleagues
- "Testing my new AI browser - need feedback"

**Give them tasks:**
1. "Find remote Python jobs on Indeed"
2. "Research papers about LLMs on arXiv"
3. "Download the top 5 results"

**Measure:**
- Does it work? (success rate)
- Is it fast? (time to complete)
- Is it intuitive? (do they understand how to use it?)

---

### Day 25-26: Fix Bugs from Testing

**Common issues you'll find:**
- Cloudflare still blocks some sites
- WebSocket disconnects randomly
- Voice recognition accuracy issues
- UI feels clunky

**Prioritize:**
- P0: Crashes, data loss
- P1: Core features broken
- P2: UX annoyances
- P3: Nice-to-haves

**Fix P0/P1, defer P2/P3 for post-launch**

---

### Day 27-28: Launch Materials

**Create:**
1. **Product Hunt page**
   - "Blackreach - The AI browser where YOU pick the brain"
   - Screenshot/demo video
   - Launch on Tuesday/Wednesday (best days)

2. **Landing page**
   - What: "First AI browser with multi-LLM support"
   - Why: "Use OpenAI for code, Claude for writing, Grok for data"
   - How: Download link, demo video
   - CTA: "Download for Mac" (start with Mac, Windows later)

3. **Demo video (2 min)**
   - Show voice command: "Find me Python jobs"
   - Show switching LLMs mid-task
   - Show results + downloads

4. **Reddit posts**
   - r/MacApps: "I built an AI browser that lets you pick which AI to use"
   - r/SideProject: "Spent 4 weeks building this..."
   - r/LocalLLaMA: "First AI browser with Ollama support"

---

## How to Make Sure It's GOOD

### Quality Checklist (Before Launch)

#### ✅ Core Functionality
- [ ] User can input task (text or voice)
- [ ] User can switch between 4 LLM providers
- [ ] Agent actually completes basic tasks (search, download)
- [ ] Real-time logs show what's happening
- [ ] Results are accurate (no hallucinations)

#### ✅ Reliability
- [ ] Doesn't crash during tasks
- [ ] Handles network errors gracefully
- [ ] Cloudflare bypass works 70%+ of the time
- [ ] Can interrupt/cancel running tasks

#### ✅ User Experience
- [ ] Launches in <3 seconds
- [ ] UI is intuitive (no manual needed)
- [ ] Voice recognition works 80%+ of time
- [ ] Keyboard shortcuts work
- [ ] Looks polished (not like a prototype)

#### ✅ Performance
- [ ] Tasks complete in reasonable time (<5 min for job search)
- [ ] Doesn't use excessive RAM (< 500MB idle)
- [ ] Downloads don't block UI

---

### Metrics to Track (Post-Launch)

**Week 1 Goals:**
- ✅ 100 downloads
- ✅ 20 active users (ran at least 1 task)
- ✅ 5 users ran 5+ tasks (power users)

**Week 2-4 Goals:**
- ✅ 500 downloads
- ✅ 100 active users
- ✅ 20% retention (users come back next day)
- ✅ 50+ upvotes on Product Hunt

**Month 2-3 Goals:**
- ✅ 5,000 downloads
- ✅ 1,000 active users
- ✅ 30% retention
- ✅ First paying customers (if you add premium features)

---

### How to Know If It's "Good Enough"

**MVP is good enough when:**
1. **5 strangers use it successfully** (not just friends)
2. **At least 1 person says "this is amazing"** (validates value prop)
3. **No P0 bugs in 10 test runs** (stable enough)
4. **You'd use it yourself daily** (dogfooding test)

**Don't wait for perfect.** Ship when it's 80% done.

---

### Post-Launch Iteration

**After launch, prioritize based on user feedback:**

**If users say: "This is cool but..."**
- "...it's too slow" → Optimize agent speed
- "...it crashes" → Fix stability
- "...I don't know what it's doing" → Better logs/UI
- "...Cloudflare blocks me" → Improve bypass

**If users say: "I wish it could..."**
- "...remember my tasks" → Add session history
- "...auto-fill forms" → Add Dia-like Skills
- "...work offline" → Add Ollama by default
- "...share results" → Add export feature

**Iterate every 2 weeks based on top 3 requests.**

---

## Tech Stack Summary

| Component | Technology | Why |
|-----------|-----------|-----|
| **Desktop App** | Electron | Cross-platform, web tech |
| **Frontend** | React + Material UI | Fast to build, looks good |
| **Backend API** | FastAPI | Async, fast, Python |
| **Browser Engine** | Chromium (via Electron) | Standard, compatible |
| **Automation** | Blackreach/Playwright | Already built |
| **LLMs** | OpenAI, Anthropic, xAI, Ollama | Multi-provider |
| **Real-time** | WebSockets | Live agent logs |
| **Storage** | localStorage + SQLite | API keys + sessions |

---

## Timeline Summary

**Week 1:** Backend API wrapper + multi-LLM routing
**Week 2:** Electron app + UI + voice input
**Week 3:** Integration + polish + keyboard shortcuts
**Week 4:** User testing + bug fixes + launch prep

**Day 28:** Ship it. 🚀

---

## Cost to Build

**Tools:**
- Electron: Free
- FastAPI: Free
- React: Free
- OpenAI API (testing): $5-20
- Domain name (optional): $10/year
- **Total: <$50**

---

## Next Steps

**Option 1: Start Building Tonight**
I can generate the full boilerplate for you right now:
- FastAPI server setup
- Electron app scaffold
- React components

**Option 2: Validate First**
Build a fake landing page, post on Reddit:
"Would you use an AI browser where you pick which AI runs your tasks?"
Get 50+ "yes" responses → then build

**Option 3: Hire Help**
Post on Upwork: "Need Electron dev to wrap my Python project"
Budget: $500-2000 for 1-2 weeks work

---

Which approach do you want? I can start building the backend API wrapper right now if you want to go for it.
