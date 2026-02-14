# =============================================================================
# Auto-Broker Mock Revenue Generator - Demo Mode
# Simula revenue che sale costantemente per demo visuale
# =============================================================================

import asyncio
import random
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class MockRevenueGenerator:
    """
    Generatore di revenue fittizia per demo mode.
    Crea spedizioni e revenue in tempo reale così la dashboard
    mostra grafici che salgono e la mappa si popola.
    """
    
    def __init__(self, db_session_factory=None, websocket_manager=None):
        self.db_session_factory = db_session_factory
        self.websocket_manager = websocket_manager
        self.running = False
        self.task = None
        
        # Stato revenue
        self.monthly_revenue = 4850.0  # Inizia da Livello 2
        self.total_shipments = 8
        self.active_shipments = 5
        
        # Dati per generazione
        self.clients = [
            {"name": "Rossi Srl", "city": "Milano", "lat": 45.4642, "lon": 9.1900},
            {"name": "Bianchi Spa", "city": "Roma", "lat": 41.9028, "lon": 12.4964},
            {"name": "Verdi & Co", "city": "Torino", "lat": 45.0703, "lon": 7.6869},
            {"name": "Neri Logistics", "city": "Bologna", "lat": 44.4949, "lon": 11.3426},
            {"name": "Gialli Trasporti", "city": "Napoli", "lat": 40.8518, "lon": 14.2681},
            {"name": "Blu Cargo", "city": "Firenze", "lat": 43.7696, "lon": 11.2558},
            {"name": "Viola Freight", "city": "Verona", "lat": 45.4384, "lon": 10.9916},
            {"name": "Arancio Ship", "city": "Bari", "lat": 41.1171, "lon": 16.8719},
        ]
        
        self.carriers = [
            {"id": "BRT", "name": "Bartolini", "color": "#ef4444"},
            {"id": "DHL", "name": "DHL Express", "color": "#eab308"},
            {"id": "SDA", "name": "SDA", "color": "#3b82f6"},
            {"id": "TNT", "name": "TNT", "color": "#f97316"},
        ]
        
        self.lanes = [
            {"from": "Milano", "to": "Roma", "from_lat": 45.4642, "from_lon": 9.1900, "to_lat": 41.9028, "to_lon": 12.4964, "distance": 570},
            {"from": "Torino", "to": "Palermo", "from_lat": 45.0703, "from_lon": 7.6869, "to_lat": 38.1157, "to_lon": 13.3615, "distance": 1650},
            {"from": "Bologna", "to": "Napoli", "from_lat": 44.4949, "from_lon": 11.3426, "to_lat": 40.8518, "to_lon": 14.2681, "distance": 580},
            {"from": "Verona", "to": "Bari", "from_lat": 45.4384, "from_lon": 10.9916, "to_lat": 41.1171, "to_lon": 16.8719, "distance": 890},
            {"from": "Firenze", "to": "Genova", "from_lat": 43.7696, "from_lon": 11.2558, "to_lat": 44.4056, "to_lon": 8.9463, "distance": 230},
            {"from": "Roma", "to": "Milano", "from_lat": 41.9028, "from_lon": 12.4964, "to_lat": 45.4642, "to_lon": 9.1900, "distance": 570},
            {"from": "Napoli", "to": "Torino", "from_lat": 40.8518, "from_lon": 14.2681, "to_lat": 45.0703, "to_lon": 7.6869, "distance": 890},
        ]
        
        # Tracciamento spedizioni attive (per GPS)
        self.active_tracking: Dict[str, Any] = {}
        
        logger.info("💰 MockRevenueGenerator initialized (Demo Mode)")
    
    async def start(self):
        """Avvia il generatore"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._revenue_loop())
        
        # Avvia anche il tracker GPS
        asyncio.create_task(self._gps_loop())
        
        logger.info("💰 MockRevenueGenerator started (revenue every 30s)")
    
    async def stop(self):
        """Ferma il generatore"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("💰 MockRevenueGenerator stopped")
    
    async def _revenue_loop(self):
        """Loop principale - genera revenue ogni 30 secondi"""
        while self.running:
            try:
                await asyncio.sleep(30)  # Ogni 30 secondi
                
                if not self.running:
                    break
                
                # Genera revenue casuale tra €50 e €300
                revenue = round(random.uniform(50, 300), 2)
                self.monthly_revenue += revenue
                
                # Decidi se creare nuova spedizione o aggiornare esistente
                if random.random() < 0.7:  # 70% nuova spedizione
                    await self._create_new_shipment(revenue)
                else:
                    await self._update_existing_shipment(revenue)
                
                # Invia update dashboard
                await self._broadcast_revenue_update(revenue)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Revenue generator error: {e}")
    
    async def _create_new_shipment(self, revenue: float):
        """Crea una nuova spedizione fittizia"""
        lane = random.choice(self.lanes)
        carrier = random.choice(self.carriers)
        client = random.choice(self.clients)
        
        shipment_id = f"SHIP-{uuid.uuid4().hex[:8].upper()}"
        
        # Peso e dimensioni casuali
        weight_kg = random.randint(50, 2000)
        volume_m3 = round(weight_kg * 0.003, 2)
        
        shipment = {
            "id": shipment_id,
            "client": client["name"],
            "client_city": client["city"],
            "origin": lane["from"],
            "destination": lane["to"],
            "carrier": carrier["name"],
            "carrier_id": carrier["id"],
            "status": "in_transit",
            "weight_kg": weight_kg,
            "volume_m3": volume_m3,
            "distance_km": lane["distance"],
            "revenue": revenue,
            "created_at": datetime.utcnow().isoformat(),
            "eta": (datetime.utcnow() + timedelta(hours=random.randint(6, 72))).isoformat(),
            "coordinates": {
                "origin": {"lat": lane["from_lat"], "lon": lane["from_lon"]},
                "destination": {"lat": lane["to_lat"], "lon": lane["to_lon"]},
                "current": {"lat": lane["from_lat"], "lon": lane["from_lon"]}  # Inizia da origine
            },
            "mock": True
        }
        
        # Aggiungi a tracking attivo
        self.active_tracking[shipment_id] = {
            **shipment,
            "progress": 0.0,
            "speed_kmh": random.randint(60, 90)
        }
        
        self.total_shipments += 1
        self.active_shipments = len(self.active_tracking)
        
        # Broadcast nuova spedizione
        event = {
            "type": "new_shipment",
            "shipment": shipment,
            "monthly_revenue": round(self.monthly_revenue, 2),
            "total_shipments": self.total_shipments,
            "active_shipments": self.active_shipments,
            "timestamp": datetime.utcnow().isoformat(),
            "mock": True
        }
        
        await self._broadcast(event)
        logger.info(f"📦 [MOCK] New shipment: {shipment_id} ({lane['from']}→{lane['to']}) €{revenue:.2f}")
    
    async def _update_existing_shipment(self, revenue: float):
        """Aggiorna una spedizione esistente (es. consegna completata)"""
        if not self.active_tracking:
            await self._create_new_shipment(revenue)
            return
        
        # Prendi una spedizione casuale e segna come consegnata
        shipment_id = random.choice(list(self.active_tracking.keys()))
        shipment = self.active_tracking.pop(shipment_id)
        
        shipment["status"] = "delivered"
        shipment["revenue"] += revenue
        shipment["delivered_at"] = datetime.utcnow().isoformat()
        
        self.active_shipments = len(self.active_tracking)
        
        event = {
            "type": "shipment_delivered",
            "shipment": shipment,
            "additional_revenue": revenue,
            "monthly_revenue": round(self.monthly_revenue, 2),
            "active_shipments": self.active_shipments,
            "timestamp": datetime.utcnow().isoformat(),
            "mock": True
        }
        
        await self._broadcast(event)
        logger.info(f"✅ [MOCK] Shipment delivered: {shipment_id} +€{revenue:.2f}")
    
    async def _gps_loop(self):
        """Aggiorna posizioni GPS ogni 5 secondi"""
        while self.running:
            try:
                await asyncio.sleep(5)
                
                if not self.running:
                    break
                
                for shipment_id, tracking in list(self.active_tracking.items()):
                    # Calcola nuova posizione
                    from_lat = tracking["coordinates"]["origin"]["lat"]
                    from_lon = tracking["coordinates"]["origin"]["lon"]
                    to_lat = tracking["coordinates"]["destination"]["lat"]
                    to_lon = tracking["coordinates"]["destination"]["lon"]
                    
                    # Aumenta progresso
                    progress_increment = random.uniform(0.02, 0.08)
                    tracking["progress"] = min(tracking["progress"] + progress_increment, 1.0)
                    
                    # Calcola posizione corrente (interpolazione lineare)
                    current_lat = from_lat + (to_lat - from_lat) * tracking["progress"]
                    current_lon = from_lon + (to_lon - from_lon) * tracking["progress"]
                    
                    tracking["coordinates"]["current"] = {
                        "lat": round(current_lat, 6),
                        "lon": round(current_lon, 6)
                    }
                    
                    # Se arrivato a destinazione
                    if tracking["progress"] >= 1.0:
                        tracking["status"] = "arrived"
                        self.active_tracking.pop(shipment_id, None)
                        self.active_shipments = len(self.active_tracking)
                    
                    # Broadcast posizione
                    event = {
                        "type": "carrier_position",
                        "shipment_id": shipment_id,
                        "carrier": tracking["carrier"],
                        "position": tracking["coordinates"]["current"],
                        "progress": round(tracking["progress"] * 100, 1),
                        "status": tracking["status"],
                        "timestamp": datetime.utcnow().isoformat(),
                        "mock": True
                    }
                    
                    await self._broadcast(event)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"GPS loop error: {e}")
    
    async def _broadcast_revenue_update(self, revenue: float):
        """Invia update revenue"""
        event = {
            "type": "revenue_update",
            "new_revenue": revenue,
            "monthly_revenue_total": round(self.monthly_revenue, 2),
            "level": self._calculate_level(),
            "progress_to_next": self._calculate_progress(),
            "timestamp": datetime.utcnow().isoformat(),
            "mock": True
        }
        await self._broadcast(event)
    
    def _calculate_level(self) -> Dict[str, Any]:
        """Calcola livello basato su revenue"""
        if self.monthly_revenue < 5000:
            return {
                "current": 2,
                "name": "Growth",
                "color": "#22c55e",
                "next_threshold": 5000
            }
        elif self.monthly_revenue < 10000:
            return {
                "current": 3,
                "name": "Scale",
                "color": "#3b82f6",
                "next_threshold": 10000
            }
        else:
            return {
                "current": 4,
                "name": "Enterprise",
                "color": "#a855f7",
                "next_threshold": 50000
            }
    
    def _calculate_progress(self) -> float:
        """Calcola progresso verso prossimo livello"""
        level = self._calculate_level()
        current = self.monthly_revenue
        threshold = level["next_threshold"]
        
        if level["current"] == 2:
            prev_threshold = 2500
        elif level["current"] == 3:
            prev_threshold = 5000
        else:
            prev_threshold = 10000
        
        progress = (current - prev_threshold) / (threshold - prev_threshold)
        return round(min(max(progress, 0), 1) * 100, 1)
    
    async def _broadcast(self, event: Dict[str, Any]):
        """Invia evento via WebSocket"""
        if self.websocket_manager and hasattr(self.websocket_manager, 'broadcast'):
            try:
                await self.websocket_manager.broadcast(event)
            except Exception as e:
                logger.error(f"WebSocket broadcast error: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Ritorna statistiche correnti"""
        return {
            "monthly_revenue": round(self.monthly_revenue, 2),
            "total_shipments": self.total_shipments,
            "active_shipments": self.active_shipments,
            "tracking_shipments": len(self.active_tracking),
            "level": self._calculate_level(),
            "mock": True
        }


# Singleton
_revenue_generator = None


def get_revenue_generator(db_session_factory=None, websocket_manager=None) -> MockRevenueGenerator:
    global _revenue_generator
    if _revenue_generator is None:
        _revenue_generator = MockRevenueGenerator(db_session_factory, websocket_manager)
    return _revenue_generator
