"""
🎭 Kimi Bridge - Connettore per Auto-Broker
Permette a Kimi (me stesso) di controllare il browser

Architettura:
Kimi → MCP Client → MCP Server → Browser Agent → Playwright → Browser
"""

import asyncio
import json
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class BrowserTask:
    """Task da eseguire sul browser"""
    goal: str
    url: Optional[str] = None
    actions: List[Dict] = None
    screenshot_each_step: bool = True


class KimiBrowserBridge:
    """
    Bridge che permette a Kimi di controllare il browser
    Come Operator di OpenAI o Claude Computer Use
    """
    
    def __init__(self, mcp_server_url: str = "http://localhost:8001"):
        self.server_url = mcp_server_url
        self.session_history: List[Dict] = []
        self.current_page = None
        
    async def start_session(self):
        """Avvia una nuova sessione browser"""
        # Esegui il browser agent in background
        import subprocess
        
        self.process = subprocess.Popen(
            ["python", "-m", "browser_agent.agent"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        await asyncio.sleep(2)  # Attendi avvio
        print("🌐 Browser session started")
        
    async def execute_task(self, task: BrowserTask) -> Dict:
        """
        Esegue un task complesso sul browser
        
        Example:
            task = BrowserTask(
                goal="Login to Oracle Cloud",
                url="https://cloud.oracle.com",
                actions=[
                    {"type": "screenshot"},
                    {"type": "find", "text": "Sign In"},
                    {"type": "click", "selector": "button.sign-in"}
                ]
            )
            result = await bridge.execute_task(task)
        """
        print(f"🎯 Task: {task.goal}")
        
        results = []
        
        # Naviga all'URL se specificato
        if task.url:
            result = await self._navigate(task.url)
            results.append(result)
            
        # Esegui azioni
        if task.actions:
            for action in task.actions:
                result = await self._execute_action(action)
                results.append(result)
                
                if task.screenshot_each_step:
                    screenshot = await self._screenshot()
                    result["screenshot"] = screenshot
                    
        return {
            "success": all(r.get("success", False) for r in results),
            "task": task.goal,
            "steps": len(results),
            "results": results
        }
    
    async def _navigate(self, url: str) -> Dict:
        """Naviga a URL"""
        return await self._call_mcp("navigate", {"url": url})
    
    async def _click(self, selector: str) -> Dict:
        """Click su elemento"""
        return await self._call_mcp("click", {"selector": selector})
    
    async def _type(self, selector: str, text: str) -> Dict:
        """Digita testo"""
        return await self._call_mcp("type", {"selector": selector, "text": text})
    
    async def _screenshot(self) -> str:
        """Screenshot"""
        result = await self._call_mcp("screenshot", {})
        return result.get("base64", "")
    
    async def _execute_action(self, action: Dict) -> Dict:
        """Esegue azione generica"""
        action_type = action.get("type")
        
        if action_type == "navigate":
            return await self._navigate(action["url"])
        elif action_type == "click":
            return await self._click(action["selector"])
        elif action_type == "type":
            return await self._type(action["selector"], action["text"])
        elif action_type == "screenshot":
            return {"success": True, "screenshot": await self._screenshot()}
        elif action_type == "wait":
            await asyncio.sleep(action.get("seconds", 1))
            return {"success": True, "waited": action.get("seconds", 1)}
        else:
            return await self._call_mcp(action_type, action)
    
    async def _call_mcp(self, tool: str, params: Dict) -> Dict:
        """Chiama server MCP"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.server_url}/mcp",
                json={"type": "execute", "tool": tool, "params": params}
            ) as resp:
                data = await resp.json()
                return data.get("result", {})
    
    def plan_oracle_cloud_login(self, username: str = None, password: str = None) -> BrowserTask:
        """
        Pianifica task per login Oracle Cloud
        Come farebbe Operator di OpenAI
        """
        actions = [
            {"type": "screenshot"},  # Vedi pagina iniziale
            {"type": "wait", "seconds": 2},
        ]
        
        # Cerca bottone Sign In
        actions.append({
            "type": "click",
            "selector": "button:has-text('Sign In')",
            "fallback_selectors": ["a:has-text('Sign In')", "[data-testid='signin-button']"]
        })
        
        if username:
            actions.append({
                "type": "type",
                "selector": "input[name='username']",
                "text": username
            })
            
        return BrowserTask(
            goal="Login to Oracle Cloud",
            url="https://cloud.oracle.com",
            actions=actions
        )
    
    def plan_create_vm(self) -> BrowserTask:
        """
        Pianifica task per creare VM su Oracle Cloud
        """
        return BrowserTask(
            goal="Create ARM Ampere A1 VM on Oracle Cloud",
            url="https://cloud.oracle.com/compute/instances",
            actions=[
                {"type": "wait", "seconds": 3},
                {"type": "screenshot"},
                {
                    "type": "click",
                    "selector": "button:has-text('Create Instance')"
                },
                {"type": "wait", "seconds": 2},
                {
                    "type": "type",
                    "selector": "input[name='display-name']",
                    "text": "auto-broker-vm"
                },
                # Selezione shape ARM
                {
                    "type": "click",
                    "selector": "button:has-text('Change Shape')"
                },
                {"type": "wait", "seconds": 1},
                {
                    "type": "click",
                    "selector": "text=VM.Standard.A1.Flex"
                },
                {"type": "screenshot"}
            ]
        )


# ==========================================
# INTERFACCIA SEMPLICE PER KIMI
# ==========================================

class SimpleBrowser:
    """
    Interfaccia semplificata per uso immediato
    """
    
    def __init__(self):
        self.bridge = None
        
    async def __aenter__(self):
        self.bridge = KimiBrowserBridge()
        await self.bridge.start_session()
        return self
        
    async def __aexit__(self, *args):
        pass  # Cleanup
        
    async def goto(self, url: str):
        """Vai a URL"""
        result = await self.bridge.execute_task(
            BrowserTask(goal=f"Navigate to {url}", url=url)
        )
        return result
        
    async def click(self, text: str):
        """Click su elemento con testo"""
        task = BrowserTask(
            goal=f"Click on {text}",
            actions=[{
                "type": "click",
                "selector": f"text={text}"
            }]
        )
        return await self.bridge.execute_task(task)
        
    async def screenshot(self) -> str:
        """Screenshot"""
        result = await self.bridge._screenshot()
        return result
        
    async def oracle_login(self):
        """Task completo: login Oracle"""
        task = self.bridge.plan_oracle_cloud_login()
        return await self.bridge.execute_task(task)


# ==========================================
# ESEMPIO USO
# ==========================================

async def example_usage():
    """Come usare il sistema"""
    
    # Metodo 1: Semplice
    async with SimpleBrowser() as browser:
        await browser.goto("https://cloud.oracle.com")
        await browser.click("Sign In")
        screenshot = await browser.screenshot()
        print(f"Screenshot: {screenshot[:50]}...")
    
    # Metodo 2: Task pianificato
    bridge = KimiBrowserBridge()
    await bridge.start_session()
    
    task = bridge.plan_oracle_cloud_login()
    result = await bridge.execute_task(task)
    
    print(f"✅ Task completed: {result['success']}")
    print(f"📸 Screenshot available: {len(result['results'])} steps")


if __name__ == "__main__":
    asyncio.run(example_usage())
