"""
AUTO-BROKER NetSuite Adapter
RESTlet v2 integration for NetSuite ERP
Enterprise Integration - P1
"""

import logging
import hmac
import hashlib
import base64
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from security.vault_integration import VaultClient, get_vault_client

logger = logging.getLogger(__name__)


@dataclass
class NetSuiteTransaction:
    """Generic NetSuite transaction record."""
    id: str
    record_type: str  # salesorder, purchaseorder, itemfulfillment
    tranid: str  # Document number
    entity: str  # Customer/Vendor name
    trandate: datetime
    status: str
    total: float
    currency: str
    custom_fields: Dict[str, Any]


@dataclass
class NetSuiteItem:
    """NetSuite item/line item."""
    item_id: str
    name: str
    description: str
    quantity: float
    rate: float
    amount: float
    weight_kg: Optional[float] = None


class NetSuiteAuth:
    """
    NetSuite Token-based Authentication (TBA).
    
    Uses consumer key/secret and token key/secret
    with HMAC-SHA256 signature.
    """
    
    def __init__(
        self,
        account: str,
        consumer_key: str,
        consumer_secret: str,
        token_key: str,
        token_secret: str
    ):
        self.account = account
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.token_key = token_key
        self.token_secret = token_secret
    
    def generate_signature(self, method: str, url: str, nonce: str, timestamp: str) -> str:
        """Generate OAuth 1.0a signature."""
        # Build base string
        params = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_token": self.token_key,
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": timestamp,
            "oauth_nonce": nonce,
            "oauth_version": "1.0"
        }
        
        sorted_params = sorted(params.items())
        param_string = urlencode(sorted_params)
        
        base_string = f"{method.upper()}&{self._encode(url)}&{self._encode(param_string)}"
        
        # Signing key
        signing_key = f"{self._encode(self.consumer_secret)}&{self._encode(self.token_secret)}"
        
        # HMAC-SHA256
        signature = hmac.new(
            signing_key.encode(),
            base_string.encode(),
            hashlib.sha256
        ).digest()
        
        return base64.b64encode(signature).decode()
    
    def _encode(self, s: str) -> str:
        """URL encode string."""
        from urllib.parse import quote
        return quote(s, safe='')
    
    def get_auth_header(self, method: str, url: str) -> str:
        """Generate OAuth Authorization header."""
        import time
        import secrets
        
        nonce = secrets.token_urlsafe(16)
        timestamp = str(int(time.time()))
        
        signature = self.generate_signature(method, url, nonce, timestamp)
        
        auth_params = {
            "oauth_consumer_key": self.consumer_key,
            "oauth_token": self.token_key,
            "oauth_signature_method": "HMAC-SHA256",
            "oauth_timestamp": timestamp,
            "oauth_nonce": nonce,
            "oauth_version": "1.0",
            "oauth_signature": signature
        }
        
        auth_string = ", ".join([f'{k}="{v}"' for k, v in auth_params.items()])
        return f"OAuth {auth_string}"


