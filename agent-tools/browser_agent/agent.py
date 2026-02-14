"""
🌐 Auto-Broker Browser Agent
Big Tech Style - Computer Use Agent (2026)

Inspired by:
- Anthropic Computer Use API
- OpenAI Operator
- Google Project Mariner
- Model Context Protocol (MCP)
"""

import asyncio
import base64
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import logging

# Playwright per browser automation
try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
except ImportError:
    print("⚠️  Playwright not installed. Run: pip install playwright && playwright install")
    raise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class AgentAction:
    """Singola azione da eseguire"""
    type: str  # click, type, navigate, screenshot, scroll, wait
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class AgentObservation:
    """Risultato di un'azione"""
    action: AgentAction
    success: bool
    screenshot: Optional[str] = None  # Base64
    html: Optional[str] = None
    error: Optional[str] = None
    url: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class BrowserAgent:
    """
    Agent intelligente per controllo browser
    Come Operator di OpenAI o Computer Use di Anthropic
    """
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.history: List[AgentObservation] = []
        self.max_history = 50
        
    async def start(self):
        """Avvia il browser"""
        self.playwright = await async_playwright().start()
        
        # Configurazione avanzata come le Big Tech
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process',
            ]
        )
        
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            locale='it-IT',
            timezone_id='Europe/Rome',
        )
        
        self.page = await self.context.new_page()
        
        # Anti-detection
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        logger.info("🌐 Browser Agent started (Big Tech Mode)")
        
    async def stop(self):
        """Ferma il browser"""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info("🌐 Browser Agent stopped")
        
    async def execute(self, action: AgentAction) -> AgentObservation:
        """Esegue un'azione sul browser"""
        observation = AgentObservation(action=action, success=False)
        
        try:
            if action.type == "navigate":
                await self._navigate(action.params)
                
            elif action.type == "click":
                await self._click(action.params)
                
            elif action.type == "type":
                await self._type(action.params)
                
            elif action.type == "screenshot":
                await self._screenshot(action.params)
                
            elif action.type == "scroll":
                await self._scroll(action.params)
                
            elif action.type == "wait":
                await self._wait(action.params)
                
            elif action.type == "extract":
                await self._extract(action.params)
                
            observation.success = True
            observation.url = self.page.url
            
            # Screenshot automatico dopo azione
            screenshot_bytes = await self.page.screenshot(full_page=False)
            observation.screenshot = base64.b64encode(screenshot_bytes).decode('utf-8')
            
        except Exception as e:
            observation.error = str(e)
            logger.error(f"❌ Action failed: {action.type} - {e}")
            
        # Salva history
        self.history.append(observation)
        if len(self.history) > self.max_history:
            self.history.pop(0)
            
        return observation
    
    async def _navigate(self, params: Dict):
        """Naviga a URL"""
        url = params.get("url")
        await self.page.goto(url, wait_until="networkidle")
        logger.info(f"🧭 Navigated to: {url}")
        
    async def _click(self, params: Dict):
        """Click su elemento"""
        selector = params.get("selector")
        coordinates = params.get("coordinates")
        
        if selector:
            await self.page.click(selector)
        elif coordinates:
            await self.page.mouse.click(coordinates["x"], coordinates["y"])
            
        logger.info(f"🖱️  Clicked: {selector or coordinates}")
        
    async def _type(self, params: Dict):
        """Digita testo"""
        selector = params.get("selector")
        text = params.get("text")
        clear_first = params.get("clear", True)
        
        if clear_first:
            await self.page.fill(selector, "")
        await self.page.type(selector, text, delay=50)
        logger.info(f"⌨️  Typed: {text[:30]}...")
        
    async def _screenshot(self, params: Dict):
        """Screenshot"""
        path = params.get("path")
        if path:
            await self.page.screenshot(path=path, full_page=params.get("full_page", False))
            logger.info(f"📸 Screenshot saved: {path}")
            
    async def _scroll(self, params: Dict):
        """Scroll pagina"""
        direction = params.get("direction", "down")
        amount = params.get("amount", 500)
        
        if direction == "down":
            await self.page.evaluate(f"window.scrollBy(0, {amount})")
        elif direction == "up":
            await self.page.evaluate(f"window.scrollBy(0, -{amount})")
            
        logger.info(f"📜 Scrolled {direction}")
        
    async def _wait(self, params: Dict):
        """Attesa"""
        seconds = params.get("seconds", 1)
        await asyncio.sleep(seconds)
        logger.info(f"⏱️  Waited {seconds}s")
        
    async def _extract(self, params: Dict):
        """Estrae dati dalla pagina"""
        selector = params.get("selector")
        attribute = params.get("attribute", "textContent")
        
        elements = await self.page.query_selector_all(selector)
        data = []
        for el in elements:
            if attribute == "textContent":
                text = await el.text_content()
                data.append(text.strip())
            else:
                attr = await el.get_attribute(attribute)
                data.append(attr)
                
        logger.info(f"📊 Extracted {len(data)} elements")
        return data
    
    async def get_page_info(self) -> Dict:
        """Informazioni sulla pagina corrente"""
        return {
            "url": self.page.url,
            "title": await self.page.title(),
            "viewport": await self.page.viewport_size(),
        }
        
    async def find_element(self, description: str, selector_hints: List[str] = None) -> Optional[Dict]:
        """
        Trova elemento usando descrizione testuale (AI-powered)
        Come Computer Use di Anthropic
        """
        # Prima prova selector hints se forniti
        if selector_hints:
            for hint in selector_hints:
                try:
                    element = await self.page.query_selector(hint)
                    if element:
                        bbox = await element.bounding_box()
                        return {
                            "selector": hint,
                            "found": True,
                            "bounding_box": bbox
                        }
                except:
                    continue
                    
        # Altrimenti cerca per testo
        try:
            # XPath per testo contenente descrizione
            xpath = f"//*[contains(text(), '{description}')]"
            element = await self.page.query_selector(f"xpath={xpath}")
            if element:
                bbox = await element.bounding_box()
                return {
                    "selector": f"xpath={xpath}",
                    "found": True,
                    "bounding_box": bbox
                }
        except:
            pass
            
        return {"found": False}


