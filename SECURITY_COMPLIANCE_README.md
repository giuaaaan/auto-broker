# AUTO-BROKER Enterprise Security & Compliance
## Zero Trust Architecture | GDPR/AI Act/eFTI Compliance

---

## 📋 Executive Summary

Implementazione completa di security enterprise-grade per AUTO-BROKER:

- **Zero Trust**: mTLS tra tutti i servizi, nessuna comunicazione plaintext
- **Identity**: OAuth2/OIDC con Keycloak, SAML 2.0 SSO, MFA enforcement
- **Compliance**: GDPR Article 22 (spiegabilità AI), eFTI CMR digitale
- **HITL**: Human-in-the-Loop dashboard con emergency overrides

---

## 🏗️ Architecture Components

### Security Layer

| Component | File | Purpose |
|-----------|------|---------|
| Identity Provider | `security/identity_provider.py` | OAuth2/OIDC, JWT, MFA |
| RBAC Matrix | `security/rbac_matrix.py` | Role-based access control |
| PII Masking | `security/pii_masking.py` | GDPR data protection |
| Vault Integration | `security/vault_integration.py` | Dynamic secrets |

### Compliance Layer

| Component | File | Purpose |
|-----------|------|---------|
| Audit Logger | `compliance/audit_logger.py` | Immutable AI decision log |
| GDPR Manager | `compliance/gdpr_manager.py` | Art. 15-22 compliance |
| eFTI CMR | `compliance/efti_cm_generator.py` | Digital CMR (UE 2020/1056) |

### HITL Dashboard

| Component | File | Purpose |
|-----------|------|---------|
| Backend API | `dashboard/hitl_backend/routes.py` | Emergency overrides |
| Emergency UI | `dashboard/hitl_frontend/EmergencyOverride.tsx` | Kill switch, agent status |
| Queue UI | `dashboard/hitl_frontend/EscalationQueue.tsx` | Escalation management |

### Service Mesh

| Component | File | Purpose |
|-----------|------|---------|
| mTLS Config | `istio-manifests/peer-authentication.yaml` | Strict mTLS |
| Network Policies | `istio-manifests/network-policies.yaml` | Pod isolation |

---

## 🔐 Security Features

### 1. Zero Trust Network

```yaml
# mTLS enforced on all services
api ↔ postgres: STRICT mTLS
api ↔ redis: STRICT mTLS  
n8n ↔ api: STRICT mTLS
api ↔ chroma: STRICT mTLS
```

### 2. Identity & Access

**JWT Claims:**
```json
{
  "sub": "user-123",
  "email": "user@company.com",
  "organization_id": "org-456",
  "role": "supervisor",
  "mfa_verified": true,
  "iat": 1707912000,
  "exp": 1707912900,
  "jti": "uuid-unique",
  "scope": ["read:leads", "write:pricing"]
}
```

**RBAC Roles:**
- `broker`: CRUD own leads, read pricing, no system config
- `supervisor`: Org-wide read, AI override, escalation mgmt
- `admin`: Full access, secret rotation, chaos testing

### 3. Secrets Management

**Vault Integration:**
- PostgreSQL: Dynamic credentials with 1h TTL
- API Keys: Retrieved from `secret/auto-broker/`
- JWT Keys: Automatic rotation every 90 days

---

## 📜 Compliance Features

### GDPR Article 22 - Right to Explanation

```python
# Log every AI decision with explainability
decision_id = audit_logger.log_decision(
    decision_type=DecisionType.PRICING,
    model_name="pricing-v2",
    model_version="2.1.0",
    input_data={"weight": 1000, "distance": 500},
    output_data={"price": 1500, "currency": "EUR"},
    feature_importance=[
        FeatureImportance("fuel_cost", 0.45, "positive", "Fuel price impact"),
        FeatureImportance("distance", 0.35, "positive", "Km driven")
    ],
    decision_logic="Price calculated based on fuel cost * distance + margin"
)
```

### GDPR Endpoints

| Endpoint | Article | Purpose |
|----------|---------|---------|
| `/compliance/right-to-explanation/{id}` | Art. 22 | Get decision explanation |
| `/compliance/data-portability/{user_id}` | Art. 20 | Export user data |
| `DELETE /compliance/right-to-erasure/{id}` | Art. 17 | Delete user data |

### eFTI Digital CMR

**Conformity:** Regolamento UE 2020/1056

```python
cmr = efti_generator.generate_cmr_xml(
    cmr_number="CMR-2026-001",
    carrier=CMRCarrier(...),
    shipper=CMRShipper(...),
    consignee=CMRConsignee(...),
    goods=CMRGoods(...)
)

# eIDAS qualified signature
signed_cmr = efti_generator.sign_cmr_qualified(
    cmr_xml=cmr,
    signer_name="Mario Rossi",
    signer_certificate_id="ARUBA-123"
)

# WORM archive (5 years)
archive_metadata = efti_generator.archive_cmr_worm(
    cmr_number="CMR-2026-001",
    cmr_xml=signed_cmr,
    shipment_id="SHIP-123"
)
```

