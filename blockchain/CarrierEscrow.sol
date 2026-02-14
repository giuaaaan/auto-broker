// SPDX-License-Identifier: MIT
// AUTO-BROKER: Carrier Escrow Smart Contract
// Gestisce pagamenti escrow ai carrier con supporto failover atomico
// Parte del sistema Self-Healing Supply Chain (PAOLO Agent)

pragma solidity ^0.8.19;

import "@openzeppelin/contracts/access/AccessControl.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

/**
 * @title CarrierEscrow
 * @dev Gestisce escrow per pagamenti carrier con atomicità su failover
 * 
 * Features:
 * - Lock fondi al carrier iniziale
 * - Atomic transfer a nuovo carrier in caso di failover
 * - Release condizionato (delivery + no dispute)
 * - Refund al shipper in caso di dispute risolta a favore cliente
 * - Audit trail completo su blockchain
 */
contract CarrierEscrow is AccessControl, ReentrancyGuard, Pausable {
    
    // ==================== Roles ====================
    bytes32 public constant PAOLO_AGENT_ROLE = keccak256("PAOLO_AGENT_ROLE");
    bytes32 public constant GIULIA_AGENT_ROLE = keccak256("GIULIA_AGENT_ROLE");
    bytes32 public constant ADMIN_ROLE = keccak256("ADMIN_ROLE");
    bytes32 public constant SHIPPER_ROLE = keccak256("SHIPPER_ROLE");
    
    // ==================== Enums ====================
    enum EscrowStatus {
        LOCKED,           // Fondi bloccati, attesa delivery
        RELEASED,         // Fondi rilasciati al carrier
        REFUNDED,         // Fondi rimborsati al shipper
        TRANSFERRED,      // Fondi trasferiti a nuovo carrier (failover)
        DISPUTED,         // In dispute
        RESOLVED          // Dispute risolta
    }
    
    enum FailoverReason {
        CARRIER_DELAY,    // Carrier in ritardo
        CARRIER_FAILURE,  // Carrier fallito/non risponde
        PERFORMANCE_DROP, // Performance scesa sotto soglia
        MANUAL_OVERRIDE   // Override manuale admin
    }
    
    // ==================== Structs ====================
    
    /**
     * @dev Record escrow per shipment
     */
    struct Escrow {
        string shipmentId;
        address shipper;           // Chi ha depositato i fondi
        address carrier;           // Carrier attuale
        address originalCarrier;   // Carrier originale (per audit)
        uint256 amount;            // Amount in escrow
        uint256 deadline;          // Deadline per delivery
        EscrowStatus status;
        bool delivered;
        bool disputed;
        uint256 createdAt;
        uint256 updatedAt;
        uint256 failoverCount;     // Numero di failover eseguiti
        bytes32 lastActionHash;    // Hash ultima azione (audit)
    }
    
    /**
     * @dev Record failover per audit trail
     */
    struct FailoverRecord {
        string shipmentId;
        address fromCarrier;
        address toCarrier;
        FailoverReason reason;
        uint256 timestamp;
        bytes32 evidenceHash;      // Hash evidence (IPFS)
        address executedBy;        // Paolo Agent address
    }
    
    /**
     * @dev Record decisione dispute per audit
     */
    struct DisputeResolution {
        string shipmentId;
        bool carrierWins;
        uint256 refundAmount;
        bytes32 evidenceHash;
        string aiAnalysisHash;     // Hash risultato analisi AI
        uint256 confidence;        // Confidence score (0-100)
        uint256 timestamp;
        address resolvedBy;        // Giulia Agent address
    }
    
    // ==================== State Variables ====================
    
    // Mapping shipment ID -> Escrow
    mapping(string => Escrow) public escrows;
    
    // Mapping shipment ID -> lista failover
    mapping(string => FailoverRecord[]) public failoverHistory;
    
    // Mapping shipment ID -> dispute resolution
    mapping(string => DisputeResolution) public disputeResolutions;
    
    // Lista shipment IDs attivi
    string[] public activeShipments;
    
    // Counter statistiche
    uint256 public totalEscrows;
    uint256 public totalFailovers;
    uint256 public totalDisputes;
    uint256 public totalVolume;      // Volume totale in wei
    
    // Limiti per human-in-the-loop
    uint256 public constant AUTO_FAILOVER_LIMIT = 10_000 ether;  // Max 10k EUR senza approvazione
    uint256 public constant AUTO_RESOLUTION_LIMIT = 5_000 ether; // Max 5k EUR per auto-resolve
    
    // Events
    event FundsLocked(
        string indexed shipmentId,
        address indexed shipper,
        address indexed carrier,
        uint256 amount,
        uint256 deadline
    );
    
    event FundsReleased(
        string indexed shipmentId,
        address indexed carrier,
        uint256 amount,
        bytes32 proofHash
    );
    
    event FundsRefunded(
        string indexed shipmentId,
        address indexed shipper,
        uint256 amount,
        string reason
    );
    
    event CarrierTransferred(
        string indexed shipmentId,
        address indexed fromCarrier,
        address indexed toCarrier,
        uint256 timestamp,
        FailoverReason reason
    );
    
    event DisputeOpened(
        string indexed shipmentId,
        address indexed initiator,
        uint256 claimedAmount
    );
    
    event DisputeResolved(
        string indexed shipmentId,
        bool indexed carrierWins,
        uint256 refundAmount,
        bytes32 evidenceHash,
        uint256 confidence
    );
    
    event DeadlineExtended(
        string indexed shipmentId,
        uint256 oldDeadline,
        uint256 newDeadline
    );
    
    event EmergencyPause(
        address indexed triggeredBy,
        string reason
    );
    
    // ==================== Modifiers ====================
    
    modifier onlyPaoloAgent() {
        require(hasRole(PAOLO_AGENT_ROLE, msg.sender), "Not authorized: Paolo Agent only");
        _;
    }
    
    modifier onlyGiuliaAgent() {
        require(hasRole(GIULIA_AGENT_ROLE, msg.sender), "Not authorized: Giulia Agent only");
        _;
    }
    
    modifier escrowExists(string memory _shipmentId) {
        require(escrows[_shipmentId].createdAt > 0, "Escrow does not exist");
        _;
    }
    
    modifier notDisputed(string memory _shipmentId) {
        require(!escrows[_shipmentId].disputed, "Escrow under dispute");
        _;
    }
    
    // ==================== Constructor ====================
    
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(ADMIN_ROLE, msg.sender);
    }
    
    // ==================== Core Functions ====================
    
    /**
     * @dev Blocca fondi per una spedizione
     * @param _shipmentId ID shipment
     * @param _carrier Wallet address carrier
     * @param _durationDays Giorni entro cui consegnare
     */
    function lockFunds(
        string memory _shipmentId,
        address _carrier,
        uint256 _durationDays
    ) external payable onlyRole(SHIPPER_ROLE) whenNotPaused returns (bool) {
        require(msg.value > 0, "Amount must be greater than 0");
        require(_carrier != address(0), "Invalid carrier address");
        require(escrows[_shipmentId].createdAt == 0, "Escrow already exists");
        require(_durationDays > 0 && _durationDays <= 30, "Invalid duration");
        
        uint256 deadline = block.timestamp + (_durationDays * 1 days);
        
        escrows[_shipmentId] = Escrow({
            shipmentId: _shipmentId,
            shipper: msg.sender,
            carrier: _carrier,
            originalCarrier: _carrier,
            amount: msg.value,
            deadline: deadline,
            status: EscrowStatus.LOCKED,
            delivered: false,
            disputed: false,
            createdAt: block.timestamp,
            updatedAt: block.timestamp,
            failoverCount: 0,
            lastActionHash: keccak256(abi.encodePacked("LOCK", _shipmentId, msg.value))
        });
        
        activeShipments.push(_shipmentId);
        totalEscrows++;
        totalVolume += msg.value;
        
        emit FundsLocked(_shipmentId, msg.sender, _carrier, msg.value, deadline);
        return true;
    }
    
    /**
     * @dev Rilascia fondi al carrier dopo delivery confermata
     * @param _shipmentId ID shipment
     * @param _proofHash Hash proof of delivery (IPFS)
     */
    function releaseFunds(
        string memory _shipmentId,
        bytes32 _proofHash
    ) external onlyPaoloAgent nonReentrant escrowExists(_shipmentId) notDisputed(_shipmentId) returns (bool) {
        Escrow storage e = escrows[_shipmentId];
        
        require(e.status == EscrowStatus.LOCKED, "Invalid status");
        require(e.delivered, "Delivery not confirmed");
        require(block.timestamp <= e.deadline, "Deadline exceeded");
        
        e.status = EscrowStatus.RELEASED;
        e.updatedAt = block.timestamp;
        e.lastActionHash = keccak256(abi.encodePacked("RELEASE", _shipmentId, _proofHash));
        
        // Rimuovi da active
        _removeActiveShipment(_shipmentId);
        
        // Trasferisci fondi
        (bool success, ) = payable(e.carrier).call{value: e.amount}("");
        require(success, "Transfer failed");
        
        emit FundsReleased(_shipmentId, e.carrier, e.amount, _proofHash);
        return true;
    }
    
    /**
     * @dev Trasferisce fondi a nuovo carrier (failover atomico)
     * @param _shipmentId ID shipment
     * @param _newCarrier Nuovo carrier
     * @param _reason Motivo failover
     * @param _evidenceHash Hash evidence (IPFS)
     */
    function transferToNewCarrier(
        string memory _shipmentId,
        address _newCarrier,
        FailoverReason _reason,
        bytes32 _evidenceHash
    ) external onlyPaoloAgent nonReentrant escrowExists(_shipmentId) notDisputed(_shipmentId) returns (bool) {
        Escrow storage e = escrows[_shipmentId];
        
        require(e.status == EscrowStatus.LOCKED, "Invalid status");
        require(!e.delivered, "Already delivered");
        require(_newCarrier != address(0), "Invalid new carrier");
        require(_newCarrier != e.carrier, "Same carrier");
        
        // Human-in-the-loop per importi alti
        if (e.amount > AUTO_FAILOVER_LIMIT) {
            require(hasRole(ADMIN_ROLE, msg.sender), "High value: admin approval required");
        }
        
        address oldCarrier = e.carrier;
        
        // Registra failover
        FailoverRecord memory record = FailoverRecord({
            shipmentId: _shipmentId,
            fromCarrier: oldCarrier,
            toCarrier: _newCarrier,
            reason: _reason,
            timestamp: block.timestamp,
            evidenceHash: _evidenceHash,
            executedBy: msg.sender
        });
        
        failoverHistory[_shipmentId].push(record);
        
        // Aggiorna escrow
        e.carrier = _newCarrier;
        e.status = EscrowStatus.TRANSFERRED;
        e.failoverCount++;
        e.updatedAt = block.timestamp;
        e.lastActionHash = keccak256(abi.encodePacked("TRANSFER", _shipmentId, _newCarrier));
        
        // Extended deadline (+1 giorno per nuovo carrier)
        uint256 oldDeadline = e.deadline;
        e.deadline = block.timestamp + 1 days;
        
        totalFailovers++;
        
        emit CarrierTransferred(_shipmentId, oldCarrier, _newCarrier, block.timestamp, _reason);
        emit DeadlineExtended(_shipmentId, oldDeadline, e.deadline);
        
        return true;
    }
    
    /**
     * @dev Marca delivery come completata (chiamato da POD contract)
     * @param _shipmentId ID shipment
     */
    function markDelivered(
        string memory _shipmentId
    ) external onlyPaoloAgent escrowExists(_shipmentId) returns (bool) {
        Escrow storage e = escrows[_shipmentId];
        require(!e.delivered, "Already delivered");
        
        e.delivered = true;
        e.updatedAt = block.timestamp;
        e.lastActionHash = keccak256(abi.encodePacked("DELIVERED", _shipmentId));
        
        return true;
    }
    
    /**
     * @dev Apre dispute su escrow
     * @param _shipmentId ID shipment
     * @param _claimedAmount Amount contestato
     */
    function openDispute(
        string memory _shipmentId,
        uint256 _claimedAmount
    ) external escrowExists(_shipmentId) returns (bool) {
        Escrow storage e = escrows[_shipmentId];
        
        require(msg.sender == e.shipper || hasRole(GIULIA_AGENT_ROLE, msg.sender), "Not authorized");
        require(!e.disputed, "Dispute already open");
        require(e.status == EscrowStatus.LOCKED || e.status == EscrowStatus.TRANSFERRED, "Invalid status");
        
        e.disputed = true;
        e.status = EscrowStatus.DISPUTED;
        e.updatedAt = block.timestamp;
        
        totalDisputes++;
        
        emit DisputeOpened(_shipmentId, msg.sender, _claimedAmount);
        return true;
    }
    
    /**
     * @dev Risolve dispute (Giulia Agent)
     * @param _shipmentId ID shipment
     * @param _carrierWins True se carrier vince
     * @param _refundAmount Amount da rimborsare (se carrier non vince)
     * @param _evidenceHash Hash evidence
     * @param _aiAnalysisHash Hash analisi AI
     * @param _confidence Confidence score (0-100)
     */
    function resolveDispute(
        string memory _shipmentId,
        bool _carrierWins,
        uint256 _refundAmount,
        bytes32 _evidenceHash,
        bytes32 _aiAnalysisHash,
        uint256 _confidence
    ) external onlyGiuliaAgent nonReentrant escrowExists(_shipmentId) returns (bool) {
        Escrow storage e = escrows[_shipmentId];
        
        require(e.disputed, "No dispute to resolve");
        require(e.status == EscrowStatus.DISPUTED, "Invalid status");
        require(_confidence <= 100, "Invalid confidence");
        
        // Human-in-the-loop per importi alti o confidence bassa
        if (e.amount > AUTO_RESOLUTION_LIMIT || _confidence < 85) {
            require(hasRole(ADMIN_ROLE, msg.sender), "High value/low confidence: admin required");
        }
        
        // Registra risoluzione
        DisputeResolution memory resolution = DisputeResolution({
            shipmentId: _shipmentId,
            carrierWins: _carrierWins,
            refundAmount: _carrierWins ? 0 : _refundAmount,
            evidenceHash: _evidenceHash,
            aiAnalysisHash: _aiAnalysisHash,
            confidence: _confidence,
            timestamp: block.timestamp,
            resolvedBy: msg.sender
        });
        
        disputeResolutions[_shipmentId] = resolution;
        
        e.status = EscrowStatus.RESOLVED;
        e.updatedAt = block.timestamp;
        e.lastActionHash = keccak256(abi.encodePacked("RESOLVED", _shipmentId, _carrierWins));
        
        // Rimuovi da active
        _removeActiveShipment(_shipmentId);
        
        if (_carrierWins) {
            // Paga carrier
            e.status = EscrowStatus.RELEASED;
            (bool success, ) = payable(e.carrier).call{value: e.amount}("");
            require(success, "Transfer to carrier failed");
            
            emit FundsReleased(_shipmentId, e.carrier, e.amount, _evidenceHash);
        } else {
            // Rimborsa shipper
            e.status = EscrowStatus.REFUNDED;
            require(_refundAmount <= e.amount, "Refund exceeds amount");
            
            (bool success, ) = payable(e.shipper).call{value: _refundAmount}("");
            require(success, "Refund failed");
            
            // Se rimane qualcosa, paga carrier
            uint256 remaining = e.amount - _refundAmount;
            if (remaining > 0) {
                (bool carrierSuccess, ) = payable(e.carrier).call{value: remaining}("");
                require(carrierSuccess, "Carrier payment failed");
            }
            
            emit FundsRefunded(_shipmentId, e.shipper, _refundAmount, "Dispute resolved");
        }
        
        emit DisputeResolved(_shipmentId, _carrierWins, _refundAmount, _evidenceHash, _confidence);
        return true;
    }
    
    /**
     * @dev Refund emergency (solo admin)
     * @param _shipmentId ID shipment
     * @param _reason Motivo refund
     */
    function emergencyRefund(
        string memory _shipmentId,
        string memory _reason
    ) external onlyRole(ADMIN_ROLE) nonReentrant escrowExists(_shipmentId) returns (bool) {
        Escrow storage e = escrows[_shipmentId];
        
        require(e.status == EscrowStatus.LOCKED || e.status == EscrowStatus.TRANSFERRED, "Invalid status");
        
        e.status = EscrowStatus.REFUNDED;
        e.updatedAt = block.timestamp;
        
        _removeActiveShipment(_shipmentId);
        
        (bool success, ) = payable(e.shipper).call{value: e.amount}("");
        require(success, "Refund failed");
        
        emit FundsRefunded(_shipmentId, e.shipper, e.amount, _reason);
        return true;
    }
    
    // ==================== Admin Functions ====================
    
    /**
     * @dev Pausa contratto (emergenza)
     */
    function pause() external onlyRole(ADMIN_ROLE) {
        _pause();
        emit EmergencyPause(msg.sender, "Manual pause triggered");
    }
    
    /**
     * @dev Riprende operazioni
     */
    function unpause() external onlyRole(ADMIN_ROLE) {
        _unpause();
    }
    
    /**
     * @dev Registra Paolo Agent
     */
    function registerPaoloAgent(address _agent) external onlyRole(ADMIN_ROLE) {
        _grantRole(PAOLO_AGENT_ROLE, _agent);
    }
    
    /**
     * @dev Registra Giulia Agent
     */
    function registerGiuliaAgent(address _agent) external onlyRole(ADMIN_ROLE) {
        _grantRole(GIULIA_AGENT_ROLE, _agent);
    }
    
    /**
     * @dev Revoca agent
     */
    function revokeAgent(bytes32 _role, address _agent) external onlyRole(ADMIN_ROLE) {
        revokeRole(_role, _agent);
    }
    
    // ==================== View Functions ====================
    
    /**
     * @dev Get escrow details
     */
    function getEscrow(string memory _shipmentId) external view returns (Escrow memory) {
        return escrows[_shipmentId];
    }
    
    /**
     * @dev Get failover history
     */
    function getFailoverHistory(string memory _shipmentId) external view returns (FailoverRecord[] memory) {
        return failoverHistory[_shipmentId];
    }
    
    /**
     * @dev Get dispute resolution
     */
    function getDisputeResolution(string memory _shipmentId) external view returns (DisputeResolution memory) {
        return disputeResolutions[_shipmentId];
    }
    
    /**
     * @dev Get active shipments count
     */
    function getActiveShipmentCount() external view returns (uint256) {
        return activeShipments.length;
    }
    
    /**
     * @dev Verifica se shipment ha subito failover
     */
    function hasFailoverOccurred(string memory _shipmentId) external view returns (bool) {
        return failoverHistory[_shipmentId].length > 0;
    }
    
    /**
     * @dev Get statistiche sistema
     */
    function getStats() external view returns (
        uint256 escrows,
        uint256 failovers,
        uint256 disputes,
        uint256 volume
    ) {
        return (totalEscrows, totalFailovers, totalDisputes, totalVolume);
    }
    
    /**
     * @dev Check se failover richiede approvazione umana
     */
    function requiresHumanApproval(string memory _shipmentId) external view returns (bool) {
        return escrows[_shipmentId].amount > AUTO_FAILOVER_LIMIT;
    }
    
    // ==================== Internal Functions ====================
    
    function _removeActiveShipment(string memory _shipmentId) internal {
        for (uint256 i = 0; i < activeShipments.length; i++) {
            if (keccak256(bytes(activeShipments[i])) == keccak256(bytes(_shipmentId))) {
                activeShipments[i] = activeShipments[activeShipments.length - 1];
                activeShipments.pop();
                break;
            }
        }
    }
    
    // ==================== Fallback ====================
    
    receive() external payable {
        revert("Use lockFunds() to deposit");
    }
    
    fallback() external payable {
        revert("Invalid call");
    }
}