class AgentOrchestrator:
    """
    Orchestratore che pianifica ed esegue task complessi
    Come Operator di OpenAI o Project Mariner di Google
    """
    
    def __init__(self, agent: BrowserAgent):
        self.agent = agent
        self.planner = None  # Qui collegare LLM per pianificazione
        
    async def execute_task(self, goal: str, steps: List[Dict] = None) -> List[AgentObservation]:
        """
        Esegue un task complesso
        
        Args:
            goal: Obiettivo in linguaggio naturale
            steps: Passi predefiniti (opzionale)
        """
        logger.info(f"🎯 Task: {goal}")
        
        if steps is None:
            # Qui integrare LLM per generare steps
            steps = self._plan_steps(goal)
            
        observations = []
        
        for i, step in enumerate(steps, 1):
            logger.info(f"📍 Step {i}/{len(steps)}: {step.get('reason', step['action'])}")
            
            action = AgentAction(
                type=step['action'],
                params=step.get('params', {}),
                reason=step.get('reason', '')
            )
            
            observation = await self.agent.execute(action)
            observations.append(observation)
            
            if not observation.success:
                logger.error(f"❌ Step {i} failed: {observation.error}")
                # Qui retry logic o adattamento come fanno le Big Tech
                break
                
        return observations
    
    def _plan_steps(self, goal: str) -> List[Dict]:
        """
        Pianifica passi per raggiungere l'obiettivo
        In produzione: usa LLM (GPT-4, Claude, Kimi)
        """
        # Esempio: task "accedi a oracle cloud"
        if "oracle" in goal.lower() and "cloud" in goal.lower():
            return [
                {
                    "action": "navigate",
                    "params": {"url": "https://cloud.oracle.com"},
                    "reason": "Navigate to Oracle Cloud login"
                },
                {
                    "action": "screenshot",
                    "params": {},
                    "reason": "Capture login page"
                }
            ]
        
        # Default: naviga all'URL
        return [
            {
                "action": "navigate",
                "params": {"url": goal if goal.startswith("http"): "https://" + goal},
                "reason": f"Navigate to {goal}"
            }
        ]


# ==========================================
# USAGE EXAMPLES
# ==========================================

async def example_oracle_login():
    """Esempio: Accedi a Oracle Cloud"""
    agent = BrowserAgent(headless=False)
    await agent.start()
    
    try:
        # Naviga a Oracle
        obs = await agent.execute(AgentAction(
            type="navigate",
            params={"url": "https://cloud.oracle.com"},
            reason="Open Oracle Cloud"
        ))
        
        if obs.success:
            print(f"✅ Page loaded: {obs.url}")
            
            # Trova bottone Sign In
            element = await agent.find_element("Sign In", ["text=Sign In", "button:has-text('Sign In')"])
            print(f"Sign In button: {element}")
            
            # Screenshot
            await agent.execute(AgentAction(
                type="screenshot",
                params={"path": "oracle_cloud.png"}
            ))
            
    finally:
        await agent.stop()


async def example_complex_task():
    """Esempio: Task complesso con orchestrator"""
    agent = BrowserAgent(headless=False)
    orchestrator = AgentOrchestrator(agent)
    
    await agent.start()
    
    try:
        # Definisci task
        steps = [
            {
                "action": "navigate",
                "params": {"url": "https://github.com/giuaaaan/auto-broker"},
                "reason": "Open repository"
            },
            {
                "action": "wait",
                "params": {"seconds": 2},
                "reason": "Wait for load"
            },
            {
                "action": "screenshot",
                "params": {"path": "repo.png", "full_page": True},
                "reason": "Capture repository"
            }
        ]
        
        results = await orchestrator.execute_task(
            goal="Open auto-broker repo and screenshot",
            steps=steps
        )
        
        print(f"✅ Task completed: {len(results)} steps executed")
        
    finally:
        await agent.stop()


if __name__ == "__main__":
    # Esegui esempio
    asyncio.run(example_oracle_login())
