"""
AUTO-BROKER Teleroute Client
European freight exchange integration
Enterprise Integration - P1

Features:
- REST API for freight offers and vehicle offers
- Real-time load/carrier matching
- Redis caching for offer data
"""

import logging
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from security.vault_integration import get_vault_client
from services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class TelerouteOfferType(Enum):
    """Teleroute offer types."""
    FREIGHT = "FREIGHT"  # Shipper posting freight
    VEHICLE = "VEHICLE"  # Carrier posting available vehicle


class TelerouteEquipment(Enum):
    """Equipment types."""
    TENT = "TENT"  # Curtainsider
    FRIGO = "FRIGO"  # Refrigerated
    TANK = "TANK"  # Tanker
    BOX = "BOX"  # Box truck
    FLAT = "FLAT"  # Flatbed
    MEGA = "MEGA"  # Mega trailer
    JUMBO = "JUMBO"  # Jumbo trailer


@dataclass
class TelerouteLocation:
    """Location with geocoding."""
    city: str
    postal_code: str
    country_code: str  # ISO 3166-1 alpha-2
    lat: Optional[float] = None
    lon: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "city": self.city,
            "postalCode": self.postal_code,
            "countryCode": self.country_code,
            "coordinates": {
                "latitude": self.lat,
                "longitude": self.lon
            } if self.lat and self.lon else None
        }


@dataclass
class TelerouteFreightOffer:
    """Freight offer from Teleroute."""
    offer_id: str
    reference: str
    loading_location: TelerouteLocation
    unloading_location: TelerouteLocation
    loading_date: datetime
    unloading_date: Optional[datetime]
    equipment_type: TelerouteEquipment
    weight_kg: float
    volume_m3: Optional[float]
    pallets: Optional[int]
    adr: bool  # Dangerous goods
    price: Optional[float]
    currency: str
    contact_phone: str
    contact_email: Optional[str]
    company_name: str
    published_at: datetime
    expires_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "reference": self.reference,
            "loading": self.loading_location.to_dict(),
            "unloading": self.unloading_location.to_dict(),
            "loading_date": self.loading_date.isoformat(),
            "unloading_date": self.unloading_date.isoformat() if self.unloading_date else None,
            "equipment": self.equipment_type.value,
            "weight_kg": self.weight_kg,
            "volume_m3": self.volume_m3,
            "pallets": self.pallets,
            "adr": self.adr,
            "price": self.price,
            "currency": self.currency,
            "contact": {
                "phone": self.contact_phone,
                "email": self.contact_email
            },
            "company": self.company_name,
            "published_at": self.published_at.isoformat(),
            "expires_at": self.expires_at.isoformat()
        }


@dataclass
class TelerouteVehicleOffer:
    """Vehicle offer from Teleroute."""
    offer_id: str
    current_location: TelerouteLocation
    available_date: datetime
    available_until: Optional[datetime]
    destination_preferences: List[TelerouteLocation]
    equipment_type: TelerouteEquipment
    weight_capacity_kg: float
    volume_capacity_m3: float
    pallet_capacity: Optional[int]
    adr_capable: bool
    price_expectation: Optional[float]
    currency: str
    contact_phone: str
    company_name: str
    published_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "offer_id": self.offer_id,
            "current_location": self.current_location.to_dict(),
            "available_date": self.available_date.isoformat(),
            "equipment": self.equipment_type.value,
            "capacity": {
                "weight_kg": self.weight_capacity_kg,
                "volume_m3": self.volume_capacity_m3,
                "pallets": self.pallet_capacity
            },
            "adr_capable": self.adr_capable,
            "price_expectation": self.price_expectation,
            "company": self.company_name,
            "published_at": self.published_at.isoformat()
        }


