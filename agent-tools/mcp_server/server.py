"""
🔌 MCP Server - Model Context Protocol
Standard 2026 per connessione AI ↔ Tools

Come Anthropic MCP, OpenAI Function Calling, Google A2A
"""

import asyncio
import json
import sys
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Definizione di un tool MCP"""
    name: str
    description: str
    parameters: Dict[str, Any]
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }


@dataclass
class MCPMessage:
    """Messaggio MCP"""
    role: str  # user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_results: Optional[List[Dict]] = None


class BrowserMCPServer:
    """
    Server MCP per controllo browser
    Permette a Kimi (o altri LLM) di usare il browser
    """
    
    def __init__(self):
        self.tools: Dict[str, MCPTool] = {}
        self.browser_agent = None
        self._register_tools()
        
    def _register_tools(self):
        """Registra i tool disponibili"""
        
        # Tool: navigate
        self.tools["navigate"] = MCPTool(
            name="navigate",
            description="Navigate to a URL",
            parameters={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL to navigate to"
                    }
                },
                "required": ["url"]
            }
        )
        
        # Tool: click
        self.tools["click"] = MCPTool(
            name="click",
            description="Click on an element",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector or XPath"
                    },
                    "description": {
                        "type": "string",
                        "description": "Human description of element"
                    }
                }
            }
        )
        
        # Tool: type
        self.tools["type"] = MCPTool(
            name="type",
            description="Type text into an input field",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "Input field selector"
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to type"
                    }
                },
                "required": ["selector", "text"]
            }
        )
        
        # Tool: screenshot
        self.tools["screenshot"] = MCPTool(
            name="screenshot",
            description="Take a screenshot of current page",
            parameters={
                "type": "object",
                "properties": {
                    "full_page": {
                        "type": "boolean",
                        "description": "Capture full page or viewport"
                    }
                }
            }
        )
        
        # Tool: scroll
        self.tools["scroll"] = MCPTool(
            name="scroll",
            description="Scroll the page",
            parameters={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down", "left", "right"]
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Pixels to scroll"
                    }
                }
            }
        )
        
        # Tool: extract
        self.tools["extract"] = MCPTool(
            name="extract",
            description="Extract data from page elements",
            parameters={
                "type": "object",
                "properties": {
                    "selector": {
                        "type": "string",
                        "description": "CSS selector for elements"
                    },
                    "attribute": {
                        "type": "string",
                        "description": "Attribute to extract (default: textContent)"
                    }
                }
            }
        )
        
        # Tool: wait
        self.tools["wait"] = MCPTool(
            name="wait",
            description="Wait for specified time or condition",
            parameters={
                "type": "object",
                "properties": {
                    "seconds": {
                        "type": "integer",
                        "description": "Seconds to wait"
                    }
                }
            }
        )
        
        logger.info(f"🔧 Registered {len(self.tools)} tools")
        
    def get_tools_list(self) -> List[Dict]:
        """Ritorna lista tool per LLM"""
        return [tool.to_dict() for tool in self.tools.values()]
    
    async def execute_tool(self, tool_name: str, params: Dict) -> Dict:
        """Esegue un tool"""
        logger.info(f"🔨 Executing tool: {tool_name} with {params}")
        
        if tool_name not in self.tools:
            return {"error": f"Tool {tool_name} not found"}
        
        try:
            # Qui integrare con BrowserAgent reale
            # Per ora simuliamo la risposta
            
            if tool_name == "navigate":
                return {
                    "success": True,
                    "url": params["url"],
                    "title": f"Page at {params['url']}",
                    "screenshot": "base64_placeholder..."
                }
                
            elif tool_name == "click":
                return {
                    "success": True,
                    "element": params.get("selector") or params.get("description"),
                    "new_url": None
                }
                
            elif tool_name == "type":
                return {
                    "success": True,
                    "field": params["selector"],
                    "text_entered": params["text"][:20] + "..."
                }
                
            elif tool_name == "screenshot":
                return {
                    "success": True,
                    "format": "png",
                    "base64": "iVBORw0KGgoAAAANSUhEUgAA...",
                    "width": 1920,
                    "height": 1080
                }
                
            elif tool_name == "scroll":
                return {
                    "success": True,
                    "direction": params.get("direction", "down"),
                    "amount": params.get("amount", 500)
                }
                
            elif tool_name == "extract":
                return {
                    "success": True,
                    "selector": params["selector"],
                    "count": 5,
                    "data": ["Item 1", "Item 2", "Item 3", "Item 4", "Item 5"]
                }
                
            elif tool_name == "wait":
                await asyncio.sleep(params.get("seconds", 1))
                return {
                    "success": True,
                    "waited_seconds": params.get("seconds", 1)
                }
                
        except Exception as e:
            logger.error(f"❌ Tool execution failed: {e}")
            return {"error": str(e)}
    
    async def process_request(self, request: Dict) -> Dict:
        """Processa richiesta dal LLM"""
        
        if request.get("type") == "list_tools":
            return {
                "type": "tools_list",
                "tools": self.get_tools_list()
            }
        
        elif request.get("type") == "execute":
            tool_name = request.get("tool")
            params = request.get("params", {})
            result = await self.execute_tool(tool_name, params)
            return {
                "type": "tool_result",
                "tool": tool_name,
                "result": result
            }
        
        elif request.get("type") == "chat":
            # Qui integrare con LLM per chat nativa
            return {
                "type": "chat_response",
                "content": "I can help you control the browser. Use the available tools."
            }
        
        else:
            return {"error": "Unknown request type"}
    
    async def run_stdio(self):
        """Modalità stdio (come MCP standard)"""
        logger.info("🚀 MCP Server started (stdio mode)")
        
        while True:
            try:
                # Leggi da stdin
                line = await asyncio.get_event_loop().run_in_executor(
                    None, sys.stdin.readline
                )
                
                if not line:
                    break
                    
                request = json.loads(line.strip())
                response = await self.process_request(request)
                
                # Scrivi su stdout
                print(json.dumps(response), flush=True)
                
            except json.JSONDecodeError as e:
                print(json.dumps({"error": f"Invalid JSON: {e}"}), flush=True)
            except Exception as e:
                print(json.dumps({"error": str(e)}), flush=True)
    
    async def run_http(self, host: str = "localhost", port: int = 8001):
        """Modalità HTTP server"""
        from aiohttp import web
        
        async def handle(request):
            try:
                body = await request.json()
                response = await self.process_request(body)
                return web.json_response(response)
            except Exception as e:
                return web.json_response({"error": str(e)}, status=500)
        
        async def handle_tools(request):
            return web.json_response({
                "tools": self.get_tools_list()
            })
        
        app = web.Application()
        app.router.add_post('/mcp', handle)
        app.router.add_get('/mcp/tools', handle_tools)
        
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        
        logger.info(f"🚀 MCP HTTP Server started on http://{host}:{port}")
        await site.start()
        
        # Mantieni vivo
        while True:
            await asyncio.sleep(3600)


# ==========================================
# MCP CLIENT (per Kimi)
# ==========================================

class MCPClient:
    """
    Client MCP per connettere Kimi al browser
    """
    
    def __init__(self, server_url: str = "http://localhost:8001"):
        self.server_url = server_url
        self.tools: List[Dict] = []
        
    async def connect(self):
        """Connetti al server MCP"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{self.server_url}/mcp/tools") as resp:
                data = await resp.json()
                self.tools = data.get("tools", [])
                logger.info(f"🔗 Connected to MCP server. {len(self.tools)} tools available")
                
    async def execute(self, tool_name: str, **params) -> Dict:
        """Esegue tool sul server"""
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.server_url}/mcp",
                json={"type": "execute", "tool": tool_name, "params": params}
            ) as resp:
                return await resp.json()
    
    def get_tools_prompt(self) -> str:
        """Genera prompt con descrizione tool per LLM"""
        prompt = "You have access to the following browser automation tools:\n\n"
        
        for tool in self.tools:
            prompt += f"## {tool['name']}\n"
            prompt += f"Description: {tool['description']}\n"
            prompt += f"Parameters: {json.dumps(tool['parameters'], indent=2)}\n\n"
        
        prompt += "\nTo use a tool, respond with:\n"
        prompt += '```json\n{"tool": "tool_name", "params": {"param": "value"}}\n```\n'
        
        return prompt


if __name__ == "__main__":
    import sys
    
    server = BrowserMCPServer()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--http":
        # Modalità HTTP
        asyncio.run(server.run_http())
    else:
        # Modalità stdio (MCP standard)
        asyncio.run(server.run_stdio())
