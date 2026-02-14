// SPDX-License-Identifier: MIT
// AUTO-BROKER POD Smart Contract
// Polygon deployment for Proof of Delivery verification
// Enterprise Integration - P1

pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";

/**
 * @title PODSmartContract
 * @dev Stores Proof of Delivery records on Polygon blockchain
 * 
 * Features:
 * - Immutable delivery verification
 * - Multi-party signature (Carrier, Shipper, Consignee)
 * - Dispute resolution mechanism
 * - Integration with IPFS for document storage
 */
contract PODSmartContract is AccessControl, ReentrancyGuard {
    using ECDSA for bytes32;
    
    // ==================== Roles ====================
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant CARRIER_ROLE = keccak256("CARRIER_ROLE");
    bytes32 public constant SHIPPER_ROLE = keccak256("SHIPPER_ROLE");
    bytes32 public constant ARBITER_ROLE = keccak256("ARBITER_ROLE");
    
    // ==================== Enums ====================
    enum DeliveryStatus {
        PENDING,      // Shipment created, awaiting pickup
        IN_TRANSIT,   // Picked up, en route
        DELIVERED,    // Delivered, awaiting confirmation
        CONFIRMED,    // Confirmed by consignee
        DISPUTED,     // Under dispute
        RESOLVED      // Dispute resolved
    }
    
    // ==================== Structs ====================
    
    /**
     * @dev Delivery record structure
     */
    struct Delivery {
        string shipmentId;           // External shipment ID
        address carrier;             // Carrier wallet address
        address shipper;             // Shipper wallet address
        address consignee;           // Consignee wallet address
        string origin;               // Origin location hash
        string destination;          // Destination location hash
        uint256 pickupTime;          // Timestamp of pickup
        uint256 deliveryTime;        // Timestamp of delivery
        uint256 quantity;            // Quantity delivered
        DeliveryStatus status;       // Current status
        string ipfsDocumentHash;     // IPFS hash of POD document
        bytes32 documentHash;        // SHA256 hash of document
        bytes carrierSignature;      // Carrier's ECDSA signature
        bytes consigneeSignature;    // Consignee's ECDSA signature
        bool isDisputed;             // Dispute flag
        string disputeReason;        // Reason for dispute
        uint256 createdAt;           // Creation timestamp
        uint256 updatedAt;           // Last update timestamp
    }
    
    /**
     * @dev Dispute record structure
     */
    struct Dispute {
        string shipmentId;
        address initiator;
        string reason;
        uint256 amount;
        uint256 createdAt;
        bool resolved;
        string resolution;
        uint256 resolvedAt;
    }
    
    // ==================== State Variables ====================
    
    // Mapping from shipment ID to Delivery
    mapping(string => Delivery) public deliveries;
    
    // Mapping from shipment ID to Dispute
    mapping(string => Dispute) public disputes;
    
    // List of all shipment IDs
    string[] public shipmentList;
    
    // Document hash to shipment ID mapping (prevent duplicate docs)
    mapping(bytes32 => string) public documentToShipment;
    
    // Events
    event DeliveryCreated(
        string indexed shipmentId,
        address indexed carrier,
        address indexed shipper,
        uint256 createdAt
    );
    
    event PickupConfirmed(
        string indexed shipmentId,
        uint256 pickupTime,
        bytes carrierSignature
    );
    
    event DeliveryCompleted(
        string indexed shipmentId,
        uint256 deliveryTime,
        string ipfsHash
    );
    
    event DeliveryConfirmed(
        string indexed shipmentId,
        address indexed consignee,
        bytes consigneeSignature,
        uint256 confirmedAt
    );
    
    event DisputeOpened(
        string indexed shipmentId,
        address indexed initiator,
        string reason,
        uint256 amount
    );
    
    event DisputeResolved(
        string indexed shipmentId,
        string resolution,
        uint256 resolvedAt
    );
    
    event DocumentStored(
        string indexed shipmentId,
        bytes32 documentHash,
        string ipfsHash
    );
    
    // ==================== Constructor ====================
    
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
        _grantRole(ARBITER_ROLE, msg.sender);
    }
    
    // ==================== Modifiers ====================
    
    modifier onlyCarrier(string memory _shipmentId) {
        require(
            deliveries[_shipmentId].carrier == msg.sender ||
            hasRole(CARRIER_ROLE, msg.sender),
            "Not authorized: carrier only"
        );
        _;
    }
    
    modifier onlyConsignee(string memory _shipmentId) {
        require(
            deliveries[_shipmentId].consignee == msg.sender ||
            hasRole(ADMIN_ROLE, msg.sender),
            "Not authorized: consignee only"
        );
        _;
    }
    
    modifier onlyParticipant(string memory _shipmentId) {
        Delivery storage d = deliveries[_shipmentId];
        require(
            d.carrier == msg.sender ||
            d.shipper == msg.sender ||
            d.consignee == msg.sender ||
            hasRole(ADMIN_ROLE, msg.sender),
            "Not authorized: participant only"
        );
        _;
    }
    
    // ==================== Core Functions ====================
    
    /**
     * @dev Create a new delivery record
     * @param _shipmentId Unique shipment identifier
     * @param _carrier Carrier wallet address
     * @param _shipper Shipper wallet address
     * @param _consignee Consignee wallet address
     * @param _origin Origin location (hashed)
     * @param _destination Destination location (hashed)
     * @param _quantity Expected quantity
     */
    function createDelivery(
        string memory _shipmentId,
        address _carrier,
        address _shipper,
        address _consignee,
        string memory _origin,
        string memory _destination,
        uint256 _quantity
    ) external onlyRole(SHIPPER_ROLE) returns (bool) {
        require(bytes(deliveries[_shipmentId].shipmentId).length == 0, "Shipment already exists");
        require(_carrier != address(0), "Invalid carrier address");
        require(_consignee != address(0), "Invalid consignee address");
        
        deliveries[_shipmentId] = Delivery({
            shipmentId: _shipmentId,
            carrier: _carrier,
            shipper: _shipper,
            consignee: _consignee,
            origin: _origin,
            destination: _destination,
            pickupTime: 0,
            deliveryTime: 0,
            quantity: _quantity,
            status: DeliveryStatus.PENDING,
            ipfsDocumentHash: "",
            documentHash: 0,
            carrierSignature: "",
            consigneeSignature: "",
            isDisputed: false,
            disputeReason: "",
            createdAt: block.timestamp,
            updatedAt: block.timestamp
        });
        
        shipmentList.push(_shipmentId);
        
        emit DeliveryCreated(_shipmentId, _carrier, _shipper, block.timestamp);
        return true;
    }
    
    /**
     * @dev Confirm pickup by carrier
     * @param _shipmentId Shipment identifier
     * @param _signature Carrier's ECDSA signature
     */
    function confirmPickup(
        string memory _shipmentId,
        bytes memory _signature
    ) external onlyCarrier(_shipmentId) returns (bool) {
        Delivery storage d = deliveries[_shipmentId];
        require(d.status == DeliveryStatus.PENDING, "Invalid status");
        
        // Verify signature
        bytes32 messageHash = keccak256(abi.encodePacked(
            "PICKUP",
            _shipmentId,
            block.timestamp
        ));
        bytes32 ethSignedMessageHash = messageHash.toEthSignedMessageHash();
        address signer = ethSignedMessageHash.recover(_signature);
        require(signer == d.carrier, "Invalid carrier signature");
        
        d.pickupTime = block.timestamp;
        d.carrierSignature = _signature;
        d.status = DeliveryStatus.IN_TRANSIT;
        d.updatedAt = block.timestamp;
        
        emit PickupConfirmed(_shipmentId, block.timestamp, _signature);
        return true;
    }
    
    /**
     * @dev Complete delivery by carrier (upload POD)
     * @param _shipmentId Shipment identifier
     * @param _ipfsHash IPFS hash of POD document
     * @param _documentHash SHA256 hash of document content
     * @param _quantityDelivered Actual quantity delivered
     */
    function completeDelivery(
        string memory _shipmentId,
        string memory _ipfsHash,
        bytes32 _documentHash,
        uint256 _quantityDelivered
    ) external onlyCarrier(_shipmentId) returns (bool) {
        Delivery storage d = deliveries[_shipmentId];
        require(d.status == DeliveryStatus.IN_TRANSIT, "Invalid status");
        require(bytes(_ipfsHash).length > 0, "Invalid IPFS hash");
        require(_documentHash != 0, "Invalid document hash");
        require(bytes(documentToShipment[_documentHash]).length == 0, "Document already used");
        
        d.deliveryTime = block.timestamp;
        d.ipfsDocumentHash = _ipfsHash;
        d.documentHash = _documentHash;
        d.quantity = _quantityDelivered;
        d.status = DeliveryStatus.DELIVERED;
        d.updatedAt = block.timestamp;
        
        documentToShipment[_documentHash] = _shipmentId;
        
        emit DeliveryCompleted(_shipmentId, block.timestamp, _ipfsHash);
        emit DocumentStored(_shipmentId, _documentHash, _ipfsHash);
        return true;
    }
    
    /**
     * @dev Confirm delivery by consignee
     * @param _shipmentId Shipment identifier
     * @param _signature Consignee's ECDSA signature
     */
    function confirmDelivery(
        string memory _shipmentId,
        bytes memory _signature
    ) external onlyConsignee(_shipmentId) returns (bool) {
        Delivery storage d = deliveries[_shipmentId];
        require(d.status == DeliveryStatus.DELIVERED, "Delivery not completed");
        require(!d.isDisputed, "Delivery under dispute");
        
        // Verify signature
        bytes32 messageHash = keccak256(abi.encodePacked(
            "CONFIRM",
            _shipmentId,
            d.documentHash
        ));
        bytes32 ethSignedMessageHash = messageHash.toEthSignedMessageHash();
        address signer = ethSignedMessageHash.recover(_signature);
        require(signer == d.consignee, "Invalid consignee signature");
        
        d.consigneeSignature = _signature;
        d.status = DeliveryStatus.CONFIRMED;
        d.updatedAt = block.timestamp;
        
        emit DeliveryConfirmed(_shipmentId, d.consignee, _signature, block.timestamp);
        return true;
    }
    
    /**
     * @dev Open dispute on delivery
     * @param _shipmentId Shipment identifier
     * @param _reason Reason for dispute
     * @param _claimedAmount Amount in dispute
     */
    function openDispute(
        string memory _shipmentId,
        string memory _reason,
        uint256 _claimedAmount
    ) external onlyParticipant(_shipmentId) nonReentrant returns (bool) {
        Delivery storage d = deliveries[_shipmentId];
        require(
            d.status == DeliveryStatus.DELIVERED ||
            d.status == DeliveryStatus.CONFIRMED,
            "Invalid status for dispute"
        );
        require(!d.isDisputed, "Dispute already open");
        require(bytes(_reason).length > 0, "Reason required");
        
        d.isDisputed = true;
        d.disputeReason = _reason;
        d.status = DeliveryStatus.DISPUTED;
        d.updatedAt = block.timestamp;
        
        disputes[_shipmentId] = Dispute({
            shipmentId: _shipmentId,
            initiator: msg.sender,
            reason: _reason,
            amount: _claimedAmount,
            createdAt: block.timestamp,
            resolved: false,
            resolution: "",
            resolvedAt: 0
        });
        
        emit DisputeOpened(_shipmentId, msg.sender, _reason, _claimedAmount);
        return true;
    }
    
    /**
     * @dev Resolve dispute (arbiter only)
     * @param _shipmentId Shipment identifier
     * @param _resolution Resolution description
     */
    function resolveDispute(
        string memory _shipmentId,
        string memory _resolution
    ) external onlyRole(ARBITER_ROLE) returns (bool) {
        Delivery storage d = deliveries[_shipmentId];
        require(d.isDisputed, "No dispute to resolve");
        
        Dispute storage dispute = disputes[_shipmentId];
        dispute.resolved = true;
        dispute.resolution = _resolution;
        dispute.resolvedAt = block.timestamp;
        
        d.status = DeliveryStatus.RESOLVED;
        d.updatedAt = block.timestamp;
        
        emit DisputeResolved(_shipmentId, _resolution, block.timestamp);
        return true;
    }
    
    // ==================== View Functions ====================
    
    /**
     * @dev Get delivery details
     */
    function getDelivery(string memory _shipmentId) external view returns (Delivery memory) {
        return deliveries[_shipmentId];
    }
    
    /**
     * @dev Get dispute details
     */
    function getDispute(string memory _shipmentId) external view returns (Dispute memory) {
        return disputes[_shipmentId];
    }
    
    /**
     * @dev Verify document integrity
     */
    function verifyDocument(
        string memory _shipmentId,
        bytes32 _documentHash
    ) external view returns (bool) {
        return deliveries[_shipmentId].documentHash == _documentHash;
    }
    
    /**
     * @dev Get all shipments count
     */
    function getShipmentCount() external view returns (uint256) {
        return shipmentList.length;
    }
    
    /**
     * @dev Get shipments by page
     */
    function getShipmentsByPage(
        uint256 _page,
        uint256 _perPage
    ) external view returns (string[] memory) {
        uint256 start = _page * _perPage;
        require(start < shipmentList.length, "Page out of range");
        
        uint256 end = start + _perPage;
        if (end > shipmentList.length) {
            end = shipmentList.length;
        }
        
        string[] memory result = new string[](end - start);
        for (uint256 i = start; i < end; i++) {
            result[i - start] = shipmentList[i];
        }
        return result;
    }
    
    /**
     * @dev Check if delivery is fully verified
     */
    function isVerified(string memory _shipmentId) external view returns (bool) {
        Delivery storage d = deliveries[_shipmentId];
        return (
            d.status == DeliveryStatus.CONFIRMED ||
            (d.status == DeliveryStatus.RESOLVED && disputes[_shipmentId].resolved)
        );
    }
}