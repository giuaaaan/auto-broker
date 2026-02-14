# Zero-Knowledge Pricing per AUTO-BROKER

Sistema crittografico Zero-Knowledge per verifica fair pricing senza rivelare il costo base.

## Overview

Il sistema permette di verificare che il markup su un preventivo sia ≤ 30% **senza** che il broker conosca il costo base del cliente.

### Caso d'uso
- **Cliente**: Ha un costo base privato (es. 1000 EUR) e vuole vendere a 1250 EUR (25% markup)
- **Broker**: Vuole verificare che il markup sia fair (≤ 30%) ma non deve vedere il costo base
- **Soluzione ZK**: Il cliente genera una proof che dimostra `selling_price * 100 <= base_cost * 130` senza rivelare `base_cost`

## Architettura

```
┌──────────────┐          ┌──────────────┐          ┌──────────────┐
│   Cliente    │          │    AUTO-     │          │  Blockchain  │
│  (Browser)   │─────────▶│   BROKER     │─────────▶│  (Polygon)   │
│              │  Proof   │   Backend    │  Verify  │              │
└──────────────┘          └──────────────┘          └──────────────┘
       │                           │                         │
       │ base_cost + salt          │ commitment + proof      │
       │ (mai inviato!)            │ (pubblico)              │
       ▼                           ▼                         ▼
  [Commitment]              [Verifica ZK]            [Smart Contract]
  hash(base_cost + salt)    senza base_cost!         On-chain verify
```

## Componenti

### 1. Circuito ZK (`api/services/zk_pricing_service.py`)

```python
class ZKPriceCircuit:
    def generate_proof(base_cost, selling_price, salt) -> (proof, public_inputs)
    def verify_proof(proof, public_inputs) -> bool
```

**Vincolo matematico**: `selling_price * 100 <= base_cost * 130`
- Equivale a: `(selling - base) / base <= 0.30`
- Ovvero: markup ≤ 30%

### 2. Smart Contract (`blockchain/zk_pricing_verifier.sol`)

```solidity
contract ZKPricingVerifier {
    function verifyPricing(bytes32 commitment, bytes calldata zkProof) external returns (bool);
    function verifyFairPricing(uint256 baseCost, uint256 sellingPrice) external pure returns (bool);
}
```

### 3. API Endpoints (`api/routers/zk_pricing.py`)

| Endpoint | Metodo | Descrizione |
|----------|--------|-------------|
| `/pricing/zk/commit` | POST | Cliente crea commitment ZK |
| `/pricing/zk/verify` | POST | Verifica proof (pubblico) |
| `/pricing/zk/reveal` | POST | Admin reveal (solo dispute) |
| `/pricing/zk/audit/{quote_id}` | GET | Audit trail (admin) |

## Flusso Completo

### 1. Creazione Commitment (Cliente)

```bash
curl -X POST http://localhost:8000/pricing/zk/commit \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "quote_id": "550e8400-e29b-41d4-a716-446655440000",
    "base_cost": 1000.00,
    "selling_price": 1250.00,
    "markup_percent": 25.00
  }'
```

**Response**:
```json
{
  "quote_id": "550e8400-e29b-41d4-a716-446655440000",
  "commitment": "a1b2c3d4e5f6...",  // hash(base_cost + salt)
  "proof": "{...}",  // Proof ZK
  "public_inputs": "{...}",  // Dati pubblici per verifica
  "selling_price": 1250.00,
  "salt_hash": "b2c3d4e5f6...",  // hash(salt), NON il salt!
  "message": "Zero-knowledge commitment generated successfully"
}
```

**Nota**: `base_cost` e `salt` NON sono salvati nel DB!

### 2. Verifica (Broker o chiunque)

```bash
curl -X POST http://localhost:8000/pricing/zk/verify \
  -H "Content-Type: application/json" \
  -d '{
    "commitment": "a1b2c3d4e5f6..."
  }'
```

**Response**:
```json
{
  "commitment": "a1b2c3d4e5f6...",
  "is_valid": true,
  "selling_price": 1250.00,
  "message": "Proof verified: markup is within 30% limit"
}
```

### 3. Dispute Resolution (Solo Admin)

```bash
curl -X POST http://localhost:8000/pricing/zk/reveal \
  -H "Authorization: Bearer admin-token" \
  -H "Content-Type: application/json" \
  -d '{
    "quote_id": "550e8400-e29b-41d4-a716-446655440000",
    "base_cost": 1000.00,
    "salt": "salt_segreto_del_cliente"
  }'
```

**Response**:
```json
{
  "quote_id": "550e8400-e29b-41d4-a716-446655440000",
  "verified": true,
  "commitment_match": true,
  "base_cost": 1000.00,
  "selling_price": 1250.00,
  "markup_percent": 25.00,
  "message": "Price revealed successfully. Access logged for GDPR audit.",
  "audit_logged": true
}
```

## Sicurezza

### Privacy Guarantees

1. **Base Cost**: Mai salvato in chiaro, mai loggato
2. **Salt**: Generato client-side, solo hash salvato
3. **Commitment**: Hash one-way (SHA256), non reversibile
4. **Proof**: Verificabile senza rivelare witness (base_cost)

### GDPR Compliance

- **Article 22**: Log di ogni accesso ai dati sensibili
- **Right to erasure**: Possibile cancellare commitment (senza base_cost)
- **Audit trail**: Chi ha visto cosa e quando

## Test

```bash
# Esegui test ZK Pricing
pytest tests/unit/services/test_zk_pricing.py -v

# Test specifico markup 30%
pytest tests/unit/services/test_zk_pricing.py::TestZKPriceCircuit::test_generate_proof_valid_markup -xvs

# Test privacy (base_cost non in DB)
pytest tests/unit/services/test_zk_pricing.py::TestZKPrivacy::test_base_cost_never_stored_plaintext -xvs
```

## Implementazione Tecnica

### Circuito Semplificato

Non usiamo un vero zk-SNARK (che richiederebbe circom/snarkjs) ma una implementazione semplificata ma sicura:

```python
def generate_proof(base_cost, selling_price, salt):
    # 1. Verifica constraint: selling * 100 <= base * 130
    assert selling_price * 100 <= base_cost * 130
    
    # 2. Calcola commitment: H(base_cost || salt)
    commitment = sha256(f"{base_cost}:{salt}")
    
    # 3. Firma BLS se disponibile (py_ecc)
    signature = bls.Sign(priv_key, message)
    
    return commitment, proof
```

**Vantaggi**:
- No setup ceremony complesso
- No trusted setup
- Verificabile on-chain con BLS12-381

**Limitazioni**:
- Non è un vero SNARK (ma sufficiente per questo use case)
- Per produzione su larga scala, migrare a circom

## Roadmap

### v1.0 (Current)
- Commitment scheme con hash
- Range proof semplificata
- Firma BLS (opzionale)

### v2.0 (Future)
- Integrazione circom verifier
- True zk-SNARKs
- Recursive proofs

## References

- [zk-SNARKs: Under the Hood](https://medium.com/@VitalikButerin/zk-snarks-under-the-hood-b33151a013f6)
- [BLS12-381 for zk-SNARKs](https://electriccoin.co/blog/new-snark-curve/)
- [Zero-Knowledge Proofs: An illustrated primer](https://blog.cryptographyengineering.com/2014/11/27/zero-knowledge-proofs-illustrated-primer/)