class NetSuiteAdapter:
    """
    NetSuite RESTlet Adapter.
    
    Features:
    - Token-based authentication (TBA)
    - RESTlet endpoints for custom business logic
    - SuiteQL queries for complex data retrieval
    """
    
    def __init__(
        self,
        account: Optional[str] = None,
        consumer_key: Optional[str] = None,
        consumer_secret: Optional[str] = None,
        token_key: Optional[str] = None,
        token_secret: Optional[str] = None,
        vault_client: Optional[VaultClient] = None
    ):
        self.vault = vault_client or get_vault_client()
        
        # Get credentials
        if account and consumer_key and consumer_secret and token_key and token_secret:
            self.account = account
            self.auth = NetSuiteAuth(
                account=account,
                consumer_key=consumer_key,
                consumer_secret=consumer_secret,
                token_key=token_key,
                token_secret=token_secret
            )
        else:
            creds = self._get_credentials_from_vault()
            self.account = creds.get("account", "")
            self.auth = NetSuiteAuth(
                account=self.account,
                consumer_key=creds.get("consumer_key", ""),
                consumer_secret=creds.get("consumer_secret", ""),
                token_key=creds.get("token_key", ""),
                token_secret=creds.get("token_secret", "")
            )
        
        self.base_url = f"https://{self.account}.suitetalk.api.netsuite.com"
        self.client = None
    
    def _get_credentials_from_vault(self) -> Dict[str, str]:
        """Retrieve NetSuite credentials from Vault."""
        try:
            secret = self.vault.client.secrets.kv.v2.read_secret_version(
                path="erp/netsuite",
                mount_point="secret"
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to get NetSuite credentials: {e}")
            import os
            return {
                "account": os.getenv("NETSUITE_ACCOUNT", ""),
                "consumer_key": os.getenv("NETSUITE_CONSUMER_KEY", ""),
                "consumer_secret": os.getenv("NETSUITE_CONSUMER_SECRET", ""),
                "token_key": os.getenv("NETSUITE_TOKEN_KEY", ""),
                "token_secret": os.getenv("NETSUITE_TOKEN_SECRET", "")
            }
    
    async def __aenter__(self):
        """Async context manager."""
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context exit."""
        if self.client:
            await self.client.aclose()
    
    def _get_headers(self, method: str, url: str) -> Dict[str, str]:
        """Get request headers with OAuth."""
        return {
            "Authorization": self.auth.get_auth_header(method, url),
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated request."""
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(method, url)
        
        try:
            if method == "GET":
                response = await self.client.get(url, headers=headers)
            elif method == "POST":
                response = await self.client.post(url, headers=headers, json=data)
            elif method == "PATCH":
                response = await self.client.patch(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"NetSuite request failed: {e.response.status_code}")
            raise
    
    async def execute_suiteql(self, query: str) -> List[Dict[str, Any]]:
        """
        Execute SuiteQL query via RESTlet.
        
        SuiteQL is NetSuite's SQL-like query language.
        """
        endpoint = "/services/rest/query/v1/suiteql"
        
        data = {
            "q": query
        }
        
        try:
            result = await self._make_request("POST", endpoint, data)
            return result.get("items", [])
        except Exception as e:
            logger.error(f"SuiteQL execution failed: {e}")
            return []
    
    async def get_sales_orders(
        self,
        from_date: Optional[datetime] = None,
        status: Optional[str] = None
    ) -> List[NetSuiteTransaction]:
        """Get sales orders from NetSuite."""
        
        # Build SuiteQL query
        query = """
            SELECT 
                id, 
                transactionname as tranid, 
                entity, 
                trandate, 
                status, 
                total, 
                currency
            FROM transaction 
            WHERE type = 'SalesOrd'
        """
        
        if from_date:
            query += f" AND trandate >= '{from_date.strftime('%Y-%m-%d')}'"
        if status:
            query += f" AND status = '{status}'"
        
        query += " ORDER BY trandate DESC"
        
        try:
            results = await self.execute_suiteql(query)
            orders = []
            
            for row in results:
                order = NetSuiteTransaction(
                    id=str(row.get("id", "")),
                    record_type="salesorder",
                    tranid=row.get("tranid", ""),
                    entity=row.get("entity", ""),
                    trandate=datetime.strptime(row.get("trandate", ""), "%Y-%m-%d"),
                    status=row.get("status", ""),
                    total=float(row.get("total", 0)),
                    currency=row.get("currency", "USD"),
                    custom_fields={}
                )
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get sales orders: {e}")
            return []
    
    async def get_item_fulfillments(
        self,
        order_id: Optional[str] = None
    ) -> List[NetSuiteTransaction]:
        """Get item fulfillments (shipments)."""
        query = """
            SELECT 
                id, 
                transactionname as tranid, 
                createdfrom, 
                trandate, 
                status
            FROM transaction 
            WHERE type = 'ItemShip'
        """
        
        if order_id:
            query += f" AND createdfrom = {order_id}"
        
        try:
            results = await self.execute_suiteql(query)
            fulfillments = []
            
            for row in results:
                ff = NetSuiteTransaction(
                    id=str(row.get("id", "")),
                    record_type="itemfulfillment",
                    tranid=row.get("tranid", ""),
                    entity=row.get("entity", ""),
                    trandate=datetime.strptime(row.get("trandate", ""), "%Y-%m-%d"),
                    status=row.get("status", ""),
                    total=0,
                    currency="USD",
                    custom_fields={}
                )
                fulfillments.append(ff)
            
            return fulfillments
            
        except Exception as e:
            logger.error(f"Failed to get fulfillments: {e}")
            return []
    
    async def create_item_fulfillment(
        self,
        order_id: str,
        items: List[Dict[str, Any]],
        tracking_number: Optional[str] = None
    ) -> Optional[str]:
        """
        Create item fulfillment (shipment) for sales order.
        
        Args:
            order_id: Internal ID of sales order
            items: List of {item_id, quantity}
            tracking_number: Optional tracking number
            
        Returns:
            Internal ID of created fulfillment
        """
        endpoint = "/services/rest/record/v1/itemFulfillment"
        
        data = {
            "createdFrom": {"id": order_id},
            "shipStatus": {"id": "A"},  # Shipped
            "item": {
                "items": [
                    {
                        "item": {"id": item["item_id"]},
                        "quantity": item["quantity"]
                    }
                    for item in items
                ]
            }
        }
        
        if tracking_number:
            data["linkedTrackingNumbers"] = tracking_number
        
        try:
            result = await self._make_request("POST", endpoint, data)
            fulfillment_id = result.get("id")
            logger.info(f"Created item fulfillment: {fulfillment_id}")
            return fulfillment_id
        except Exception as e:
            logger.error(f"Failed to create fulfillment: {e}")
            return None
    
    async def update_order_status(
        self,
        order_id: str,
        status: str,
        memo: Optional[str] = None
    ) -> bool:
        """Update order status and add memo."""
        endpoint = f"/services/rest/record/v1/salesOrder/{order_id}"
        
        data = {}
        if status:
            data["orderStatus"] = {"id": status}
        if memo:
            data["memo"] = memo
        
        try:
            await self._make_request("PATCH", endpoint, data)
            return True
        except Exception as e:
            logger.error(f"Failed to update order {order_id}: {e}")
            return False
    
    async def search_items(self, query: str) -> List[NetSuiteItem]:
        """Search items by name/description."""
        suiteql = f"""
            SELECT 
                id, 
                itemid, 
                displayname, 
                salesdescription,
                weight
            FROM item 
            WHERE itemid LIKE '%{query}%' OR displayname LIKE '%{query}%'
        """
        
        try:
            results = await self.execute_suiteql(suiteql)
            items = []
            
            for row in results:
                item = NetSuiteItem(
                    item_id=str(row.get("id", "")),
                    name=row.get("itemid", ""),
                    description=row.get("displayname", ""),
                    quantity=0,
                    rate=0,
                    amount=0,
                    weight_kg=float(row.get("weight", 0)) if row.get("weight") else None
                )
                items.append(item)
            
            return items
            
        except Exception as e:
            logger.error(f"Failed to search items: {e}")
            return []
