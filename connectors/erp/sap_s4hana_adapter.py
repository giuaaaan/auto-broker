"""
AUTO-BROKER SAP S/4HANA Adapter
OData v4 integration for SAP S/4HANA Cloud/On-Premise
Enterprise Integration - P1

Entities:
- Master data: Materials, Customers, Vendors
- Transactional: Sales Orders, Purchase Orders, Delivery Notes
- Confirmations: POD (Proof of Delivery) as Goods Receipt
"""

import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from functools import wraps

import httpx
import yaml
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from security.vault_integration import VaultClient, get_vault_client

logger = logging.getLogger(__name__)


@dataclass
class SAPMaterial:
    """SAP Material Master."""
    material_id: str
    description: str
    weight_kg: float
    length_m: Optional[float] = None
    width_m: Optional[float] = None
    height_m: Optional[float] = None
    adr_class: Optional[str] = None  # Dangerous goods
    hazmat: bool = False


@dataclass
class SAPCustomer:
    """SAP Customer Master."""
    customer_id: str
    name: str
    address: str
    city: str
    postal_code: str
    country: str
    vat_number: Optional[str] = None
    delivery_instructions: Optional[str] = None


@dataclass
class SAPVendor:
    """SAP Vendor (Carrier) Master."""
    vendor_id: str
    name: str
    address: str
    city: str
    country: str
    vat_number: str
    scac_code: Optional[str] = None  # Standard Carrier Alpha Code


@dataclass
class SAPSalesOrder:
    """SAP Sales Order."""
    order_id: str
    customer_id: str
    order_date: datetime
    delivery_date: datetime
    items: List[Dict[str, Any]]
    total_value: float
    currency: str
    shipping_address: Dict[str, str]
    status: str


@dataclass
class SAPDeliveryNote:
    """SAP Delivery Note (Outbound Delivery)."""
    delivery_id: str
    order_id: str
    customer_id: str
    items: List[Dict[str, Any]]
    planned_ship_date: datetime
    actual_ship_date: Optional[datetime] = None
    carrier_id: Optional[str] = None
    tracking_number: Optional[str] = None


