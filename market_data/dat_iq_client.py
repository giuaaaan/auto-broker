"""
AUTO-BROKER DAT iQ Market Data Client
Real-time spot rate benchmarking and freight analytics
Enterprise Integration - P1

Features:
- WebSocket connection for real-time rates
- Redis caching for rate history (24h default)
- Historical analysis for pricing context
"""

import logging
import asyncio
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable, Any, AsyncIterator
from enum import Enum

import httpx
import websockets
from websockets.exceptions import ConnectionClosed

from security.vault_integration import get_vault_client
from services.circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)


class DATRouteType(Enum):
    """DAT route classifications."""
    VAN = "V"
    REEFER = "R"
    FLATBED = "F"


@dataclass
class DATRate:
    """DAT spot rate data point."""
    route: str  # e.g., "IT-MIL-IT-ROM"
    route_type: DATRouteType
    avg_rate: float  # Average spot rate
    low_rate: float  # 10th percentile
    high_rate: float  # 90th percentile
    rate_per_km: float
    fuel_surcharge: float
    timestamp: datetime
    equipment_type: str
    distance_km: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "route": self.route,
            "route_type": self.route_type.value,
            "avg_rate": self.avg_rate,
            "low_rate": self.low_rate,
            "high_rate": self.high_rate,
            "rate_per_km": self.rate_per_km,
            "fuel_surcharge": self.fuel_surcharge,
            "timestamp": self.timestamp.isoformat(),
            "equipment_type": self.equipment_type,
            "distance_km": self.distance_km
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DATRate":
        return cls(
            route=data["route"],
            route_type=DATRouteType(data["route_type"]),
            avg_rate=data["avg_rate"],
            low_rate=data["low_rate"],
            high_rate=data["high_rate"],
            rate_per_km=data["rate_per_km"],
            fuel_surcharge=data["fuel_surcharge"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            equipment_type=data["equipment_type"],
            distance_km=data.get("distance_km")
        )


@dataclass
class DATMarketCondition:
    """DAT market conditions for a lane."""
    route: str
    load_to_truck_ratio: float  # > 1 = tight capacity, < 1 = loose capacity
    rejection_rate: float  # % of loads rejected
    market_tension: str  # Loose, Balanced, Tight, Very Tight
    trend_7d: float  # 7-day rate change %
    trend_30d: float  # 30-day rate change %
    timestamp: datetime


class DATiQClient:
    """
    DAT iQ API Client.
    
    Provides:
    - Real-time spot rates via WebSocket
    - Historical rate data via REST API
    - Market condition indicators
    - Redis caching for performance
    """
    
    REST_BASE_URL = "https://analytics.dat.com/api"
    WS_BASE_URL = "wss://analytics.dat.com/ws"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        redis_client: Optional[Any] = None
    ):
        """
        Initialize DAT iQ client.
        
        Args:
            api_key: DAT API key (or from Vault)
            api_secret: DAT API secret (or from Vault)
            redis_client: Redis client for caching
        """
        self.redis = redis_client
        
        # Get credentials
        if api_key and api_secret:
            self.api_key = api_key
            self.api_secret = api_secret
        else:
            creds = self._get_credentials_from_vault()
            self.api_key = creds.get("api_key", "")
            self.api_secret = creds.get("api_secret", "")
        
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        
        self.http_client: Optional[httpx.AsyncClient] = None
        self.ws_connection: Optional[websockets.WebSocketClientProtocol] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_callbacks: List[Callable[[DATRate], None]] = []
        
        # Circuit breaker for resilience
        self.circuit = CircuitBreaker(
            name="dat_iq",
            failure_threshold=5,
            recovery_timeout=60,
            half_open_max_calls=2
        )
    
    def _get_credentials_from_vault(self) -> Dict[str, str]:
        """Retrieve DAT credentials from Vault."""
        try:
            vault = get_vault_client()
            secret = vault.client.secrets.kv.v2.read_secret_version(
                path="market-data/dat-iq",
                mount_point="secret"
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to get DAT credentials: {e}")
            import os
            return {
                "api_key": os.getenv("DAT_API_KEY", ""),
                "api_secret": os.getenv("DAT_API_SECRET", "")
            }
    
    async def __aenter__(self):
        """Async context manager."""
        await self._ensure_token()
        self.http_client = httpx.AsyncClient(
            headers=self._get_auth_headers(),
            timeout=30.0
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context exit."""
        await self.close()
    
    async def close(self):
        """Close connections."""
        if self.http_client:
            await self.http_client.aclose()
        if self.ws_connection:
            await self.ws_connection.close()
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
    
    async def _ensure_token(self):
        """Ensure valid access token."""
        if self._access_token and self._token_expires:
            if datetime.now() < self._token_expires - timedelta(minutes=5):
                return
        
        # Get new token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.REST_BASE_URL}/auth/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.api_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires = datetime.now() + timedelta(seconds=expires_in)
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        if not self._access_token:
            raise Exception("No access token available")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # ==================== REST API Methods ====================
    
    async def get_spot_rate(
        self,
        origin: str,
        destination: str,
        route_type: DATRouteType = DATRouteType.VAN,
        equipment: Optional[str] = None
    ) -> Optional[DATRate]:
        """
        Get current spot rate for a route.
        
        Args:
            origin: Origin location code (e.g., "IT-MIL")
            destination: Destination code (e.g., "IT-ROM")
            route_type: VAN, REEFER, or FLATBED
            equipment: Specific equipment type
            
        Returns:
            DATRate object or None if not available
        """
        route = f"{origin}-{destination}"
        
        # Check cache first
        if self.redis:
            cache_key = f"dat:rate:{route}:{route_type.value}"
            cached = await self.redis.get(cache_key)
            if cached:
                try:
                    data = json.loads(cached)
                    rate = DATRate.from_dict(data)
                    # Check if cache is still fresh (< 1 hour)
                    if datetime.now() - rate.timestamp < timedelta(hours=1):
                        return rate
                except Exception:
                    pass
        
        # Fetch from API
        try:
            await self.circuit.call(self._ensure_token)
            
            params = {
                "origin": origin,
                "destination": destination,
                "equipmentType": route_type.value
            }
            if equipment:
                params["equipment"] = equipment
            
            response = await self.circuit.call(
                self.http_client.get,
                f"{self.REST_BASE_URL}/v1/spot/rates",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            rate = DATRate(
                route=route,
                route_type=route_type,
                avg_rate=data["avgRate"],
                low_rate=data.get("lowRate", data["avgRate"] * 0.85),
                high_rate=data.get("highRate", data["avgRate"] * 1.15),
                rate_per_km=data.get("ratePerKm", 0),
                fuel_surcharge=data.get("fuelSurcharge", 0),
                timestamp=datetime.now(),
                equipment_type=equipment or route_type.name,
                distance_km=data.get("distanceKm")
            )
            
            # Cache the result
            if self.redis:
                await self.redis.setex(
                    cache_key,
                    3600,  # 1 hour TTL
                    json.dumps(rate.to_dict())
                )
            
            return rate
            
        except Exception as e:
            logger.error(f"Failed to get spot rate for {route}: {e}")
            return None
    
    async def get_market_conditions(
        self,
        origin: str,
        destination: str
    ) -> Optional[DATMarketCondition]:
        """Get market conditions for a lane."""
        route = f"{origin}-{destination}"
        
        try:
            response = await self.circuit.call(
                self.http_client.get,
                f"{self.REST_BASE_URL}/v1/market/conditions",
                params={"origin": origin, "destination": destination}
            )
            response.raise_for_status()
            data = response.json()
            
            return DATMarketCondition(
                route=route,
                load_to_truck_ratio=data.get("loadToTruckRatio", 1.0),
                rejection_rate=data.get("rejectionRate", 0.0),
                market_tension=data.get("marketTension", "Balanced"),
                trend_7d=data.get("trend7d", 0),
                trend_30d=data.get("trend30d", 0),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to get market conditions for {route}: {e}")
            return None
    
    async def get_historical_rates(
        self,
        origin: str,
        destination: str,
        days: int = 30,
        route_type: DATRouteType = DATRouteType.VAN
    ) -> List[DATRate]:
        """
        Get historical spot rates.
        
        Args:
            origin: Origin location
            destination: Destination
            days: Number of days of history
            route_type: Equipment type
        """
        route = f"{origin}-{destination}"
        
        # Try cache first for recent data
        if self.redis and days <= 7:
            cache_key = f"dat:history:{route}:{route_type.value}:{days}"
            cached = await self.redis.get(cache_key)
            if cached:
                try:
                    data = json.loads(cached)
                    return [DATRate.from_dict(r) for r in data]
                except Exception:
                    pass
        
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)
            
            response = await self.circuit.call(
                self.http_client.get,
                f"{self.REST_BASE_URL}/v1/spot/historical",
                params={
                    "origin": origin,
                    "destination": destination,
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d"),
                    "equipmentType": route_type.value
                }
            )
            response.raise_for_status()
            data = response.json()
            
            rates = []
            for point in data.get("rates", []):
                rate = DATRate(
                    route=route,
                    route_type=route_type,
                    avg_rate=point["avgRate"],
                    low_rate=point.get("lowRate", point["avgRate"] * 0.85),
                    high_rate=point.get("highRate", point["avgRate"] * 1.15),
                    rate_per_km=point.get("ratePerKm", 0),
                    fuel_surcharge=point.get("fuelSurcharge", 0),
                    timestamp=datetime.fromisoformat(point["date"]),
                    equipment_type=route_type.name
                )
                rates.append(rate)
            
            # Cache short-term history
            if self.redis and days <= 7:
                await self.redis.setex(
                    f"dat:history:{route}:{route_type.value}:{days}",
                    7200,  # 2 hours
                    json.dumps([r.to_dict() for r in rates])
                )
            
            return rates
            
        except Exception as e:
            logger.error(f"Failed to get historical rates for {route}: {e}")
            return []
    
    async def analyze_rate_trend(
        self,
        origin: str,
        destination: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze rate trends for a lane.
        
        Returns volatility, seasonality, and trend metrics.
        """
        rates = await self.get_historical_rates(origin, destination, days)
        
        if not rates or len(rates) < 7:
            return {"error": "Insufficient data for analysis"}
        
        avg_rates = [r.avg_rate for r in rates]
        
        # Calculate metrics
        current = avg_rates[-1]
        avg_7d = sum(avg_rates[-7:]) / 7
        avg_30d = sum(avg_rates) / len(avg_rates)
        
        # Volatility (standard deviation / mean)
        import statistics
        volatility = statistics.stdev(avg_rates) / avg_30d if avg_30d > 0 else 0
        
        # Trend direction
        if current > avg_7d * 1.05:
            trend = "rising"
        elif current < avg_7d * 0.95:
            trend = "falling"
        else:
            trend = "stable"
        
        return {
            "route": f"{origin}-{destination}",
            "current_rate": current,
            "avg_7d": avg_7d,
            "avg_30d": avg_30d,
            "change_7d_pct": ((current - avg_7d) / avg_7d) * 100,
            "change_30d_pct": ((current - avg_30d) / avg_30d) * 100,
            "volatility": volatility,
            "trend_direction": trend,
            "data_points": len(rates)
        }
    
    # ==================== WebSocket Methods ====================
    
    def add_rate_listener(self, callback: Callable[[DATRate], None]):
        """Add callback for real-time rate updates."""
        self._ws_callbacks.append(callback)
    
    def remove_rate_listener(self, callback: Callable[[DATRate], None]):
        """Remove rate listener callback."""
        if callback in self._ws_callbacks:
            self._ws_callbacks.remove(callback)
    
    async def start_websocket(self, routes: List[str]):
        """
        Start WebSocket connection for real-time rates.
        
        Args:
            routes: List of route codes to subscribe to
        """
        await self._ensure_token()
        
        ws_url = f"{self.WS_BASE_URL}/rates?token={self._access_token}"
        
        self._ws_task = asyncio.create_task(
            self._websocket_loop(ws_url, routes)
        )
    
    async def _websocket_loop(self, ws_url: str, routes: List[str]):
        """WebSocket connection loop with auto-reconnect."""
        reconnect_delay = 5
        
        while True:
            try:
                async with websockets.connect(ws_url) as ws:
                    self.ws_connection = ws
                    logger.info("DAT WebSocket connected")
                    
                    # Subscribe to routes
                    await ws.send(json.dumps({
                        "action": "subscribe",
                        "routes": routes
                    }))
                    
                    # Listen for messages
                    async for message in ws:
                        await self._handle_ws_message(message)
                    
            except ConnectionClosed:
                logger.warning("DAT WebSocket disconnected, reconnecting...")
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
            
            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 60)  # Max 60s delay
    
    async def _handle_ws_message(self, message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(message)
            
            if data.get("type") == "rate_update":
                rate = DATRate(
                    route=data["route"],
                    route_type=DATRouteType(data.get("routeType", "V")),
                    avg_rate=data["avgRate"],
                    low_rate=data.get("lowRate", 0),
                    high_rate=data.get("highRate", 0),
                    rate_per_km=data.get("ratePerKm", 0),
                    fuel_surcharge=data.get("fuelSurcharge", 0),
                    timestamp=datetime.now(),
                    equipment_type=data.get("equipmentType", "VAN")
                )
                
                # Update cache
                if self.redis:
                    cache_key = f"dat:rate:{rate.route}:{rate.route_type.value}"
                    await self.redis.setex(
                        cache_key,
                        3600,
                        json.dumps(rate.to_dict())
                    )
                
                # Notify listeners
                for callback in self._ws_callbacks:
                    try:
                        if asyncio.iscoroutinefunction(callback):
                            await callback(rate)
                        else:
                            callback(rate)
                    except Exception as e:
                        logger.error(f"Rate listener error: {e}")
                        
        except Exception as e:
            logger.error(f"Failed to handle WS message: {e}")
    
    # ==================== Pricing Engine Integration ====================
    
    async def get_pricing_context(
        self,
        origin: str,
        destination: str,
        cargo_weight_kg: Optional[float] = None,
        cargo_volume_m3: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Get complete pricing context for a shipment.
        
        Includes current rates, market conditions, and trend analysis.
        """
        rate = await self.get_spot_rate(origin, destination)
        market = await self.get_market_conditions(origin, destination)
        trend = await self.analyze_rate_trend(origin, destination, days=14)
        
        context = {
            "route": f"{origin}-{destination}",
            "timestamp": datetime.now().isoformat(),
            "spot_rate": rate.to_dict() if rate else None,
            "market_conditions": {
                "load_to_truck_ratio": market.load_to_truck_ratio if market else None,
                "market_tension": market.market_tension if market else None,
                "trend_7d": market.trend_7d if market else None
            } if market else None,
            "trend_analysis": trend,
            "recommendation": None
        }
        
        # Generate pricing recommendation
        if rate and market:
            if market.market_tension in ["Tight", "Very Tight"]:
                recommended_rate = rate.high_rate
                strategy = "price_aggressively"
            elif market.market_tension == "Loose":
                recommended_rate = rate.avg_rate
                strategy = "competitive"
            else:
                recommended_rate = (rate.avg_rate + rate.high_rate) / 2
                strategy = "balanced"
            
            context["recommendation"] = {
                "rate": recommended_rate,
                "strategy": strategy,
                "confidence": "high" if trend.get("data_points", 0) > 14 else "medium"
            }
        
        return context
