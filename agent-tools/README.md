# 🤖 Auto-Broker Agent Tools

**Big Tech Style Browser Automation - 2026 Edition**

> *"Come OpenAI Operator, Anthropic Computer Use, e Google Project Mariner - ma per Auto-Broker"*

---

## 🏗️ Architettura

```
┌─────────────────────────────────────────────────────────────────┐
│                        KIMI (TU)                                 │
│                    Planning & Reasoning                          │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼ MCP Protocol
┌─────────────────────────────────────────────────────────────────┐
│                     MCP SERVER                                   │
│              Standard 2026 per AI ↔ Tools                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  navigate   │  │    click    │  │    type     │             │
│  │  screenshot │  │   scroll    │  │   extract   │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼ Playwright
┌─────────────────────────────────────────────────────────────────┐
│                   BROWSER AGENT                                  │
│         Anti-detection, Vision, Coordination                     │
│                    Chromium/Chrome                               │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                     TARGET SITE                                  │
│              Oracle Cloud / GitHub / Any                         │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Installazione

```bash
cd agent-tools
chmod +x setup.sh
./setup.sh
```

### 2. Avvia MCP Server

```bash
source venv/bin/activate
python mcp_server/server.py --http
```

Server in ascolto su `http://localhost:8001`

### 3. Usa in Python

```python
import asyncio
from browser_agent.kimi_bridge import SimpleBrowser

async def main():
    async with SimpleBrowser() as browser:
        # Naviga a Oracle Cloud
        await browser.goto("https://cloud.oracle.com")
        
        # Screenshot
        screenshot = await browser.screenshot()
        
        # Click su Sign In
        await browser.click("Sign In")
        
        # Altri comandi...

asyncio.run(main())
```

---

## 🎯 Use Cases

### Login Oracle Cloud

```python
from browser_agent.kimi_bridge import KimiBrowserBridge

bridge = KimiBrowserBridge()
await bridge.start_session()

# Task pianificato automaticamente
task = bridge.plan_oracle_cloud_login(
    username="tuo@email.com"
)

result = await bridge.execute_task(task)
```

### Creare VM Automaticamente

```python
task = bridge.plan_create_vm()
result = await bridge.execute_task(task)
# Screenshot ad ogni step
```

### Task Custom

```python
from browser_agent.kimi_bridge import BrowserTask

task = BrowserTask(
    goal="Extract pricing from page",
    url="https://example.com/pricing",
    actions=[
        {"type": "wait", "seconds": 2},
        {"type": "scroll", "direction": "down"},
        {"type": "extract", "selector": ".price"}
    ]
)

result = await bridge.execute_task(task)
```

---

## 🛠️ Tools Disponibili

| Tool | Descrizione | Parametri |
|------|-------------|-----------|
| `navigate` | Naviga a URL | `url` |
| `click` | Click elemento | `selector`, `description` |
| `type` | Digita testo | `selector`, `text` |
| `screenshot` | Screenshot | `full_page` |
| `scroll` | Scroll pagina | `direction`, `amount` |
| `extract` | Estrai dati | `selector`, `attribute` |
| `wait` | Attesa | `seconds` |

---

## 🔌 MCP Protocol

Il **Model Context Protocol (MCP)** è lo standard del 2026 per connettere AI a tool esterni.

### Chiamata HTTP

```bash
curl -X POST http://localhost:8001/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "type": "execute",
    "tool": "navigate",
    "params": {"url": "https://cloud.oracle.com"}
  }'
```

### Lista Tools

```bash
curl http://localhost:8001/mcp/tools
```

---

## 🎭 Come le Big Tech

### OpenAI Operator Style
```python
# Piano generato automaticamente
task = bridge.plan_oracle_cloud_login()
result = await bridge.execute_task(task)
```

### Anthropic Computer Use Style
```python
# Vision-based element finding
element = await agent.find_element(
    description="Sign In button",
    selector_hints=["button:has-text('Sign In')"]
)
```

### Google Project Mariner Style
```python
# Multi-step complex task
orchestrator = AgentOrchestrator(agent)
results = await orchestrator.execute_task(
    goal="Create VM and configure security group",
    steps=generated_steps
)
```

---

## 🔒 Anti-Detection

Il browser agent include protezioni avanzate:

- ✅ **User-Agent reale** (Chrome 120)
- ✅ **Viewport realistico** (1920x1080)
- ✅ **WebDriver stealth** (`navigator.webdriver = undefined`)
- ✅ **Timezone & locale** corretti
- ✅ **Random delays** tra azioni

---

## 📊 Monitoring

### Logs

```bash
tail -f logs/agent.log
```

### Screenshot

Salvati automaticamente in `screenshots/`

### History

Ogni azione viene tracciata:

```python
for obs in agent.history:
    print(f"{obs.action.type}: {obs.success}")
```

---

## 🌟 Features 2026

| Feature | Status | Descrizione |
|---------|--------|-------------|
| Vision-based interaction | ✅ | Vede la pagina come un umano |
| Retry logic | ✅ | Riprova automaticamente su errore |
| Fallback selectors | ✅ | Multiple strategie di selezione |
| Screenshot analysis | ✅ | Ogni step documentato |
| MCP Standard | ✅ | Protocollo universale |
| Async/await | ✅ | Performance ottimale |

---

## 🚀 Esempi Avanzati

### Estrarre Dati da Tabella

```python
result = await bridge.execute_task(BrowserTask(
    goal="Extract all VM instances",
    url="https://cloud.oracle.com/compute/instances",
    actions=[
        {"type": "wait", "seconds": 3},
        {
            "type": "extract",
            "selector": "table.instances-table tr",
            "attribute": "textContent"
        }
    ]
))
```

### Multi-step Workflow

```python
steps = [
    {"type": "navigate", "url": "https://cloud.oracle.com"},
    {"type": "screenshot"},
    {"type": "click", "selector": "button.sign-in"},
    {"type": "wait", "seconds": 2},
    {"type": "type", "selector": "#username", "text": "user@example.com"},
    {"type": "click", "selector": "button.continue"},
    {"type": "screenshot"}
]

result = await orchestrator.execute_task(
    goal="Complete Oracle login flow",
    steps=steps
)
```

---

## 🔧 Troubleshooting

### Playwright not found

```bash
playwright install chromium
```

### Port 8001 busy

```bash
python mcp_server/server.py --http --port 8002
```

### Headless mode

```python
agent = BrowserAgent(headless=True)  # Senza GUI
```

---

## 📚 References

- [Anthropic Computer Use](https://www.anthropic.com/news/computer-use)
- [OpenAI Operator](https://openai.com/operator)
- [Google Project Mariner](https://deepmind.google/technologies/project-mariner/)
- [Model Context Protocol](https://modelcontextprotocol.io/)
- [Playwright](https://playwright.dev/)

---

**Built with ❤️ for the agentic AI era**

*2026 Edition - Big Tech Style*