---

## 🎛️ HITL Dashboard

### Emergency Override

**Kill Switch**: Blocca immediatamente tutti gli agenti AI

```typescript
// EmergencyOverride.tsx
const handleKillSwitch = async () => {
  await fetch('/hitl/agents/SARA/halt', {
    method: 'POST',
    body: JSON.stringify({
      reason: 'EMERGENCY - System halt required',
      mfa_code: mfaCode
    })
  });
};
```

**Override Form:**
- Target: pricing/shipment/agent/carrier
- Reason: min 20 characters (audit requirement)
- MFA: 6-digit code required
- Immediate execution option

### Escalation Queue

**Priority Levels:**
- CRITICAL (10): System down, legal threat
- HIGH (7): Angry customer, pricing dispute
- MEDIUM (5): Standard escalation
- LOW (3): Minor concerns

**Real-time Updates:**
```typescript
// WebSocket connection
const ws = new WebSocket('wss://api.auto-broker/hitl/ws?token=JWT');
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  if (msg.type === 'new_escalation') {
    // Play notification, update queue
  }
};
```

---

## 🚀 Deployment

### Prerequisites

```bash
# Keycloak (Identity Provider)
docker run -p 8080:8080 \
  -e KEYCLOAK_ADMIN=admin \
  -e KEYCLOAK_ADMIN_PASSWORD=admin \
  quay.io/keycloak/keycloak:24.0 start-dev

# HashiCorp Vault (Secrets)
docker run -p 8200:8200 \
  -e VAULT_DEV_ROOT_TOKEN_ID=dev-token \
  hashicorp/vault:latest

# Istio (Service Mesh)
istioctl install --set profile=default
```

### Apply Network Policies

```bash
kubectl apply -f istio-manifests/
```

### Database Migration

```sql
-- AI Decisions Audit Table (Immutable)
CREATE TABLE ai_decisions (
    decision_id UUID PRIMARY KEY,
    decision_type VARCHAR(50) NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    input_hash VARCHAR(64) NOT NULL,
    output_hash VARCHAR(64) NOT NULL,
    feature_importance JSONB NOT NULL,
    decision_logic TEXT NOT NULL,
    human_override BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL,
    retention_until TIMESTAMP NOT NULL
);

-- Prevent updates/deletes
CREATE OR REPLACE FUNCTION prevent_audit_modification()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'AI_DECISIONS table is immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_immutable
    BEFORE UPDATE OR DELETE ON ai_decisions
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_modification();
```

---

## 🧪 Testing

### Security Tests

```bash
# JWT token validation
pytest tests/unit/test_security_identity.py::TestJWT -v

# RBAC authorization
pytest tests/unit/test_security_identity.py::TestRBAC -v

# PII masking
pytest tests/unit/test_security_identity.py::TestPII -v
```

### Compliance Tests

```bash
# GDPR right to explanation
pytest tests/unit/test_compliance.py::TestExplanation -v

# eFTI CMR validation
pytest tests/unit/test_compliance.py::TestCMR -v

# Audit log immutability
pytest tests/unit/test_compliance.py::TestAuditLog -v
```

### Penetration Testing

```bash
# JWT forgery attempt (should fail)
jwt_tool.py -t eyJ0eXAiOiJKV1Qi... -pk public.pem

# Wireshark capture (should show only TLS 1.3)
tshark -i eth0 -Y "ssl.record.version == 0x0304"

# PII grep in logs (should be masked)
grep -r "@.*\.com" /var/log/auto-broker/  # Should find 0 matches
```

---

## 📊 Acceptance Criteria

### Security
- [x] JWT tokens cannot be forged (RS256 signature)
- [x] 100% internal traffic uses mTLS
- [x] Zero PII in logs (masked)
- [x] Vault secrets rotation without downtime

### Compliance
- [x] GDPR deletion < 24h (verified by query)
- [x] CMR XML validates with EU tool
- [x] SHAP values for every pricing decision
- [x] HITL dashboard latency < 500ms (p95)

### Access Control
- [x] Broker cannot access other org data
- [x] Supervisor can override AI decisions
- [x] Admin can rotate secrets
- [x] MFA required for privileged operations

---

## 📞 Support

- **Security Issues**: security@auto-broker.com
- **Compliance Questions**: compliance@auto-broker.com
- **Incident Response**: P0 incidents → +39-XXX-XXXX (24/7)

---

**Version**: 1.0.0  
**Last Updated**: 2026-02-14  
**Classification**: Confidential - Internal Use Only
