# =============================================================================
# Auto-Broker Mock Agents - Demo Mode
# Simula attività agenti AI in background (SARA, PAOLO, GIULIA)
# Invia update via WebSocket così la dashboard si anima
# =============================================================================

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MockAgentSimulator:
    """
    Simula l'attività degli agenti AI in demo mode.
    Crea eventi realistici che alimentano la dashboard.
    """
    
    def __init__(self, websocket_manager=None):
        self.websocket_manager = websocket_manager
        self.running = False
        self.tasks = []
        
        # Dati demo per simulazioni
        self.clients = [
            {"id": "CLI001", "name": "Rossi Srl", "city": "Milano"},
            {"id": "CLI002", "name": "Bianchi Spa", "city": "Roma"},
            {"id": "CLI003", "name": "Verdi & Co", "city": "Torino"},
            {"id": "CLI004", "name": "Neri Logistics", "city": "Bologna"},
            {"id": "CLI005", "name": "Gialli Trasporti", "city": "Napoli"},
        ]
        
        self.carriers = [
            {"id": "CAR001", "name": "Bartolini", "reliability": 0.94},
            {"id": "CAR002", "name": "DHL", "reliability": 0.97},
            {"id": "CAR003", "name": "SDA", "reliability": 0.89},
            {"id": "CAR004", "name": "TNT", "reliability": 0.92},
            {"id": "CAR005", "name": "GLS", "reliability": 0.90},
        ]
        
        self.lanes = [
            {"from": "Milano", "to": "Roma", "distance_km": 570},
            {"from": "Torino", "to": "Palermo", "distance_km": 1650},
            {"from": "Bologna", "to": "Napoli", "distance_km": 580},
            {"from": "Verona", "to": "Bari", "distance_km": 890},
            {"from": "Firenze", "to": "Genova", "distance_km": 230},
        ]
        
        logger.info("🤖 MockAgentSimulator initialized (Demo Mode)")
    
    async def start(self):
        """Avvia tutti i simulatori agenti"""
        if self.running:
            return
        
        self.running = True
        logger.info("🎮 Starting Mock Agent Simulators...")
        
        # Avvia simulatori con intervalli diversi
        self.tasks = [
            asyncio.create_task(self._sara_simulator()),      # Ogni 2 min
            asyncio.create_task(self._paolo_simulator()),     # Ogni 5 min
            asyncio.create_task(self._giulia_simulator()),    # Ogni 10 min
            asyncio.create_task(self._marco_simulator()),     # Ogni 3 min
            asyncio.create_task(self._anna_simulator()),      # Ogni 4 min
        ]
        
        logger.info("✅ All Mock Agent Simulators started")
    
    async def stop(self):
        """Ferma tutti i simulatori"""
        self.running = False
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        logger.info("🛑 Mock Agent Simulators stopped")
    
    # ==========================================================================
    # SARA - Acquisition Agent (Ogni 2 minuti)
    # ==========================================================================
    async def _sara_simulator(self):
        """Simula SARA che chiama nuovi lead"""
        while self.running:
            try:
                await asyncio.sleep(120)  # 2 minuti
                
                if not self.running:
                    break
                
                client = random.choice(self.clients)
                
                event = {
                    "type": "agent_activity",
                    "agent": "SARA",
                    "agent_name": "SARA (Acquisition)",
                    "icon": "📞",
                    "status": "completed",
                    "message": f"Called {client['name']} - Interested!",
                    "details": {
                        "client": client['name'],
                        "duration": f"{random.randint(2, 5)}m",
                        "outcome": "qualified",
                        "next_step": "Handover to MARCO"
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                    "mock": True
                }
                
                await self._broadcast(event)
                logger.info(f"📞 [MOCK SARA] Called {client['name']} - Success!")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"SARA simulator error: {e}")
    
    # ==========================================================================
    # MARCO - Qualification Agent (Ogni 3 minuti)
    # ==========================================================================
    async def _marco_simulator(self):
        """Simula MARCO che qualifica lead"""
        while self.running:
            try:
                await asyncio.sleep(180)  # 3 minuti
                
                if not self.running:
                    break
                
                client = random.choice(self.clients)
                volume = random.randint(500, 3000)
                score = random.randint(65, 95)
                
                event = {
                    "type": "agent_activity",
                    "agent": "MARCO",
                    "agent_name": "MARCO (Qualification)",
                    "icon": "🎯",
                    "status": "completed",
                    "message": f"Qualified {client['name']} - Score {score}/100",
                    "details": {
                        "client": client['name'],
                        "monthly_volume_kg": volume,
                        "qualification_score": score,
                        "qualified": score >= 70,
                        "preferred_lanes": random.sample(["MI-RO", "TO-BO", "NA-GE", "FI-GE"], 2)
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                    "mock": True
                }
                
                await self._broadcast(event)
                logger.info(f"🎯 [MOCK MARCO] Qualified {client['name']}: {score}/100")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"MARCO simulator error: {e}")
    
    # ==========================================================================
    # PAOLO - Carrier Failover Agent (Ogni 5 minuti)
    # ==========================================================================
    async def _paolo_simulator(self):
        """Simula PAOLO che gestisce failover carrier"""
        while self.running:
            try:
                await asyncio.sleep(300)  # 5 minuti
                
                if not self.running:
                    break
                
                carrier = random.choice(self.carriers)
                
                # Simula problema carrier
                if carrier["reliability"] < 0.92:
                    severity = random.choice(["warning", "critical"])
                    
                    event = {
                        "type": "carrier_alert",
                        "agent": "PAOLO",
                        "agent_name": "PAOLO (Carrier Intelligence)",
                        "icon": "🚨",
                        "status": "active",
                        "severity": severity,
                        "message": f"{carrier['name']} performance degraded",
                        "details": {
                            "carrier": carrier['name'],
                            "carrier_id": carrier['id'],
                            "issue": "On-time rate dropped to 88%",
                            "affected_shipments": random.randint(1, 5),
                            "action_taken": "Initiating failover protocol",
                            "alternative_carrier": random.choice([c for c in self.carriers if c['id'] != carrier['id']])['name']
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                        "mock": True
                    }
                    
                    await self._broadcast(event)
                    logger.info(f"🚨 [MOCK PAOLO] Alert: {carrier['name']} - Failover initiated")
                    
                    # Dopo 30 secondi, simula risoluzione
                    await asyncio.sleep(30)
                    
                    resolution = {
                        "type": "carrier_alert_resolved",
                        "agent": "PAOLO",
                        "agent_name": "PAOLO (Carrier Intelligence)",
                        "icon": "✅",
                        "status": "resolved",
                        "message": f"Failover completed for {carrier['name']}",
                        "details": {
                            "carrier": carrier['name'],
                            "shipments_transferred": event['details']['affected_shipments'],
                            "new_carrier": event['details']['alternative_carrier'],
                            "downtime_minutes": random.randint(2, 8)
                        },
                        "timestamp": datetime.utcnow().isoformat(),
                        "mock": True
                    }
                    
                    await self._broadcast(resolution)
                    logger.info(f"✅ [MOCK PAOLO] Failover resolved for {carrier['name']}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"PAOLO simulator error: {e}")
    
    # ==========================================================================
    # GIULIA - Dispute Resolution Agent (Ogni 10 minuti)
    # ==========================================================================
    async def _giulia_simulator(self):
        """Simula GIULIA che risolve dispute"""
        while self.running:
            try:
                await asyncio.sleep(600)  # 10 minuti
                
                if not self.running:
                    break
                
                dispute_types = ["damaged_goods", "late_delivery", "quantity_mismatch"]
                dispute_type = random.choice(dispute_types)
                
                confidence = random.randint(70, 95)
                
                event = {
                    "type": "dispute_resolved",
                    "agent": "GIULIA",
                    "agent_name": "GIULIA (Dispute Resolution)",
                    "icon": "⚖️",
                    "status": "resolved",
                    "message": f"Dispute resolved: {dispute_type.replace('_', ' ').title()}",
                    "details": {
                        "dispute_id": f"DISP-{random.randint(1000, 9999)}",
                        "type": dispute_type,
                        "confidence_score": confidence,
                        "decision": random.choice(["customer_favor", "carrier_favor", "split"]),
                        "refund_amount": random.choice([0, 50, 120, 250]),
                        "resolution_time_minutes": random.randint(5, 30),
                        "evidence_analyzed": ["POD", "tracking_data", "photos"]
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                    "mock": True
                }
                
                await self._broadcast(event)
                logger.info(f"⚖️ [MOCK GIULIA] Dispute resolved: {dispute_type} ({confidence}% confidence)")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"GIULIA simulator error: {e}")
    
    # ==========================================================================
    # ANNA - Operations Agent (Ogni 4 minuti)
    # ==========================================================================
    async def _anna_simulator(self):
        """Simula ANNA che gestisce operazioni spedizioni"""
        while self.running:
            try:
                await asyncio.sleep(240)  # 4 minuti
                
                if not self.running:
                    break
                
                events = [
                    {
                        "type": "shipment_update",
                        "agent": "ANNA",
                        "agent_name": "ANNA (Operations)",
                        "icon": "📦",
                        "status": "picked_up",
                        "message": "Shipment picked up from warehouse",
                    },
                    {
                        "type": "shipment_update",
                        "agent": "ANNA",
                        "agent_name": "ANNA (Operations)",
                        "icon": "🚚",
                        "status": "in_transit",
                        "message": "Shipment in transit to destination",
                    },
                    {
                        "type": "shipment_update",
                        "agent": "ANNA",
                        "agent_name": "ANNA (Operations)",
                        "icon": "✅",
                        "status": "delivered",
                        "message": "Shipment delivered successfully",
                    }
                ]
                
                event = random.choice(events)
                event["details"] = {
                    "shipment_id": f"SHIP-{random.randint(10000, 99999)}",
                    "carrier": random.choice(self.carriers)["name"],
                    "origin": random.choice(self.lanes)["from"],
                    "destination": random.choice(self.lanes)["to"],
                    "eta": (datetime.utcnow() + timedelta(hours=random.randint(2, 48))).isoformat()
                }
                event["timestamp"] = datetime.utcnow().isoformat()
                event["mock"] = True
                
                await self._broadcast(event)
                logger.info(f"📦 [MOCK ANNA] {event['message']}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"ANNA simulator error: {e}")
    
    # ==========================================================================
    # Helper Methods
    # ==========================================================================
    async def _broadcast(self, event: Dict[str, Any]):
        """Invia evento via WebSocket se disponibile"""
        if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast'):
            try:
                await self.websocket_manager.broadcast(event)
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")
        else:
            # Log per debug se WebSocket non disponibile
            logger.debug(f"Mock event (no WebSocket): {event['type']}")


# Singleton
_agent_simulator = None


def get_agent_simulator(websocket_manager=None) -> MockAgentSimulator:
    global _agent_simulator
    if _agent_simulator is None:
        _agent_simulator = MockAgentSimulator(websocket_manager)
    return _agent_simulator
