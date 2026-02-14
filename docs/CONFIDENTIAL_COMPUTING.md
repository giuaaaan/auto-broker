# Confidential Computing Architecture

## Overview

Auto-Broker utilizza **Confidential Computing** per proteggere l'elaborazione delle chiamate vocali e i dati sensibili degli agenti AI. L'architettura garantisce che nemmeno l'host cloud provider possa accedere ai dati in chiaro.

## Tecnologie Supportate

### AMD SEV-SNP (Secure Encrypted Virtualization - Secure Nested Paging)
- **CPU**: AMD EPYC (3rd Gen+)
- **Feature**: Memory encryption with integrity protection
- **Ecosystem**: Kata Containers, cloud-hypervisor
- **Attestation**: AMD Key Distribution Service (KDS)

### Intel TDX (Trust Domain Extensions)
- **CPU**: Intel Xeon (4th Gen+ with TDX)
- **Feature**: TEE with encrypted memory regions
- **Ecosystem**: QEMU, TD-Shim
- **Attestation**: Intel Trust Authority

### Simulation Mode
Per development e testing senza hardware specializzato.

## Architettura

```
┌─────────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │               Confidential Namespace                   │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │              RuntimeClass: kata-cc               │  │  │
│  │  │  ┌─────────────────────────────────────────┐    │  │  │
│  │  │  │         AMD SEV-SNP / Intel TDX          │    │  │  │
│  │  │  │  ┌─────────────────────────────────┐    │    │  │  │
│  │  │  │  │     Confidential Container      │    │    │  │  │
│  │  │  │  │                                 │    │    │  │  │
│  │  │  │  │  ┌─────────────────────────┐   │    │    │  │  │
│  │  │  │  │  │    SARA/MARCO/FRANCO    │   │    │    │  │  │
│  │  │  │  │  │      Agent Service      │   │    │    │  │  │
│  │  │  │  │  └─────────────────────────┘   │    │    │  │  │
│  │  │  │  │                                 │    │    │  │  │
│  │  │  │  │  ┌─────────────────────────┐   │    │    │  │  │
│  │  │  │  │  │  Attestation Sidecar    │   │    │    │  │  │
│  │  │  │  │  │  (Report Generation)    │   │    │    │  │  │
│  │  │  │  │  └─────────────────────────┘   │    │    │  │  │
│  │  │  │  │                                 │    │    │  │  │
│  │  │  │  │  ┌─────────────────────────┐   │    │    │  │  │
│  │  │  │  │  │      Vault Agent        │   │    │    │  │  │
│  │  │  │  │  │  (Secret Injection)     │   │    │    │  │  │
│  │  │  │  │  └─────────────────────────┘   │    │    │  │  │
│  │  │  │  └─────────────────────────────────────────┘    │  │  │
│  │  │  │              Memory Encrypted                    │  │  │
│  │  │  └──────────────────────────────────────────────────┘  │  │
│  │  └───────────────────────────────────────────────────────┘  │
│  │                                                             │
│  │  Network Policy: Ingress only from API Gateway              │
│  │                  Egress only to Vault + Hume API            │
│  └─────────────────────────────────────────────────────────────┘
│                                                              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    HashiCorp Vault                          │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │           Enclave Attestation Policy                   │  │
│  │  - Whitelist of trusted measurements                   │  │
│  │  - Remote attestation verification                     │  │
│  │  - Wrapped secrets (enclave-bound)                     │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  Secrets:                                                   │
│  - enclave-agents/data/hume/api-key                        │
│  - enclave-agents/data/retell/api-key                      │
│  - enclave-agents/data/database/connection                 │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Flusso di Attestation

```
1. Enclave Boot
   │
   ▼
2. Generate Attestation Report (SEV-SNP/TDX)
   │
   ▼
3. Send Report to Vault
   │
   ▼
4. Vault Verifies:
   ├─ AMD/Intel Signature ✓
   ├─ Measurement in Whitelist ✓
   ├─ Platform Security Version ✓
   └─ Not Revoked ✓
   │
   ▼
5. Vault Returns Wrapped Secrets
   │
   ▼
