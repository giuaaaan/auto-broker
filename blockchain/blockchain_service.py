"""
AUTO-BROKER Blockchain Service
Polygon smart contract interaction
Enterprise Integration - P1

Features:
- Web3 integration with Polygon (Matic)
- POD smart contract deployment and interaction
- IPFS integration for document storage
"""

import logging
import json
import hashlib
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from enum import Enum

from web3 import Web3
from web3.contract import Contract
from web3.types import TxReceipt, HexBytes
from eth_account import Account
from eth_account.datastructures import SignedMessage
import httpx

from security.vault_integration import get_vault_client
from services.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


class DeliveryStatus(Enum):
    """Delivery status from smart contract."""
    PENDING = 0
    IN_TRANSIT = 1
    DELIVERED = 2
    CONFIRMED = 3
    DISPUTED = 4
    RESOLVED = 5


@dataclass
class PODRecord:
    """Proof of Delivery record."""
    shipment_id: str
    carrier_address: str
    shipper_address: str
    consignee_address: str
    origin: str
    destination: str
    pickup_time: Optional[datetime]
    delivery_time: Optional[datetime]
    quantity: int
    status: DeliveryStatus
    ipfs_hash: str
    document_hash: str
    is_disputed: bool
    dispute_reason: Optional[str]
    created_at: datetime
    updated_at: datetime


@dataclass
class DisputeRecord:
    """Dispute record."""
    shipment_id: str
    initiator: str
    reason: str
    amount: int
    created_at: datetime
    resolved: bool
    resolution: Optional[str]
    resolved_at: Optional[datetime]


class IPFSClient:
    """IPFS client for document storage."""
    
    def __init__(self, api_url: str = "http://localhost:5001", gateway_url: str = "https://ipfs.io"):
        self.api_url = api_url.rstrip('/')
        self.gateway_url = gateway_url.rstrip('/')
        self.http_client = httpx.AsyncClient(timeout=60.0)
    
    async def upload_document(self, content: bytes, filename: str = "document.pdf") -> Optional[str]:
        """Upload document to IPFS."""
        try:
            files = {'file': (filename, content)}
            response = await self.http_client.post(
                f"{self.api_url}/api/v0/add",
                files=files
            )
            response.raise_for_status()
            result = response.json()
            return result.get("Hash")
        except Exception as e:
            logger.error(f"Failed to upload to IPFS: {e}")
            return None
    
    async def get_document(self, ipfs_hash: str) -> Optional[bytes]:
        """Retrieve document from IPFS."""
        try:
            response = await self.http_client.get(
                f"{self.gateway_url}/ipfs/{ipfs_hash}",
                timeout=30.0
            )
            response.raise_for_status()
            return response.content
        except Exception as e:
            logger.error(f"Failed to retrieve from IPFS: {e}")
            return None
    
    def get_gateway_url(self, ipfs_hash: str) -> str:
        """Get gateway URL for IPFS hash."""
        return f"{self.gateway_url}/ipfs/{ipfs_hash}"


