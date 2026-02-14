"""
AUTO-BROKER Microsoft Dynamics 365 Adapter
OData v4 integration for Dynamics 365 Finance & Supply Chain
Enterprise Integration - P1
"""

import logging
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import quote

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from security.vault_integration import VaultClient, get_vault_client

logger = logging.getLogger(__name__)


@dataclass
class D365SalesOrder:
    """D365 Sales Order Header."""
    sales_order_number: str
    customer_account: str
    ordering_customer_account: str
    requested_receipt_date: datetime
    confirmed_receipt_date: Optional[datetime]
    sales_order_status: str  # Backorder, Delivered, Invoiced, OpenOrder
    total_amount: float
    currency_code: str
    sales_tax_amount: float


@dataclass
class D365SalesOrderLine:
    """D365 Sales Order Line."""
    sales_order_number: str
    line_number: int
    item_number: str
    product_name: str
    ordered_quantity: float
    unit_price: float
    line_amount: float
    warehouse_id: str
    requested_receipt_date: datetime


@dataclass
class D365Customer:
    """D365 Customer (Account)."""
    customer_account: str
    name: str
    address: str
    city: str
    postal_code: str
    country_region_id: str
    vat_tax_registration_id: Optional[str]
    delivery_address: Dict[str, str]


@dataclass
class D365InventoryTransactionOrigin:
    """D365 Inventory Transaction Origin (delivery/shipment)."""
    inventory_transaction_origin_id: str
    reference_category: str
    reference_number: str
    transaction_date: datetime
    from_warehouse: str
    to_warehouse: Optional[str]
    quantity: float
    item_number: str


