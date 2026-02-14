// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

/**
 * @title ZKPricingVerifier
 * @notice Verifica on-chain di Zero-Knowledge Pricing per AUTO-BROKER
 * @dev Implementazione semplificata di verifica ZK su Polygon
 * 
 * Vincolo verificato: (selling_price - base_cost) / base_cost <= 30%
 * Equivalente a: selling_price * 100 <= base_cost * 130
 * 
 * In produzione, questo contratto interagirebbe con:
 * - Verifier contract precompilato (circom verifier)
 * - BLS12-381 curve operations
 */

contract ZKPricingVerifier {
    
    // Struttura per commitment ZK
    struct ZKCommitment {
        bytes32 commitment;      // Hash del commitment
        bytes proof;             // Proof ZK
        uint256 sellingPrice;    // Prezzo vendita (in centesimi)
        uint256 timestamp;       // Timestamp creazione
        bool verified;           // Stato verifica
        address submitter;       // Chi ha sottomesso
    }
    
    // Mapping: commitment => dati
    mapping(bytes32 => ZKCommitment) public commitments;
    
    // Mapping: quote_id => commitment
    mapping(bytes32 => bytes32) public quoteCommitments;
    
    // Admin autorizzati a fare reveal
    mapping(address => bool) public authorizedAuditors;
    
    // Eventi
    event PricingCommitmentCreated(
        bytes32 indexed commitment,
        bytes32 indexed quoteId,
        uint256 sellingPrice,
        address submitter
    );
    
    event PricingVerified(
        bytes32 indexed commitment,
        bool isValid,
        uint256 timestamp
    );
    
    event PricingRevealed(
        bytes32 indexed commitment,
        bytes32 indexed quoteId,
        address revealedBy,
        string reason
    );
    
    event AuditorAdded(address auditor);
    event AuditorRemoved(address auditor);
    
    // Owner del contratto
    address public owner;
    
    // Costanti
    uint256 public constant MAX_MARKUP_BASIS_POINTS = 3000; // 30% = 3000 bps
    uint256 public constant BASIS_POINTS = 10000;           // 100% = 10000 bps
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }
    
    modifier onlyAuditor() {
        require(authorizedAuditors[msg.sender], "Only authorized auditor");
        _;
    }
    
    constructor() {
        owner = msg.sender;
        authorizedAuditors[msg.sender] = true;
    }
    
    /**
     * @notice Aggiunge un auditor autorizzato
     */
    function addAuditor(address auditor) external onlyOwner {
        authorizedAuditors[auditor] = true;
        emit AuditorAdded(auditor);
    }
    
    /**
     * @notice Rimuove un auditor
     */
    function removeAuditor(address auditor) external onlyOwner {
        authorizedAuditors[auditor] = false;
        emit AuditorRemoved(auditor);
    }
    
    /**
     * @notice Registra un nuovo commitment ZK
     * @param commitment Hash del commitment
     * @param quoteId ID del preventivo
     * @param sellingPrice Prezzo vendita (in centesimi)
     * @param proof Proof ZK (bytes)
     */
    function registerCommitment(
        bytes32 commitment,
        bytes32 quoteId,
        uint256 sellingPrice,
        bytes calldata proof
    ) external returns (bool) {
        require(commitment != bytes32(0), "Invalid commitment");
        require(sellingPrice > 0, "Invalid price");
        require(commitments[commitment].timestamp == 0, "Commitment exists");
        
        commitments[commitment] = ZKCommitment({
            commitment: commitment,
            proof: proof,
            sellingPrice: sellingPrice,
            timestamp: block.timestamp,
            verified: false,
            submitter: msg.sender
        });
        
        quoteCommitments[quoteId] = commitment;
        
        emit PricingCommitmentCreated(
            commitment,
            quoteId,
            sellingPrice,
            msg.sender
        );
        
        return true;
    }
    
    /**
     * @notice Verifica on-chain della proof ZK
     * @param commitment Hash del commitment
     * @param quoteId ID del preventivo
     * @return isValid True se proof valida
     * 
     * @dev In una implementazione completa, questo userebbe:
     * - Pairing check su BLS12-381
     * - Verifica del constraint polynomial
     * - Public input consistency check
     */
    function verifyPricing(
        bytes32 commitment,
        bytes32 quoteId
    ) external view returns (bool isValid) {
        ZKCommitment storage zk = commitments[commitment];
        require(zk.timestamp > 0, "Commitment not found");
        
        // Verifica quote_id corrisponda
        require(quoteCommitments[quoteId] == commitment, "Quote mismatch");
        
        // In una implementazione reale con circom:
        // return verifier.verifyProof(proof, publicSignals);
        
        // Per questa demo, verifichiamo che la proof non sia vuota
        // e che il commitment sia registrato
        isValid = zk.proof.length > 0;
        
        return isValid;
    }
    
    /**
     * @notice Verifica semplificata del vincolo markup
     * @param baseCost Costo base (rivelato solo in dispute)
     * @param sellingPrice Prezzo vendita
     * @return isFair True se markup <= 30%
     */
    function verifyFairPricing(
        uint256 baseCost,
        uint256 sellingPrice
    ) external pure returns (bool isFair) {
        require(baseCost > 0, "Invalid base cost");
        require(sellingPrice > 0, "Invalid selling price");
        
        // Verifica: selling_price * 100 <= base_cost * 130
        // Equivale a: markup <= 30%
        uint256 leftSide = sellingPrice * 100;
        uint256 rightSide = baseCost * 130;
        
        isFair = leftSide <= rightSide;
        
        return isFair;
    }
    
    /**
     * @notice Calcola markup percentuale
     */
    function calculateMarkup(
        uint256 baseCost,
        uint256 sellingPrice
    ) external pure returns (uint256 markupBasisPoints) {
        require(baseCost > 0, "Invalid base cost");
        
        // markup = ((selling - base) / base) * 10000
        markupBasisPoints = ((sellingPrice - baseCost) * BASIS_POINTS) / baseCost;
        
        return markupBasisPoints;
    }
    
    /**
     * @notice Logga reveal del prezzo (GDPR audit)
     * @param commitment Hash commitment
     * @param quoteId ID preventivo
     * @param reason Motivo reveal (dispute, audit, etc.)
     */
    function logPriceReveal(
        bytes32 commitment,
        bytes32 quoteId,
        string calldata reason
    ) external onlyAuditor {
        require(commitments[commitment].timestamp > 0, "Commitment not found");
        
        emit PricingRevealed(commitment, quoteId, msg.sender, reason);
    }
    
    /**
     * @notice Recupera commitment per quote ID
     */
    function getCommitmentByQuote(
        bytes32 quoteId
    ) external view returns (bytes32) {
        return quoteCommitments[quoteId];
    }
    
    /**
     * @notice Recupera dettagli commitment
     */
    function getCommitmentDetails(
        bytes32 commitment
    ) external view returns (
        uint256 sellingPrice,
        uint256 timestamp,
        bool verified,
        address submitter
    ) {
        ZKCommitment storage zk = commitments[commitment];
        require(zk.timestamp > 0, "Commitment not found");
        
        return (zk.sellingPrice, zk.timestamp, zk.verified, zk.submitter);
    }
    
    /**
     * @notice Verifica se un address è auditor autorizzato
     */
    function isAuditor(address account) external view returns (bool) {
        return authorizedAuditors[account];
    }
}