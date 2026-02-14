#!/bin/bash
# =============================================================================
# Auto-Broker Agent Tools Setup - Big Tech Style 2026
# Installazione automatica Browser Agent + MCP Server
# =============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║     🤖 Auto-Broker Agent Tools - Big Tech Edition 2026        ║"
echo "║                                                               ║"
echo "║  Inspired by:                                                 ║"
echo "║  • OpenAI Operator                                            ║"
echo "║  • Anthropic Computer Use                                     ║"
echo "║  • Google Project Mariner                                     ║"
echo "║  • Model Context Protocol (MCP)                               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.9+${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${GREEN}✅ Python version: $PYTHON_VERSION${NC}"

# Create virtual environment
echo -e "${BLUE}📦 Creating virtual environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip install playwright aiohttp

# Install Playwright browsers
echo -e "${BLUE}🌐 Installing Playwright browsers...${NC}"
playwright install chromium

# Create directories
mkdir -p screenshots logs

echo -e "${GREEN}"
echo "✅ Installation complete!"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  USAGE:"
echo ""
echo "  1. Start MCP Server (Terminal 1):"
echo "     source venv/bin/activate"
echo "     python mcp_server/server.py --http"
echo ""
echo "  2. Run Browser Agent (Terminal 2):"
echo "     source venv/bin/activate"
echo "     python browser_agent/agent.py"
echo ""
echo "  3. Use in Python:"
echo "     from browser_agent.kimi_bridge import SimpleBrowser"
echo "     async with SimpleBrowser() as browser:"
echo "         await browser.goto('https://cloud.oracle.com')"
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo -e "${NC}"

# Make scripts executable
chmod +x *.sh 2>/dev/null || true

echo -e "${YELLOW}🚀 Ready to browse like Big Tech!${NC}"