6. Enclave Unwraps with Private Key
   │
   ▼
7. Ready for Secure Processing
```

## Implementazione

### Componenti Principali

#### 1. EnclaveAttestation Service

```python
# api/services/enclave_attestation.py

from api.services.enclave_attestation import EnclaveAttestation

# Inizializza
attestation = EnclaveAttestation(mode="sev-snp")

# Genera report
report = attestation.get_attestation_report()

# Verifica
result = await attestation.verify_attestation(report, expected_measurements)

# Ottieni secrets
secrets = await attestation.provision_secrets(report, ["hume/api-key"])
```

#### 2. ConfidentialRetellService

```python
# api/services/confidential_retell.py

from api.services.confidential_retell import ConfidentialRetellService

# Inizializza servizio in enclave
service = ConfidentialRetellService()

# Inizializza enclave (attestation + secret provisioning)
await service.initialize_enclave()

# Processa chiamata in enclave sicuro
result = await service.process_call_secure(
    audio_data=audio_bytes,
    call_metadata={"shipment_id": "SHIP-123", "agent_type": "sara"}
)

# Risultato con PII mascherata per logging
print(result.to_safe_dict())
```

#### 3. Vault Integration

```python
# api/services/vault_integration.py

from api.services.vault_integration import VaultClient

vault = VaultClient()

# Ottieni secrets con attestation binding
secrets = await vault.get_secrets_with_attestation(
    paths=["hume/api-key", "retell/api-key"],
    attestation_report=report
)
```

### Kubernetes Deployment

```yaml
# infrastructure/confidential-enclave.yaml

apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: kata-cc-amd-sev
handler: kata-cc
scheduling:
  nodeSelector:
    confidential-computing: "amd-sev-snp"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: sara-agent-enclave
spec:
  template:
    spec:
      runtimeClassName: kata-cc-amd-sev  # Enclave runtime
      nodeSelector:
        confidential-computing: "amd-sev-snp"
      containers:
      - name: sara-agent
        image: auto-broker/enclave-agent:v2.1.0
        resources:
          limits:
            memory: "2Gi"
            cpu: "1000m"
            amd.com/sev-snp: "1"  # Request SEV-SNP
        volumeMounts:
        - name: secrets-store-inline
          mountPath: "/mnt/secrets-store"
          readOnly: true
        # TMP in RAM (encrypted by SEV)
        - name: tmp
          mountPath: /tmp
      volumes:
      - name: tmp
        emptyDir:
          medium: Memory  # No disk
```

## Sicurezza

### Garanzie di Confidentiality

| Feature | Protection |
|---------|------------|
| Memory Encryption | Data unreadable by host |
| No Disk Logging | stdout only, encrypted |
| Sealed Secrets | Bound to enclave measurement |
| Remote Attestation | Verifiable identity |
| Minimal Attack Surface | Distroless images |
| Network Isolation | Strict ingress/egress policies |

### PII Handling

```python
# Metadati sanitizzati - mai PII in chiaro
safe_metadata = {
    "phone_hash": "sha256:abc123...",  # Hashed
    "shipment_id": "SHIP-123",          # Reference only
    "agent_type": "sara"
}

# Trascrizione mascherata in logs
result.to_safe_dict()["transcription_preview"]
# "Questa è una tr... [MASKED - ENCLAVE ONLY]"
```

## Setup

### Requisiti Hardware

**AMD SEV-SNP:**
- CPU: AMD EPYC 7003 Series or newer
- BIOS: SEV-SNP enabled
- Kernel: Linux 5.19+ with SEV-SNP support

**Intel TDX:**
- CPU: Intel Xeon Scalable 4th Gen+
- BIOS: TDX enabled
- Kernel: Linux 6.2+ with TDX support

### Requisiti Software

```bash
# Kata Containers con confidential support
kubectl apply -f https://raw.githubusercontent.com/kata-containers/kata-containers/main/tools/packaging/kata-deploy/kata-deploy.yaml

# Label nodi
kubectl label node <node-name> confidential-computing=amd-sev-snp