class D365Auth:
    """
    Microsoft Dynamics 365 OAuth 2.0 Authentication.
    
    Uses client credentials flow for server-to-server integration.
    Supports Azure AD token caching.
    """
    
    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        resource: str = "https://<org>.operations.dynamics.com"
    ):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.resource = resource
        self.token_endpoint = f"https://login.microsoftonline.com/{tenant_id}/oauth2/token"
        self._access_token: Optional[str] = None
        self._token_expires: Optional[datetime] = None
    
    async def get_token(self) -> str:
        """Get valid access token (with caching)."""
        if self._access_token and self._token_expires:
            if datetime.now() < self._token_expires - timedelta(minutes=5):
                return self._access_token
        
        # Request new token
        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "resource": self.resource
            }
            
            response = await client.post(
                self.token_endpoint,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            response.raise_for_status()
            
            token_data = response.json()
            self._access_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._token_expires = datetime.now() + timedelta(seconds=expires_in)
            
            return self._access_token
    
    async def get_auth_header(self) -> Dict[str, str]:
        """Get Authorization header."""
        token = await self.get_token()
        return {"Authorization": f"Bearer {token}"}


class Dynamics365Adapter:
    """
    Microsoft Dynamics 365 Finance & Supply Chain Adapter.
    
    Features:
    - OAuth 2.0 client credentials flow
    - OData v4 CRUD operations
    - Data entities: Sales Orders, Customers, Inventory
    - Azure AD token caching
    """
    
    def __init__(
        self,
        organization_url: Optional[str] = None,
        tenant_id: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        vault_client: Optional[VaultClient] = None
    ):
        self.vault = vault_client or get_vault_client()
        
        # Get credentials
        if all([organization_url, tenant_id, client_id, client_secret]):
            self.org_url = organization_url.rstrip('/')
            self.auth = D365Auth(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret,
                resource=organization_url
            )
        else:
            creds = self._get_credentials_from_vault()
            self.org_url = creds.get("organization_url", "").rstrip('/')
            self.auth = D365Auth(
                tenant_id=creds.get("tenant_id", ""),
                client_id=creds.get("client_id", ""),
                client_secret=creds.get("client_secret", ""),
                resource=self.org_url
            )
        
        self.data_url = f"{self.org_url}/data"
        self.client: Optional[httpx.AsyncClient] = None
    
    def _get_credentials_from_vault(self) -> Dict[str, str]:
        """Retrieve D365 credentials from Vault."""
        try:
            secret = self.vault.client.secrets.kv.v2.read_secret_version(
                path="erp/dynamics365",
                mount_point="secret"
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to get D365 credentials: {e}")
            import os
            return {
                "organization_url": os.getenv("D365_URL", ""),
                "tenant_id": os.getenv("D365_TENANT_ID", ""),
                "client_id": os.getenv("D365_CLIENT_ID", ""),
                "client_secret": os.getenv("D365_CLIENT_SECRET", "")
            }
    
    async def __aenter__(self):
        """Async context manager."""
        auth_headers = await self.auth.get_auth_header()
        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                **auth_headers,
                "Content-Type": "application/json",
                "Accept": "application/json",
                "OData-MaxVersion": "4.0",
                "OData-Version": "4.0"
            }
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context exit."""
        if self.client:
            await self.client.aclose()
    
    @retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=4, max=60))
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make authenticated OData request."""
        url = f"{self.data_url}{endpoint}"
        
        try:
            if method == "GET":
                response = await self.client.get(url, params=params)
            elif method == "POST":
                response = await self.client.post(url, json=data)
            elif method == "PATCH":
                response = await self.client.patch(url, json=data)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            
            # Some operations return empty body (204 No Content)
            if response.status_code == 204:
                return {}
            
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"D365 request failed: {e.response.status_code} - {e.response.text}")
            raise
    
    # ==================== Sales Orders ====================
    
    async def get_sales_orders(
        self,
        customer_account: Optional[str] = None,
        status: Optional[str] = None,
        from_date: Optional[datetime] = None
    ) -> List[D365SalesOrder]:
        """Get sales orders with optional filters."""
        endpoint = "/SalesOrderHeaders"
        
        # Build OData filter
        filters = []
        if customer_account:
            filters.append(f"OrderingCustomerAccount eq '{customer_account}'")
        if status:
            filters.append(f"SalesOrderStatus eq '{status}'")
        if from_date:
            date_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            filters.append(f"RequestedReceiptDate ge {date_str}")
        
        params = {"$top": 100}
        if filters:
            params["$filter"] = " and ".join(filters)
        
        try:
            result = await self._make_request("GET", endpoint, params=params)
            orders = []
            
            for item in result.get("value", []):
                order = D365SalesOrder(
                    sales_order_number=item.get("SalesOrderNumber", ""),
                    customer_account=item.get("CustomerAccount", ""),
                    ordering_customer_account=item.get("OrderingCustomerAccount", ""),
                    requested_receipt_date=self._parse_datetime(item.get("RequestedReceiptDate", "")),
                    confirmed_receipt_date=self._parse_datetime(item.get("ConfirmedReceiptDate", "")),
                    sales_order_status=item.get("SalesOrderStatus", ""),
                    total_amount=float(item.get("TotalAmount", 0)),
                    currency_code=item.get("CurrencyCode", ""),
                    sales_tax_amount=float(item.get("SalesTaxAmount", 0))
                )
                orders.append(order)
            
            return orders
            
        except Exception as e:
            logger.error(f"Failed to get sales orders: {e}")
            return []
    
    async def get_sales_order_lines(self, sales_order_number: str) -> List[D365SalesOrderLine]:
        """Get sales order lines."""
        endpoint = "/SalesOrderLines"
        params = {
            "$filter": f"SalesOrderNumber eq '{sales_order_number}'",
            "$orderby": "LineNumber"
        }
        
        try:
            result = await self._make_request("GET", endpoint, params=params)
            lines = []
            
            for item in result.get("value", []):
                line = D365SalesOrderLine(
                    sales_order_number=item.get("SalesOrderNumber", ""),
                    line_number=int(item.get("LineNumber", 0)),
                    item_number=item.get("ItemNumber", ""),
                    product_name=item.get("ProductName", ""),
                    ordered_quantity=float(item.get("OrderedSalesQuantity", 0)),
                    unit_price=float(item.get("SalesPrice", 0)),
                    line_amount=float(item.get("LineAmount", 0)),
                    warehouse_id=item.get("RequestedWarehouseId", ""),
                    requested_receipt_date=self._parse_datetime(item.get("RequestedReceiptDate", ""))
                )
                lines.append(line)
            
            return lines
            
        except Exception as e:
            logger.error(f"Failed to get sales order lines: {e}")
            return []
    
    async def create_sales_order(
        self,
        customer_account: str,
        lines: List[Dict[str, Any]],
        requested_date: Optional[datetime] = None
    ) -> Optional[str]:
        """
        Create sales order in D365.
        
        Args:
            customer_account: Customer account number
            lines: List of {item_number, quantity, unit_price}
            requested_date: Requested delivery date
            
        Returns:
            Sales order number
        """
        endpoint = "/SalesOrderHeaders"
        
        data = {
            "CustomerAccount": customer_account,
            "SalesOrderLines": [
                {
                    "ItemNumber": line["item_number"],
                    "OrderedSalesQuantity": line["quantity"],
                    "SalesPrice": line["unit_price"]
                }
                for line in lines
            ]
        }
        
        if requested_date:
            data["RequestedReceiptDate"] = requested_date.isoformat()
        
        try:
            result = await self._make_request("POST", endpoint, data=data)
            order_number = result.get("SalesOrderNumber")
            logger.info(f"Created sales order: {order_number}")
            return order_number
        except Exception as e:
            logger.error(f"Failed to create sales order: {e}")
            return None
    
    async def update_sales_order_status(
        self,
        sales_order_number: str,
        status: str
    ) -> bool:
        """Update sales order status."""
        # D365 uses entity keys: SalesOrderNumber
        encoded_order = quote(sales_order_number, safe='')
        endpoint = f"/SalesOrderHeaders(SalesOrderNumber='{encoded_order}')"
        
        data = {
            "SalesOrderStatus": status
        }
        
        try:
            await self._make_request("PATCH", endpoint, data=data)
            return True
        except Exception as e:
            logger.error(f"Failed to update order status: {e}")
            return False
    
    # ==================== Customers ====================
    
    async def get_customer(self, customer_account: str) -> Optional[D365Customer]:
        """Get customer details."""
        endpoint = f"/Customers('{customer_account}')"
        
        try:
            item = await self._make_request("GET", endpoint)
            
            return D365Customer(
                customer_account=item.get("CustomerAccount", ""),
                name=item.get("OrganizationName", ""),
                address=item.get("Address", ""),
                city=item.get("City", ""),
                postal_code=item.get("ZipCode", ""),
                country_region_id=item.get("CountryRegionId", ""),
                vat_tax_registration_id=item.get("VATTaxRegistrationId"),
                delivery_address={
                    "street": item.get("DeliveryAddressStreet", ""),
                    "city": item.get("DeliveryAddressCity", ""),
                    "zip": item.get("DeliveryAddressZipCode", "")
                }
            )
        except Exception as e:
            logger.error(f"Failed to get customer {customer_account}: {e}")
            return None
    
    async def search_customers(self, name_query: str) -> List[D365Customer]:
        """Search customers by name."""
        endpoint = "/Customers"
        params = {
            "$filter": f"contains(OrganizationName, '{name_query}')",
            "$top": 50
        }
        
        try:
            result = await self._make_request("GET", endpoint, params=params)
            customers = []
            
            for item in result.get("value", []):
                customer = D365Customer(
                    customer_account=item.get("CustomerAccount", ""),
                    name=item.get("OrganizationName", ""),
                    address=item.get("Address", ""),
                    city=item.get("City", ""),
                    postal_code=item.get("ZipCode", ""),
                    country_region_id=item.get("CountryRegionId", ""),
                    vat_tax_registration_id=item.get("VATTaxRegistrationId"),
                    delivery_address={}
                )
                customers.append(customer)
            
            return customers
            
        except Exception as e:
            logger.error(f"Failed to search customers: {e}")
            return []
    
    # ==================== Inventory ====================
    
    async def get_inventory_transactions(
        self,
        from_date: Optional[datetime] = None,
        item_number: Optional[str] = None
    ) -> List[D365InventoryTransactionOrigin]:
        """Get inventory transaction origins (shipments, receipts)."""
        endpoint = "/InventoryTransactionOrigins"
        
        filters = []
        if from_date:
            date_str = from_date.strftime("%Y-%m-%dT%H:%M:%SZ")
            filters.append(f"TransactionDate ge {date_str}")
        if item_number:
            filters.append(f"ItemNumber eq '{item_number}'")
        
        params = {"$top": 100}
        if filters:
            params["$filter"] = " and ".join(filters)
        
        try:
            result = await self._make_request("GET", endpoint, params=params)
            transactions = []
            
            for item in result.get("value", []):
                tx = D365InventoryTransactionOrigin(
                    inventory_transaction_origin_id=item.get("InventoryTransactionOriginId", ""),
                    reference_category=item.get("ReferenceCategory", ""),
                    reference_number=item.get("ReferenceNumber", ""),
                    transaction_date=self._parse_datetime(item.get("TransactionDate", "")),
                    from_warehouse=item.get("FromWarehouse", ""),
                    to_warehouse=item.get("ToWarehouse"),
                    quantity=float(item.get("Quantity", 0)),
                    item_number=item.get("ItemNumber", "")
                )
                transactions.append(tx)
            
            return transactions
            
        except Exception as e:
            logger.error(f"Failed to get inventory transactions: {e}")
            return []
    
    # ==================== Utilities ====================
    
    def _parse_datetime(self, value: str) -> Optional[datetime]:
        """Parse datetime from D365 format."""
        if not value:
            return None
        try:
            # D365 uses ISO 8601 with Z or offset
            value = value.replace('Z', '+00:00')
            return datetime.fromisoformat(value)
        except:
            return None
    
    async def test_connection(self) -> bool:
        """Test D365 connection."""
        try:
            await self._make_request("GET", "/$metadata")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
