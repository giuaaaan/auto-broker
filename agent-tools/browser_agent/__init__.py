"""
Browser Agent Package
Big Tech Style Browser Automation
"""

from .agent import BrowserAgent, AgentOrchestrator, AgentAction, AgentObservation
from .kimi_bridge import KimiBrowserBridge, SimpleBrowser, BrowserTask

__all__ = [
    'BrowserAgent',
    'AgentOrchestrator',
    'AgentAction',
    'AgentObservation',
    'KimiBrowserBridge',
    'SimpleBrowser',
    'BrowserTask',
]