class BlockchainService:
    """
    Polygon Blockchain Service for POD Smart Contract.
    
    Features:
    - Smart contract deployment and interaction
    - Transaction signing with Vault-stored keys
    - IPFS integration for document storage
    - Event listening for delivery updates
    """
    
    # Contract ABI - would be loaded from compiled contract
    CONTRACT_ABI = [
        {
            "inputs": [],
            "stateMutability": "nonpayable",
            "type": "constructor"
        },
        {
            "inputs": [
                {"name": "_shipmentId", "type": "string"},
                {"name": "_carrier", "type": "address"},
                {"name": "_shipper", "type": "address"},
                {"name": "_consignee", "type": "address"},
                {"name": "_origin", "type": "string"},
                {"name": "_destination", "type": "string"},
                {"name": "_quantity", "type": "uint256"}
            ],
            "name": "createDelivery",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "_shipmentId", "type": "string"},
                {"name": "_signature", "type": "bytes"}
            ],
            "name": "confirmPickup",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "_shipmentId", "type": "string"},
                {"name": "_ipfsHash", "type": "string"},
                {"name": "_documentHash", "type": "bytes32"},
                {"name": "_quantityDelivered", "type": "uint256"}
            ],
            "name": "completeDelivery",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [
                {"name": "_shipmentId", "type": "string"},
                {"name": "_signature", "type": "bytes"}
            ],
            "name": "confirmDelivery",
            "outputs": [{"name": "", "type": "bool"}],
            "stateMutability": "nonpayable",
            "type": "function"
        },
        {
            "inputs": [{"name": "_shipmentId", "type": "string"}],
            "name": "getDelivery",
            "outputs": [{"components": [
                {"name": "shipmentId", "type": "string"},
                {"name": "carrier", "type": "address"},
                {"name": "shipper", "type": "address"},
                {"name": "consignee", "type": "address"},
                {"name": "origin", "type": "string"},
                {"name": "destination", "type": "string"},
                {"name": "pickupTime", "type": "uint256"},
                {"name": "deliveryTime", "type": "uint256"},
                {"name": "quantity", "type": "uint256"},
                {"name": "status", "type": "uint8"},
                {"name": "ipfsDocumentHash", "type": "string"},
                {"name": "documentHash", "type": "bytes32"},
                {"name": "carrierSignature", "type": "bytes"},
                {"name": "consigneeSignature", "type": "bytes"},
                {"name": "isDisputed", "type": "bool"},
                {"name": "disputeReason", "type": "string"},
                {"name": "createdAt", "type": "uint256"},
                {"name": "updatedAt", "type": "uint256"}
            ], "name": "", "type": "tuple"}],
            "stateMutability": "view",
            "type": "function"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "shipmentId", "type": "string"},
                {"indexed": True, "name": "carrier", "type": "address"},
                {"indexed": True, "name": "shipper", "type": "address"},
                {"name": "createdAt", "type": "uint256"}
            ],
            "name": "DeliveryCreated",
            "type": "event"
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "shipmentId", "type": "string"},
                {"name": "deliveryTime", "type": "uint256"},
                {"name": "ipfsHash", "type": "string"}
            ],
            "name": "DeliveryCompleted",
            "type": "event"
        }
    ]
    
    def __init__(
        self,
        provider_url: Optional[str] = None,
        contract_address: Optional[str] = None,
        ipfs_url: Optional[str] = None,
        vault_client = None
    ):
        """
        Initialize blockchain service.
        
        Args:
            provider_url: Polygon RPC URL
            contract_address: Deployed contract address
            ipfs_url: IPFS API URL
        """
        self.vault = vault_client or get_vault_client()
        
        # Load configuration
        if provider_url and contract_address:
            self.provider_url = provider_url
            self.contract_address = contract_address
        else:
            config = self._load_config()
            self.provider_url = config.get("provider_url", "https://polygon-rpc.com")
            self.contract_address = config.get("contract_address", "")
        
        # Initialize Web3
        self.w3 = Web3(Web3.HTTPProvider(self.provider_url))
        
        if not self.w3.is_connected():
            raise Exception("Failed to connect to Polygon network")
        
        # Load contract
        if self.contract_address:
            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=self.CONTRACT_ABI
            )
        else:
            self.contract = None
        
        # Initialize IPFS
        self.ipfs = IPFSClient(api_url=ipfs_url or "http://localhost:5001")
        
        # Circuit breaker
        self.circuit = CircuitBreaker(
            name="blockchain",
            failure_threshold=3,
            recovery_timeout=60
        )
        
        self._account: Optional[Account] = None
        self._private_key: Optional[str] = None
    
    def _load_config(self) -> Dict[str, str]:
        """Load blockchain configuration from Vault."""
        try:
            secret = self.vault.client.secrets.kv.v2.read_secret_version(
                path="blockchain/polygon",
                mount_point="secret"
            )
            return secret["data"]["data"]
        except Exception as e:
            logger.error(f"Failed to load blockchain config: {e}")
            import os
            return {
                "provider_url": os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com"),
                "contract_address": os.getenv("POD_CONTRACT_ADDRESS", "")
            }
    
    async def _load_account(self) -> Account:
        """Load signing account from Vault."""
        if self._account:
            return self._account
        
        try:
            secret = self.vault.client.secrets.kv.v2.read_secret_version(
                path="blockchain/wallet",
                mount_point="secret"
            )
            self._private_key = secret["data"]["data"]["private_key"]
            self._account = Account.from_key(self._private_key)
            return self._account
        except Exception as e:
            logger.error(f"Failed to load wallet: {e}")
            raise
    
    async def _send_transaction(
        self,
        function_call,
        value: int = 0
    ) -> Optional[TxReceipt]:
        """Send transaction to blockchain."""
        try:
            account = await self._load_account()
            
            # Build transaction
            tx = function_call.build_transaction({
                'from': account.address,
                'nonce': self.w3.eth.get_transaction_count(account.address),
                'gas': 2000000,
                'gasPrice': self.w3.to_wei('50', 'gwei'),
                'value': value
            })
            
            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self._private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                logger.info(f"Transaction successful: {tx_hash.hex()}")
                return receipt
            else:
                logger.error(f"Transaction failed: {tx_hash.hex()}")
                return None
                
        except Exception as e:
            logger.error(f"Transaction error: {e}")
            return None
    
    # ==================== POD Operations ====================
    
    async def create_delivery(
        self,
        shipment_id: str,
        carrier_address: str,
        shipper_address: str,
        consignee_address: str,
        origin: str,
        destination: str,
        quantity: int
    ) -> Optional[str]:
        """
        Create new delivery record on blockchain.
        
        Returns transaction hash.
        """
        if not self.contract:
            raise Exception("Contract not deployed")
        
        try:
            function = self.contract.functions.createDelivery(
                shipment_id,
                Web3.to_checksum_address(carrier_address),
                Web3.to_checksum_address(shipper_address),
                Web3.to_checksum_address(consignee_address),
                origin,
                destination,
                quantity
            )
            
            receipt = await self._send_transaction(function)
            return receipt.transactionHash.hex() if receipt else None
            
        except Exception as e:
            logger.error(f"Failed to create delivery: {e}")
            return None
    
    async def upload_pod_document(
        self,
        shipment_id: str,
        document_content: bytes,
        filename: str = "pod.pdf"
    ) -> Optional[Dict[str, str]]:
        """
        Upload POD document to IPFS and return hashes.
        
        Returns:
            {'ipfs_hash': '...', 'document_hash': '0x...'}
        """
        # Upload to IPFS
        ipfs_hash = await self.ipfs.upload_document(document_content, filename)
        if not ipfs_hash:
            return None
        
        # Calculate document hash
        document_hash = hashlib.sha256(document_content).hexdigest()
        document_hash_bytes = '0x' + document_hash
        
        return {
            'ipfs_hash': ipfs_hash,
            'document_hash': document_hash_bytes
        }
    
    async def complete_delivery(
        self,
        shipment_id: str,
        document_content: bytes,
        quantity_delivered: int,
        filename: str = "pod.pdf"
    ) -> Optional[Dict[str, str]]:
        """
        Complete delivery with POD document.
        
        Uploads to IPFS and records on blockchain.
        """
        # Upload document
        doc_info = await self.upload_pod_document(shipment_id, document_content, filename)
        if not doc_info:
            return None
        
        # Call contract
        try:
            function = self.contract.functions.completeDelivery(
                shipment_id,
                doc_info['ipfs_hash'],
                doc_info['document_hash'],
                quantity_delivered
            )
            
            receipt = await self._send_transaction(function)
            
            if receipt:
                return {
                    'transaction_hash': receipt.transactionHash.hex(),
                    'ipfs_hash': doc_info['ipfs_hash'],
                    'document_hash': doc_info['document_hash'],
                    'block_number': receipt.blockNumber
                }
            return None
            
        except Exception as e:
            logger.error(f"Failed to complete delivery: {e}")
            return None
    
    async def confirm_delivery(
        self,
        shipment_id: str
    ) -> Optional[str]:
        """Confirm delivery by consignee."""
        # Generate signature
        account = await self._load_account()
        
        # Get delivery to get document hash
        delivery = await self.get_delivery(shipment_id)
        if not delivery:
            return None
        
        # Create message hash
        message = f"CONFIRM:{shipment_id}:{delivery.document_hash}"
        message_hash = hashlib.sha256(message.encode()).hexdigest()
        
        # Sign
        signed = account.sign_message(message_hash)
        signature = signed.signature.hex()
        
        # Call contract
        try:
            function = self.contract.functions.confirmDelivery(
                shipment_id,
                signature
            )
            
            receipt = await self._send_transaction(function)
            return receipt.transactionHash.hex() if receipt else None
            
        except Exception as e:
            logger.error(f"Failed to confirm delivery: {e}")
            return None
    
    async def get_delivery(self, shipment_id: str) -> Optional[PODRecord]:
        """Get delivery record from blockchain."""
        if not self.contract:
            return None
        
        try:
            result = self.contract.functions.getDelivery(shipment_id).call()
            
            return PODRecord(
                shipment_id=result[0],
                carrier_address=result[1],
                shipper_address=result[2],
                consignee_address=result[3],
                origin=result[4],
                destination=result[5],
                pickup_time=datetime.fromtimestamp(result[6]) if result[6] > 0 else None,
                delivery_time=datetime.fromtimestamp(result[7]) if result[7] > 0 else None,
                quantity=result[8],
                status=DeliveryStatus(result[9]),
                ipfs_hash=result[10],
                document_hash=result[11].hex() if result[11] else "",
                is_disputed=result[14],
                dispute_reason=result[15] if result[15] else None,
                created_at=datetime.fromtimestamp(result[16]),
                updated_at=datetime.fromtimestamp(result[17])
            )
            
        except Exception as e:
            logger.error(f"Failed to get delivery: {e}")
            return None
    
    async def verify_document(
        self,
        shipment_id: str,
        document_content: bytes
    ) -> bool:
        """Verify document integrity against blockchain record."""
        delivery = await self.get_delivery(shipment_id)
        if not delivery:
            return False
        
        # Calculate hash
        calculated_hash = hashlib.sha256(document_content).hexdigest()
        
        return calculated_hash == delivery.document_hash
    
    # ==================== Event Listening ====================
    
    def listen_for_events(
        self,
        event_callback: Callable[[str, Dict], None],
        poll_interval: int = 15
    ):
        """
        Start listening for blockchain events.
        
        Args:
            event_callback: Function called with (event_name, event_data)
            poll_interval: Seconds between polls
        """
        if not self.contract:
            logger.error("Contract not deployed, cannot listen for events")
            return
        
        def event_loop():
            last_block = self.w3.eth.block_number
            
            while True:
                try:
                    current_block = self.w3.eth.block_number
                    
                    if current_block > last_block:
                        # Get events
                        events = self.contract.events.DeliveryCompleted().get_logs(
                            fromBlock=last_block + 1,
                            toBlock=current_block
                        )
                        
                        for event in events:
                            event_callback("DeliveryCompleted", {
                                'shipment_id': event.args.shipmentId,
                                'delivery_time': event.args.deliveryTime,
                                'ipfs_hash': event.args.ipfsHash
                            })
                        
                        last_block = current_block
                    
                    asyncio.sleep(poll_interval)
                    
                except Exception as e:
                    logger.error(f"Event listening error: {e}")
                    asyncio.sleep(poll_interval)
        
        # Run in background thread
        import threading
        thread = threading.Thread(target=event_loop, daemon=True)
        thread.start()
    
    # ==================== Utilities ====================
    
    async def deploy_contract(self) -> Optional[str]:
        """
        Deploy POD smart contract.
        
        Returns contract address.
        """
        # Load bytecode from compiled contract
        try:
            with open('blockchain/pod_contract_bytecode.json', 'r') as f:
                compiled = json.load(f)
                bytecode = compiled['bytecode']
                abi = compiled['abi']
        except FileNotFoundError:
            logger.error("Contract bytecode not found")
            return None
        
        try:
            # Deploy
            Contract = self.w3.eth.contract(abi=abi, bytecode=bytecode)
            
            account = await self._load_account()
            
            tx = Contract.constructor().build_transaction({
                'from': account.address,
                'nonce': self.w3.eth.get_transaction_count(account.address),
                'gas': 3000000,
                'gasPrice': self.w3.to_wei('50', 'gwei')
            })
            
            signed_tx = self.w3.eth.account.sign_transaction(tx, self._private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
            
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
            
            if receipt['status'] == 1:
                address = receipt['contractAddress']
                logger.info(f"Contract deployed at: {address}")
                self.contract_address = address
                self.contract = self.w3.eth.contract(address=address, abi=abi)
                return address
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to deploy contract: {e}")
            return None
    
    async def estimate_gas_price(self) -> Dict[str, float]:
        """Get current gas price estimates."""
        try:
            gas_price = self.w3.eth.gas_price
            return {
                'safe_low': self.w3.from_wei(int(gas_price * 0.9), 'gwei'),
                'standard': self.w3.from_wei(gas_price, 'gwei'),
                'fast': self.w3.from_wei(int(gas_price * 1.2), 'gwei'),
                'rapid': self.w3.from_wei(int(gas_price * 1.5), 'gwei')
            }
        except Exception as e:
            logger.error(f"Failed to estimate gas: {e}")
            return {}