# Install Vault CSI Provider
helm repo add hashicorp https://helm.releases.hashicorp.com
helm install vault-csi hashicorp/vault \
  --set "csi.enabled=true"
```

### Configurazione Vault

```bash
# Abilita enclave attestation
vault auth enable -path=enclave-attest jwt

# Crea policy per enclave
vault policy write enclave-agent - <<EOF
path "enclave-agents/data/+" {
    capabilities = ["read"]
}
EOF

# Configura trusted measurements
vault write auth/enclave-attest/config \
    oidc_discovery_url="https://amd-kds.com" \
    default_role="enclave-agent"
```

## Testing

### Simulation Mode (Local)

```bash
# Test senza hardware SEV/TDX
export ENCLAVE_MODE=simulation
export ATTESTATION_ENABLED=false

pytest tests/test_enclave_attestation.py -v
pytest tests/test_confidential_retell.py -v
```

### Integration Tests

```bash
# Con Vault mock
pytest tests/test_enclave_attestation.py::TestAttestationIntegration -v
```

## Monitoring

### Metriche Enclave

```python
# Health endpoint
@app.get("/health/enclave")
async def enclave_health():
    return await ConfidentialHealthEndpoint(service).health_check()

# Risultato
{
    "status": "healthy",
    "enclave": {
        "enclave_ready": true,
        "enclave_mode": "sev-snp",
        "memory_encryption_active": true,
        "secrets_provisioned": true
    },
    "attestation": {
        "valid": true,
        "trusted": true,
        "expires_at": "2024-01-15T10:00:00Z"
    }
}
```

### Alerting

```yaml
# Alert su attestation failure
- alert: EnclaveAttestationFailed
  expr: enclave_attestation_valid == 0
  for: 5m
  labels:
    severity: critical
  annotations:
    summary: "Enclave attestation failed"
```

## Cloud Alternatives

### AWS Nitro Enclaves

Se hardware SEV-SNP/TDX non disponibile:

```python
# api/services/nitro_enclave.py

from api.services.nitro_enclave import NitroEnclaveService

service = NitroEnclaveService()
result = await service.process_call_secure(audio_data)
```

### Azure Confidential Computing

```yaml
# Azure Kubernetes con DCsv3 (Intel TDX)
apiVersion: machinelearning.seldon.io/v1
kind: SeldonDeployment
metadata:
  name: confidential-agent
spec:
  predictors:
  - graph:
      implementation: SKLEARN_SERVER
      modelUri: gs://models/agent
      name: classifier
    componentSpecs:
    - spec:
        runtimeClassName: kata-cc-intel-tdx
```

## Troubleshooting

### Verifica SEV-SNP

```bash
# Check SEV-SNP status
cat /sys/devices/system/cpu/amd_sev/status
# Output: active

# Check attestation device
ls -la /dev/sev
cat /dev/sev-guest
```

### Verifica Intel TDX

```bash
# Check TDX status
rdmsr -a 0x982  # TDX capability
# Output should indicate TDX supported

# Check module
dmesg | grep -i tdx
```

### Log Enclave

```bash
# Log solo stdout (no file)
kubectl logs -n confidential-agents sara-agent-enclave-xxx

# Verifica attestation
kubectl exec -n confidential-agents sara-agent-enclave-xxx \
  -- cat /run/attestation/status
```

## Compliance

### GDPR
- PII processing isolato in enclave
- Encryption in-transit e at-rest
- Audit trail completo

### ISO 27001
- Access control basato su attestation
- Key management con HSM integration
- Regular security assessments

## Roadmap

- **Q2 2026**: Production deployment con AMD SEV-SNP
- **Q3 2026**: Intel TDX support
- **Q4 2026**: GPU confidential computing (NVIDIA H100)

## Riferimenti

- [AMD SEV-SNP](https://www.amd.com/en/developer/sev.html)
- [Intel TDX](https://www.intel.com/content/www/us/en/developer/tools/trust-domain-extensions/overview.html)
- [Kata Containers Confidential](https://github.com/kata-containers/kata-containers/tree/main/docs/how-to/confidential-containers.md)
- [HashiCorp Vault](https://www.vaultproject.io/docs/platform/k8s)