class SAPMappingConfig:
    """SAP field mapping configuration from YAML."""
    
    def __init__(self, config_path: str = "connectors/erp/mapping_sap.yaml"):
        self.config_path = config_path
        self.mappings = self._load_mappings()
    
    def _load_mappings(self) -> Dict[str, Any]:
        """Load mapping configuration from YAML."""
        try:
            with open(self.config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Mapping file {self.config_path} not found, using defaults")
            return self._default_mappings()
    
    def _default_mappings(self) -> Dict[str, Any]:
        """Default field mappings."""
        return {
            "sales_order": {
                "sap_field": "VBAK",
                "fields": {
                    "VBELN": "order_id",  # Sales Document
                    "KUNNR": "customer_id",  # Sold-to Party
                    "NETWR": "total_value",  # Net Value
                    "WAERK": "currency",  # Currency
                    "AUDAT": "order_date",  # Document Date
                }
            },
            "material": {
                "sap_field": "MARA",
                "fields": {
                    "MATNR": "material_id",
                    "MAKTX": "description",
                    "BRGEW": "weight_kg",
                    "LAENG": "length_m",
                    "BREIT": "width_m",
                    "HOEHE": "height_m",
                }
            },
            "customer": {
                "sap_field": "KNA1",
                "fields": {
                    "KUNNR": "customer_id",
                    "NAME1": "name",
                    "STRAS": "address",
                    "ORT01": "city",
                    "PSTLZ": "postal_code",
                    "LAND1": "country",
                    "STCEG": "vat_number",
                }
            }
        }
    
    def map_field(self, entity: str, sap_field: str) -> str:
        """Map SAP field name to internal field name."""
        return self.mappings.get(entity, {}).get("fields", {}).get(sap_field, sap_field)
    
    def reverse_map(self, entity: str, internal_field: str) -> str:
        """Map internal field name to SAP field name."""
        fields = self.mappings.get(entity, {}).get("fields", {})
        reverse = {v: k for k, v in fields.items()}
        return reverse.get(internal_field, internal_field)


class SAPS4HANAAdapter:
    """
    SAP S/4HANA OData v4 Adapter.
    
    Features:
    - OData v4 CRUD operations
    - Configurable field mapping via YAML
    - Retry logic with exponential backoff
    - Circuit breaker for resilience
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        vault_client: Optional[VaultClient] = None,
        mapping_config: Optional[SAPMappingConfig] = None
    ):
        """
        Initialize SAP adapter.
        
        Credentials priority:
        1. Constructor parameters
        2. Vault secrets
        3. Environment variables
        """
        self.vault = vault_client or get_vault_client()
        self.mapping = mapping_config or SAPMappingConfig()
        
        # Get credentials
        if base_url and username and password:
            self.base_url = base_url.rstrip('/')
            self.username = username
            self.password = password
        else:
            creds = self._get_credentials_from_vault()
            self.base_url = creds.get("base_url", "")
            self.username = creds.get("username", "")
            self.password = creds.get("password", "")
        
        self.client = None
        self._circuit_failures = 0
        self._circuit_last_failure = None
        self._circuit_threshold = 5
        self._circuit_timeout = 60  # seconds
    
    def _get_credentials_from_vault(self) -> Dict[str, str]:
        """Retrieve SAP credentials from Vault."""
        try:
            secret = self.vault.client.secrets.kv.v2.read_secret_version(
                path="erp/sap-s4hana",
                mount_point="secret"
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to get SAP credentials from Vault: {e}")
            # Fallback to environment
            import os
            return {
                "base_url": os.getenv("SAP_BASE_URL", ""),
                "username": os.getenv("SAP_USERNAME", ""),
                "password": os.getenv("SAP_PASSWORD", "")
            }
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(self.username, self.password),
            timeout=30.0,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.client:
            await self.client.aclose()
    
    def _check_circuit_breaker(self):
        """Check if circuit breaker is open."""
        if self._circuit_failures >= self._circuit_threshold:
            if self._circuit_last_failure:
                elapsed = (datetime.now() - self._circuit_last_failure).total_seconds()
                if elapsed < self._circuit_timeout:
                    raise Exception("Circuit breaker OPEN - SAP temporarily unavailable")
                else:
                    # Reset circuit
                    self._circuit_failures = 0
    
    def _record_failure(self):
        """Record a failure for circuit breaker."""
        self._circuit_failures += 1
        self._circuit_last_failure = datetime.now()
    
    def _record_success(self):
        """Record a success (reset circuit)."""
        if self._circuit_failures > 0:
            self._circuit_failures = 0
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60),
        reraise=True
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request with retry logic."""
        self._check_circuit_breaker()
        
        try:
            if method == "GET":
                response = await self.client.get(endpoint, params=params)
            elif method == "POST":
                response = await self.client.post(endpoint, json=data)
            elif method == "PATCH":
                response = await self.client.patch(endpoint, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            self._record_success()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            self._record_failure()
            logger.error(f"SAP request failed: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            self._record_failure()
            logger.error(f"SAP request error: {e}")
            raise
    
    # ==================== Master Data ====================
    
    async def get_material(self, material_id: str) -> Optional[SAPMaterial]:
        """Get material master from SAP."""
        endpoint = f"/sap/opu/odata4/sap/api_product/srvd_a2x/sap/product/0001/Product('{material_id}')"
        
        try:
            data = await self._make_request("GET", endpoint)
            
            return SAPMaterial(
                material_id=material_id,
                description=data.get("ProductDescription", ""),
                weight_kg=float(data.get("GrossWeight", 0)),
                length_m=float(data.get("ProductLength", 0)) or None,
                width_m=float(data.get("ProductWidth", 0)) or None,
                height_m=float(data.get("ProductHeight", 0)) or None,
                adr_class=data.get("DangerousGoodsInd", ""),
                hazmat=bool(data.get("DangerousGoodsInd"))
            )
        except Exception as e:
            logger.error(f"Failed to get material {material_id}: {e}")
            return None
    
    async def get_customer(self, customer_id: str) -> Optional[SAPCustomer]:
        """Get customer master from SAP."""
        endpoint = f"/sap/opu/odata4/sap/api_business_partner/srvd_a2x/sap/businesspartner/0001/BusinessPartner('{customer_id}')"
        
        try:
            data = await self._make_request("GET", endpoint)
            
            # Get address details
            address = data.get("to_BusinessPartnerAddress", {}).get("results", [{}])[0]
            
            return SAPCustomer(
                customer_id=customer_id,
                name=data.get("OrganizationBPName1", ""),
                address=address.get("StreetName", ""),
                city=address.get("CityName", ""),
                postal_code=address.get("PostalCode", ""),
                country=address.get("Country", ""),
                vat_number=data.get("VATRegistration", "")
            )
        except Exception as e:
            logger.error(f"Failed to get customer {customer_id}: {e}")
            return None
    
    async def get_vendor(self, vendor_id: str) -> Optional[SAPVendor]:
        """Get vendor (carrier) master from SAP."""
        endpoint = f"/sap/opu/odata4/sap/api_business_partner/srvd_a2x/sap/businesspartner/0001/BusinessPartner('{vendor_id}')"
        
        try:
            data = await self._make_request("GET", endpoint)
            
            address = data.get("to_BusinessPartnerAddress", {}).get("results", [{}])[0]
            
            return SAPVendor(
                vendor_id=vendor_id,
                name=data.get("OrganizationBPName1", ""),
                address=address.get("StreetName", ""),
                city=address.get("CityName", ""),
                country=address.get("Country", ""),
                vat_number=data.get("VATRegistration", ""),
                scac_code=data.get("BusinessPartnerIDByExtSystem", "")
            )
        except Exception as e:
            logger.error(f"Failed to get vendor {vendor_id}: {e}")
            return None
    
    # ==================== Transactional Data ====================
    
    async def get_sales_orders(
        self,
        from_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> List[SAPSalesOrder]:
        """Get sales orders from SAP."""
        endpoint = "/sap/opu/odata4/sap/api_sales_order/srvd_a2x/sap/salesorder/0001/SalesOrder"
        
        params = {}
        if from_date:
            params["$filter"] = f"CreationDate ge {from_date.isoformat()}"
        if status:
            if "$filter" in params:
                params["$filter"] += f" and OverallSDProcessStatus eq '{status}'"
            else:
                params["$filter"] = f"OverallSDProcessStatus eq '{status}'"
        
        try:
            data = await self._make_request("GET", endpoint, params=params)
            orders = []
            
            for item in data.get("value", []):
                order = SAPSalesOrder(
                    order_id=item.get("SalesOrder", ""),
                    customer_id=item.get("SoldToParty", ""),
                    order_date=datetime.fromisoformat(item.get("CreationDate", "").replace('Z', '+00:00')),
                    delivery_date=datetime.fromisoformat(item.get("RequestedDeliveryDate", "").replace('Z', '+00:00')),
                    items=[],  # Would need separate call for items
                    total_value=float(item.get("TotalNetAmount", 0)),
                    currency=item.get("TransactionCurrency", "EUR"),
                    shipping_address={},
                    status=item.get("OverallSDProcessStatus", "")
                )
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get sales orders: {e}")
            return []
    
    async def get_delivery_notes(self, from_date: Optional[datetime] = None) -> List[SAPDeliveryNote]:
        """Get outbound delivery notes from SAP."""
        endpoint = "/sap/opu/odata4/sap/api_outbound_delivery/srvd_a2x/sap/outbounddelivery/0001/OutboundDelivery"
        
        params = {}
        if from_date:
            params["$filter"] = f"CreationDate ge {from_date.isoformat()}"
        
        try:
            data = await self._make_request("GET", endpoint, params=params)
            deliveries = []
            
            for item in data.get("value", []):
                delivery = SAPDeliveryNote(
                    delivery_id=item.get("OutboundDelivery", ""),
                    order_id=item.get("SalesOrder", ""),
                    customer_id=item.get("ShipToParty", ""),
                    items=[],
                    planned_ship_date=datetime.fromisoformat(item.get("PlannedGoodsIssueDate", "").replace('Z', '+00:00')),
                    carrier_id=item.get("CarrierAccountNumber", "")
                )
                deliveries.append(delivery)
            
            return deliveries
            
        except Exception as e:
            logger.error(f"Failed to get delivery notes: {e}")
            return []
    
    # ==================== POD Confirmation ====================
    
    async def post_pod_confirmation(
        self,
        delivery_id: str,
        received_by: str,
        received_at: datetime,
        quantity_received: int
    ) -> bool:
        """
        Post Proof of Delivery back to SAP as Goods Receipt.
        
        This creates a Goods Receipt document in SAP,
        completing the order-to-cash cycle.
        """
        endpoint = "/sap/opu/odata4/sap/api_inbound_delivery/srvd_a2x/sap/inbounddelivery/0001/InboundDelivery"
        
        data = {
            "ReferenceDocument": delivery_id,
            "ReferenceDocumentType": "OUTB_DELIV",
            "ActualGoodsReceiptDate": received_at.isoformat(),
            "DeliveryDocumentItem": [
                {
                    "ActualDeliveredQtyInBaseUnit": quantity_received,
                    "GoodsReceiptStatus": "C"  # Completely delivered
                }
            ]
        }
        
        try:
            await self._make_request("POST", endpoint, data=data)
            logger.info(f"POD confirmation posted for delivery {delivery_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to post POD for {delivery_id}: {e}")
            return False
    
    # ==================== Utility ====================
    
    def test_connection(self) -> bool:
        """Test SAP connection."""
        try:
            # Simple metadata request
            asyncio.run(self._make_request("GET", "/sap/opu/odata4/$metadata"))
            return True
        except Exception:
            return False