class TelerouteClient:
    """
    Teleroute REST API Client.
    
    Provides:
    - Freight offer search and retrieval
    - Vehicle offer posting and search
    - Real-time matching capabilities
    - Redis caching for offer data
    """
    
    BASE_URL = "https://api.teleroute.com/v1"
    
    def __init__(
        self,
        username: Optional[str] = None,
        password: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        redis_client: Optional[Any] = None
    ):
        self.redis = redis_client
        
        # Get credentials
        if username and password:
            self.username = username
            self.password = password
            self.client_id = client_id or ""
            self.client_secret = client_secret or ""
        else:
            creds = self._get_credentials_from_vault()
            self.username = creds.get("username", "")
            self.password = creds.get("password", "")
            self.client_id = creds.get("client_id", "")
            self.client_secret = creds.get("client_secret", "")
        
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
        self.http_client: Optional[httpx.AsyncClient] = None
        
        self.circuit = CircuitBreaker(
            name="teleroute",
            failure_threshold=5,
            recovery_timeout=60
        )
    
    def _get_credentials_from_vault(self) -> Dict[str, str]:
        """Retrieve Teleroute credentials from Vault."""
        try:
            vault = get_vault_client()
            secret = vault.client.secrets.kv.v2.read_secret_version(
                path="market-data/teleroute",
                mount_point="secret"
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to get Teleroute credentials: {e}")
            import os
            return {
                "username": os.getenv("TELEROUTE_USERNAME", ""),
                "password": os.getenv("TELEROUTE_PASSWORD", ""),
                "client_id": os.getenv("TELEROUTE_CLIENT_ID", ""),
                "client_secret": os.getenv("TELEROUTE_CLIENT_SECRET", "")
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
        if self.http_client:
            await self.http_client.aclose()
    
    async def _ensure_token(self):
        """Ensure valid OAuth token."""
        if self._access_token and self._token_expires:
            if datetime.now() < self._token_expires - timedelta(minutes=5):
                return
        
        # OAuth2 token request
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth.teleroute.com/oauth/token",
                data={
                    "grant_type": "password",
                    "username": self.username,
                    "password": self.password,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                }
            )
            response.raise_for_status()
            data = response.json()
            
            self._access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self._token_expires = datetime.now() + timedelta(seconds=expires_in)
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authenticated headers."""
        if not self._access_token:
            raise Exception("No access token available")
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # ==================== Freight Offers ====================
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def search_freight_offers(
        self,
        loading_country: Optional[str] = None,
        loading_city: Optional[str] = None,
        unloading_country: Optional[str] = None,
        unloading_city: Optional[str] = None,
        equipment: Optional[TelerouteEquipment] = None,
        min_weight_kg: Optional[float] = None,
        max_weight_kg: Optional[float] = None,
        loading_from: Optional[datetime] = None,
        loading_to: Optional[datetime] = None,
        limit: int = 50
    ) -> List[TelerouteFreightOffer]:
        """
        Search for freight offers on Teleroute.
        
        Returns available loads matching criteria.
        """
        # Check cache
        cache_key = self._build_cache_key("freight", locals())
        if self.redis:
            cached = await self.redis.get(cache_key)
            if cached:
                import json
                data = json.loads(cached)
                return [self._freight_from_dict(o) for o in data]
        
        # Build search params
        params = {"limit": limit}
        
        if loading_country:
            params["loadingCountryCode"] = loading_country
        if loading_city:
            params["loadingCity"] = loading_city
        if unloading_country:
            params["unloadingCountryCode"] = unloading_country
        if unloading_city:
            params["unloadingCity"] = unloading_city
        if equipment:
            params["equipmentType"] = equipment.value
        if min_weight_kg:
            params["minWeight"] = min_weight_kg
        if max_weight_kg:
            params["maxWeight"] = max_weight_kg
        if loading_from:
            params["loadingDateFrom"] = loading_from.strftime("%Y-%m-%d")
        if loading_to:
            params["loadingDateTo"] = loading_to.strftime("%Y-%m-%d")
        
        try:
            await self.circuit.call(self._ensure_token)
            
            response = await self.circuit.call(
                self.http_client.get,
                f"{self.BASE_URL}/freight/offers",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            offers = []
            for item in data.get("offers", []):
                offer = self._parse_freight_offer(item)
                if offer:
                    offers.append(offer)
            
            # Cache results
            if self.redis:
                import json
                await self.redis.setex(
                    cache_key,
                    300,  # 5 minute TTL
                    json.dumps([o.to_dict() for o in offers])
                )
            
            return offers
            
        except Exception as e:
            logger.error(f"Failed to search freight offers: {e}")
            return []
    
    async def get_freight_offer(self, offer_id: str) -> Optional[TelerouteFreightOffer]:
        """Get specific freight offer details."""
        try:
            response = await self.circuit.call(
                self.http_client.get,
                f"{self.BASE_URL}/freight/offers/{offer_id}"
            )
            response.raise_for_status()
            return self._parse_freight_offer(response.json())
        except Exception as e:
            logger.error(f"Failed to get freight offer {offer_id}: {e}")
            return None
    
    async def post_freight_offer(
        self,
        loading_location: TelerouteLocation,
        unloading_location: TelerouteLocation,
        loading_date: datetime,
        equipment: TelerouteEquipment,
        weight_kg: float,
        reference: str,
        price: Optional[float] = None,
        currency: str = "EUR",
        volume_m3: Optional[float] = None,
        pallets: Optional[int] = None,
        adr: bool = False
    ) -> Optional[str]:
        """
        Post a freight offer to Teleroute.
        
        Returns the offer ID if successful.
        """
        data = {
            "reference": reference,
            "loading": {
                "location": loading_location.to_dict(),
                "date": loading_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            },
            "unloading": {
                "location": unloading_location.to_dict()
            },
            "equipmentType": equipment.value,
            "cargo": {
                "weight": weight_kg,
                "volume": volume_m3,
                "pallets": pallets,
                "adr": adr
            },
            "contact": {
                "phone": "+39",  # Should come from company settings
            },
            "validity": {
                "from": datetime.now().isoformat(),
                "to": (datetime.now() + timedelta(days=7)).isoformat()
            }
        }
        
        if price:
            data["price"] = {
                "amount": price,
                "currency": currency
            }
        
        try:
            response = await self.circuit.call(
                self.http_client.post,
                f"{self.BASE_URL}/freight/offers",
                json=data
            )
            response.raise_for_status()
            result = response.json()
            offer_id = result.get("offerId")
            logger.info(f"Posted freight offer: {offer_id}")
            return offer_id
        except Exception as e:
            logger.error(f"Failed to post freight offer: {e}")
            return None
    
    # ==================== Vehicle Offers ====================
    
    async def search_vehicle_offers(
        self,
        current_country: Optional[str] = None,
        destination_country: Optional[str] = None,
        equipment: Optional[TelerouteEquipment] = None,
        available_from: Optional[datetime] = None,
        limit: int = 50
    ) -> List[TelerouteVehicleOffer]:
        """Search for available vehicles on Teleroute."""
        params = {"limit": limit}
        
        if current_country:
            params["currentCountryCode"] = current_country
        if destination_country:
            params["destinationCountryCode"] = destination_country
        if equipment:
            params["equipmentType"] = equipment.value
        if available_from:
            params["availableFrom"] = available_from.strftime("%Y-%m-%d")
        
        try:
            response = await self.circuit.call(
                self.http_client.get,
                f"{self.BASE_URL}/vehicle/offers",
                params=params
            )
            response.raise_for_status()
            data = response.json()
            
            offers = []
            for item in data.get("offers", []):
                offer = self._parse_vehicle_offer(item)
                if offer:
                    offers.append(offer)
            
            return offers
            
        except Exception as e:
            logger.error(f"Failed to search vehicle offers: {e}")
            return []
    
    async def post_vehicle_offer(
        self,
        current_location: TelerouteLocation,
        available_date: datetime,
        equipment: TelerouteEquipment,
        weight_capacity_kg: float,
        volume_capacity_m3: float,
        destination_preferences: Optional[List[TelerouteLocation]] = None,
        price_expectation: Optional[float] = None,
        currency: str = "EUR"
    ) -> Optional[str]:
        """Post a vehicle offer to Teleroute."""
        data = {
            "currentLocation": current_location.to_dict(),
            "availableFrom": available_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "equipmentType": equipment.value,
            "capacity": {
                "weight": weight_capacity_kg,
                "volume": volume_capacity_m3
            },
            "contact": {
                "phone": "+39"
            },
            "validity": {
                "from": datetime.now().isoformat(),
                "to": (datetime.now() + timedelta(days=3)).isoformat()
            }
        }
        
        if destination_preferences:
            data["destinationPreferences"] = [loc.to_dict() for loc in destination_preferences]
        if price_expectation:
            data["priceExpectation"] = {
                "amount": price_expectation,
                "currency": currency
            }
        
        try:
            response = await self.circuit.call(
                self.http_client.post,
                f"{self.BASE_URL}/vehicle/offers",
                json=data
            )
            response.raise_for_status()
            result = response.json()
            offer_id = result.get("offerId")
            logger.info(f"Posted vehicle offer: {offer_id}")
            return offer_id
        except Exception as e:
            logger.error(f"Failed to post vehicle offer: {e}")
            return None
    
    # ==================== Parsing Methods ====================
    
    def _parse_freight_offer(self, data: Dict[str, Any]) -> Optional[TelerouteFreightOffer]:
        """Parse freight offer from API response."""
        try:
            loading = data.get("loading", {})
            unloading = data.get("unloading", {})
            cargo = data.get("cargo", {})
            price = data.get("price", {})
            contact = data.get("contact", {})
            validity = data.get("validity", {})
            
            return TelerouteFreightOffer(
                offer_id=data.get("offerId", ""),
                reference=data.get("reference", ""),
                loading_location=TelerouteLocation(
                    city=loading.get("location", {}).get("city", ""),
                    postal_code=loading.get("location", {}).get("postalCode", ""),
                    country_code=loading.get("location", {}).get("countryCode", "")
                ),
                unloading_location=TelerouteLocation(
                    city=unloading.get("location", {}).get("city", ""),
                    postal_code=unloading.get("location", {}).get("postalCode", ""),
                    country_code=unloading.get("location", {}).get("countryCode", "")
                ),
                loading_date=datetime.fromisoformat(loading.get("date", "").replace('Z', '+00:00')),
                unloading_date=datetime.fromisoformat(unloading.get("date", "").replace('Z', '+00:00')) if unloading.get("date") else None,
                equipment_type=TelerouteEquipment(data.get("equipmentType", "TENT")),
                weight_kg=cargo.get("weight", 0),
                volume_m3=cargo.get("volume"),
                pallets=cargo.get("pallets"),
                adr=cargo.get("adr", False),
                price=price.get("amount"),
                currency=price.get("currency", "EUR"),
                contact_phone=contact.get("phone", ""),
                contact_email=contact.get("email"),
                company_name=data.get("company", {}).get("name", ""),
                published_at=datetime.fromisoformat(data.get("createdAt", "").replace('Z', '+00:00')),
                expires_at=datetime.fromisoformat(validity.get("to", "").replace('Z', '+00:00'))
            )
        except Exception as e:
            logger.error(f"Failed to parse freight offer: {e}")
            return None
    
    def _parse_vehicle_offer(self, data: Dict[str, Any]) -> Optional[TelerouteVehicleOffer]:
        """Parse vehicle offer from API response."""
        try:
            capacity = data.get("capacity", {})
            price = data.get("priceExpectation", {})
            
            return TelerouteVehicleOffer(
                offer_id=data.get("offerId", ""),
                current_location=TelerouteLocation(
                    city=data.get("currentLocation", {}).get("city", ""),
                    postal_code=data.get("currentLocation", {}).get("postalCode", ""),
                    country_code=data.get("currentLocation", {}).get("countryCode", "")
                ),
                available_date=datetime.fromisoformat(data.get("availableFrom", "").replace('Z', '+00:00')),
                available_until=datetime.fromisoformat(data.get("availableTo", "").replace('Z', '+00:00')) if data.get("availableTo") else None,
                destination_preferences=[
                    TelerouteLocation(
                        city=loc.get("city", ""),
                        postal_code=loc.get("postalCode", ""),
                        country_code=loc.get("countryCode", "")
                    )
                    for loc in data.get("destinationPreferences", [])
                ],
                equipment_type=TelerouteEquipment(data.get("equipmentType", "TENT")),
                weight_capacity_kg=capacity.get("weight", 0),
                volume_capacity_m3=capacity.get("volume", 0),
                pallet_capacity=capacity.get("pallets"),
                adr_capable=data.get("adrCapable", False),
                price_expectation=price.get("amount"),
                currency=price.get("currency", "EUR"),
                contact_phone=data.get("contact", {}).get("phone", ""),
                company_name=data.get("company", {}).get("name", ""),
                published_at=datetime.fromisoformat(data.get("createdAt", "").replace('Z', '+00:00'))
            )
        except Exception as e:
            logger.error(f"Failed to parse vehicle offer: {e}")
            return None
    
    def _build_cache_key(self, prefix: str, params: Dict[str, Any]) -> str:
        """Build cache key from search parameters."""
        import hashlib
        # Extract relevant params
        relevant = {
            k: v for k, v in params.items()
            if k not in ('self', 'limit') and v is not None
        }
        param_str = json.dumps(relevant, sort_keys=True, default=str)
        hash_val = hashlib.md5(param_str.encode()).hexdigest()[:16]
        return f"teleroute:{prefix}:{hash_val}"
    
    def _freight_from_dict(self, data: Dict[str, Any]) -> TelerouteFreightOffer:
        """Reconstruct freight offer from dict."""
        return TelerouteFreightOffer(
            offer_id=data["offer_id"],
            reference=data["reference"],
            loading_location=TelerouteLocation(**data["loading"]),
            unloading_location=TelerouteLocation(**data["unloading"]),
            loading_date=datetime.fromisoformat(data["loading_date"]),
            unloading_date=datetime.fromisoformat(data["unloading_date"]) if data["unloading_date"] else None,
            equipment_type=TelerouteEquipment(data["equipment"]),
            weight_kg=data["weight_kg"],
            volume_m3=data.get("volume_m3"),
            pallets=data.get("pallets"),
            adr=data["adr"],
            price=data.get("price"),
            currency=data["currency"],
            contact_phone=data["contact"]["phone"],
            contact_email=data["contact"].get("email"),
            company_name=data["company"],
            published_at=datetime.fromisoformat(data["published_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"])
        )
