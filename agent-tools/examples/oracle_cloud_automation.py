"""
🌐 Oracle Cloud Automation Example
Crea VM ARM Ampere A1 automaticamente

Come farebbe OpenAI Operator o Claude Computer Use
"""

import asyncio
import sys
sys.path.insert(0, '..')

from browser_agent.kimi_bridge import KimiBrowserBridge, BrowserTask


async def create_oracle_vm():
    """
    Workflow completo per creare VM su Oracle Cloud
    """
    print("🚀 Starting Oracle Cloud VM Creation...")
    print("=" * 60)
    
    bridge = KimiBrowserBridge()
    await bridge.start_session()
    
    try:
        # Step 1: Login
        print("\n📍 Step 1: Navigate to Oracle Cloud")
        task = BrowserTask(
            goal="Navigate to Oracle Cloud login",
            url="https://www.oracle.com/cloud/sign-in.html",
            actions=[
                {"type": "wait", "seconds": 3},
                {"type": "screenshot"}
            ]
        )
        
        result = await bridge.execute_task(task)
        if not result['success']:
            print("❌ Failed to load Oracle Cloud")
            return
            
        print("✅ Oracle Cloud loaded")
        print(f"📸 Screenshot captured: {len(result['results'])} steps")
        
        # Step 2: Find and click Sign In
        print("\n📍 Step 2: Click Sign In")
        task = BrowserTask(
            goal="Click Sign In button",
            actions=[
                {
                    "type": "click",
                    "selector": "a:has-text('Sign in to Oracle Cloud')"
                },
                {"type": "wait", "seconds": 2},
                {"type": "screenshot"}
            ]
        )
        
        result = await bridge.execute_task(task)
        print("✅ Sign In clicked")
        
        # Step 3: Enter credentials (manual or automated)
        print("\n📍 Step 3: Login Form")
        print("⚠️  At this point, you should manually enter credentials")
        print("   or configure the bridge with your username/password")
        
        # Screenshot per vedere il form
        task = BrowserTask(
            goal="Capture login form",
            actions=[
                {"type": "wait", "seconds": 5},
                {"type": "screenshot"}
            ]
        )
        await bridge.execute_task(task)
        
        print("📸 Login form captured - check screenshots/")
        
        # Attendi login manuale
        input("\n👉 Premi ENTER dopo aver fatto login manuale...")
        
        # Step 4: Navigate to Compute Instances
        print("\n📍 Step 4: Navigate to Compute")
        task = BrowserTask(
            goal="Go to Compute Instances",
            url="https://cloud.oracle.com/compute/instances",
            actions=[
                {"type": "wait", "seconds": 4},
                {"type": "screenshot"}
            ]
        )
        
        result = await bridge.execute_task(task)
        print("✅ Compute instances page loaded")
        
        # Step 5: Click Create Instance
        print("\n📍 Step 5: Create Instance")
        task = BrowserTask(
            goal="Click Create Instance button",
            actions=[
                {
                    "type": "click",
                    "selector": "button:has-text('Create instance')"
                },
                {"type": "wait", "seconds": 3},
                {"type": "screenshot"}
            ]
        )
        
        result = await bridge.execute_task(task)
        print("✅ Create instance form opened")
        
        # Step 6: Configure VM
        print("\n📍 Step 6: Configure VM")
        task = BrowserTask(
            goal="Configure ARM Ampere A1 VM",
            actions=[
                # Nome VM
                {
                    "type": "type",
                    "selector": "input[name='display-name']",
                    "text": "auto-broker-arm-vm"
                },
                
                # Selezione compartment (default)
                {"type": "wait", "seconds": 1},
                
                # Cambia shape
                {
                    "type": "click",
                    "selector": "button:has-text('Change shape')"
                },
                {"type": "wait", "seconds": 2},
                
                # Seleziona ARM
                {
                    "type": "click",
                    "selector": "text=Ampere"
                },
                {"type": "wait", "seconds": 1},
                
                # Seleziona VM.Standard.A1.Flex
                {
                    "type": "click",
                    "selector": "text=VM.Standard.A1.Flex"
                },
                {"type": "wait", "seconds": 1},
                
                # Conferma shape
                {
                    "type": "click",
                    "selector": "button:has-text('Select shape')"
                },
                
                # Screenshot configurazione
                {"type": "wait", "seconds": 2},
                {"type": "screenshot"}
            ]
        )
        
        result = await bridge.execute_task(task)
        print("✅ VM configured")
        
        # Step 7: Networking
        print("\n📍 Step 7: Configure Networking")
        print("   ⚠️  Configure SSH key and networking...")
        
        task = BrowserTask(
            goal="Configure networking",
            actions=[
                {"type": "wait", "seconds": 2},
                {
                    "type": "scroll",
                    "direction": "down",
                    "amount": 500
                },
                {"type": "screenshot"}
            ]
        )
        
        await bridge.execute_task(task)
        
        print("\n" + "=" * 60)
        print("✅ Automation completed!")
        print("📸 Check screenshots/ folder for visual documentation")
        print("\n⚠️  Note: This demo stops before actual VM creation")
        print("   to prevent accidental charges.")
        print("   To complete creation, manually click 'Create'")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n🔚 Session completed")


async def quick_oracle_check():
    """
    Versione rapida: solo screenshot della homepage
    """
    print("🚀 Quick Oracle Cloud Check")
    print("=" * 60)
    
    bridge = KimiBrowserBridge()
    await bridge.start_session()
    
    task = BrowserTask(
        goal="Check Oracle Cloud homepage",
        url="https://cloud.oracle.com",
        actions=[
            {"type": "wait", "seconds": 3},
            {"type": "screenshot"}
        ]
    )
    
    result = await bridge.execute_task(task)
    
    if result['success']:
        print("✅ Successfully loaded Oracle Cloud")
        print("📸 Screenshot saved to screenshots/")
        print(f"   Steps executed: {result['steps']}")
    else:
        print("❌ Failed to load page")
        
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Oracle Cloud Automation')
    parser.add_argument('--full', action='store_true', help='Full VM creation workflow')
    parser.add_argument('--quick', action='store_true', help='Quick homepage check')
    
    args = parser.parse_args()
    
    if args.full:
        asyncio.run(create_oracle_vm())
    else:
        asyncio.run(quick_oracle_check())
