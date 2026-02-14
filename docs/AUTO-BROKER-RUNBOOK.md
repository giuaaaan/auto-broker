# Auto-Broker Operations Runbook

**Versione:** 1.4.0  
**Data:** 2026-02-15  
**Stato:** Aggiornato con Confidential Computing, Self-Healing Agents, ZK Pricing

---

## Indice

1. [On-Call Procedures](#on-call-procedures)
2. [Incident Response](#incident-response)
3. [Runbook Entries](#runbook-entries)
4. [Blast Radius Matrix](#blast-radius-matrix)
5. [Escalation Matrix](#escalation-matrix)
6. [Recovery Procedures](#recovery-procedures)

---

## On-Call Procedures

### Checklist Giornaliera (09:00)
- [ ] Verifica dashboard monitoring (Grafana/Kibana)
- [ ] Controlla alert non acknolwedged
- [ ] Review error logs ultime 24h
- [ ] Verifica health check endpoint: `GET /health`
- [ ] Controlla circuit breaker status
- [ ] Verifica quota Hume AI rimanente
- [ ] **Verifica Semantic Cache hit rate**: `GET /cache/stats`
- [ ] **Verifica Cost Dashboard**: `GET /costs/metrics`
- [ ] **Controlla FRANCO retention queue**: `GET /franco/stats`
- [ ] **Verifica Enclave Health**: `GET /health/enclave`
- [ ] **Controlla Self-Healing Status**: `GET /self-healing/status`
- [ ] **Verifica PAOLO Agent**: Circuit breaker e failover attivi
- [ ] **Verifica GIULIA Agent**: Queue dispute pending

### Comandi Rapidi
```bash
# Health check completo
curl -s http://localhost:8000/health | jq .

# Circuit breaker status
curl -s http://localhost:8000/metrics/circuit_breakers

# Redis connection check
redis-cli ping

# Database connection check
psql -c "SELECT count(*) FROM shipments;"

# Vault status
vault status
```

---

## Incident Response

### Severity Levels

| Level | Definizione | Response Time | Resolution Target |
|-------|-------------|---------------|-------------------|
| SEV1 | Servizio down, nessun quote possibile | 5 min | 1 ora |
| SEV2 | Feature critica degradata (ERP sync) | 15 min | 4 ore |
| SEV3 | Feature non-critica down (carbon) | 1 ora | 24 ore |
| SEV4 | Minor issue, workaround disponibile | 4 ore | 1 settimana |

### War Room Procedure (SEV1/SEV2)
1. **T+0:** Alert ricevuto, ack entro 5 min
2. **T+5:** Assessment iniziale, channel #incidents-war-room
3. **T+15:** Comunicazione stakeholder (SEV1)
4. **T+30:** Root cause identificato o escalation
5. **T+60:** Fix in progress o mitigation attiva
6. **Post-incident:** RCA entro 24h

---

## Runbook Entries

### RB-001: Database PostgreSQL Down

**Sintomi:**
- Health check FAILED: `db: disconnected`
- Errori 500 su tutte le API che usano DB

**Blast Radius:**
- ✅ New leads blocked
- ✅ Quote generation blocked
- ✅ ERP sync blocked
- ✅ Existing tracking works (cache Redis)
- ✅ POD blockchain non impattato

**Diagnostica:**
```bash
# Verifica container
docker ps | grep postgres

# Verifica logs
docker logs auto-broker-postgres-1 --tail 100

# Verifica connessione
pg_isready -h localhost -p 5432

# Verifica spazio disco
df -h /var/lib/postgresql
```

**Mitigazione:**
1. Se spazio pieno: espandere volume o pulire logs
2. Se corrupted: restore da backup ultimo snapshot
3. Se connection pool esaurito: restart applicazione

**Recovery:**
```bash
# Restart database
docker-compose restart postgres

# Verifica recovery
psql -c "SELECT pg_is_in_recovery();"
```

---

### RB-002: Redis Cache Down

**Sintomi:**
- Health check WARNING: `cache: slow`
- Performance degradata (cache miss 100%)
- Quota Hume AI consumata velocemente

**Blast Radius:**
- ⚠️ Performance -50%
- ⚠️ API rate limits hit più frequentemente
- ✅ No data loss
- ✅ ERP sync continua (senza cache)

**Recovery:**
```bash
# Restart Redis
docker-compose restart redis

# Warm cache manuale (se necessario)
python scripts/warm_cache.py
```

---

### RB-003: Hume AI API Failure

**Sintomi:**
- Circuit breaker OPEN per `hume_api`
- Sentiment analysis fallback a Ollama
- Alert: `Hume AI unavailable > 3 failures`

**Blast Radius:**
- ✅ Sentiment analysis continua (Ollama)
- ✅ No lead loss
- ⚠️ Accuratezza sentiment -15%
- ⚠️ Latenza +50ms

**Diagnostica:**
```bash
# Verifica quota
python -c "from api.services.eq_sentiment_service import SentimentService; \
           import asyncio; s = SentimentService(); \
           print(asyncio.run(s.check_hume_quota()))"

# Test manuale API
curl -X POST https://api.hume.ai/v0/batch/jobs \
  -H "X-Hume-Api-Key: $HUME_API_KEY" \
  -d '{"urls": ["https://example.com/audio.wav"]}'
```

**Recovery:**
1. Se quota esaurita: contattare Hume per upgrade
2. Se API error: attendere recovery automatico (30s)
3. Force reset circuit breaker (se necessario):
   ```bash
   redis-cli del circuit_breaker:hume_api
   ```

---

### RB-004: ERP SAP S/4HANA Unavailable

**Sintomi:**
- Circuit breaker OPEN per `sap_adapter`
- Errori sync quote → SAP
- Alert: `SAP connection failed`

**Blast Radius:**
- ⚠️ New quotes non synced to SAP
- ⚠️ Quotes use cached market data
- ✅ Pricing engine continua (formula based)
- ✅ Blockchain POD non impattato

**Diagnostica:**
```bash
# Verifica connectivity
ping sap-s4hana.company.com

# Verifica credenziali Vault
vault kv get secret/erp/sap

# Test connection manuale
python scripts/test_sap_connection.py
```

**Mitigazione:**
1. Quotes accumulate in `unapplied_changes` table
2. Pricing continua con formula (no market adjustment)
3. Notificare ops team cliente per SAP status

**Recovery:**
1. Attendere SAP restoration
2. Circuit breaker auto-recovery (HALF_OPEN → CLOSED)
3. Replay queued changes:
   ```bash
   python scripts/replay_erp_changes.py --system=sap
   ```

---

### RB-005: DAT iQ Market Data Unavailable

**Sintomi:**
- Circuit breaker OPEN per `dat_iq`
- Pricing senza market adjustment
- Alert: `DAT iQ rate limit exceeded`

**Blast Radius:**
- ⚠️ Pricing confidence interval +20%
- ⚠️ Market-based strategy unavailable
- ✅ Cost-plus pricing continua
- ✅ Cached rates usable per 24h

**Mitigazione:**
1. Switch automatico a pricing strategy "cost-plus"
2. Usa cached rates (Redis TTL 24h)
3. Notifica sales team per manual review

**Recovery:**
```bash
# Verifica subscription status
curl -H "Authorization: Bearer $DAT_IQ_TOKEN" \
     https://api.dat.com/rates/health

# Force cache refresh (quando disponibile)
redis-cli del dat_iq:rates:*
```

---

### RB-006: Polygon Blockchain Congestion

**Sintomi:**
- Transaction pending > 5 min
- Gas fees spikes
- Alert: `Blockchain tx confirmation timeout`

**Blast Radius:**
- ⚠️ POD verification delayed
- ⚠️ Smart contract interactions slow
- ✅ POD records queued localmente
- ✅ No data loss

**Mitigazione:**
1. Aumenta gas price (automatico con 20% buffer)
2. Queue transactions in `blockchain_queue` table
3. Batch multiple PODs se possibile

**Recovery:**
```bash
# Check pending transactions
python scripts/check_pending_tx.py

# Retry with higher gas (manuale)
python scripts/resubmit_tx.py --increase-gas 30
```

---

### RB-007: Vault Secret Store Down

**Sintomi:**
- Tutti i servizi non possono autenticarsi
- Health check FAILED su multiple services
- Alert: `Vault sealed or unreachable`

**Blast Radius:**
- 🔴 CRITICAL: Degradation totale dopo TTL (1h)
- 🔴 No new database connections
- 🔴 ERP auth fails
- 🔴 Blockchain key access blocked

**Diagnostica:**
```bash
# Verifica Vault status
vault status

# Se sealed, unseal richiesto
vault operator unseal <unseal-key-1>
vault operator unseal <unseal-key-2>
vault operator unseal <unseal-key-3>
```

**Recovery:**
1. **Sealed:** Unseal con 3/5 keys (procedura Shamir)
2. **Unreachable:** Verifica network, restart container
3. **Emergency:** Usa cached secrets (1h TTL) per restart graceful

**Emergency Procedure:**
```bash
# Riavvio controllato con secrets cached
docker-compose restart api worker
```

---

### RB-008: Istio Service Mesh Issues

**Sintomi:**
- mTLS handshake failures
- Services unreachable tra loro
- Alert: `Istio proxy error rate high`

**Blast Radius:**
- 🔴 Inter-service communication blocked
- 🔴 Circuit breakers non funzionano
- ⚠️ External APIs may still work

**Diagnostica:**
```bash
# Verifica istio-proxy logs
kubectl logs deployment/api -c istio-proxy --tail 100

# Verifica mTLS status
istioctl authn tls-check api.default.svc.cluster.local
```

**Recovery:**
1. Restart istio-proxy sidecar:
   ```bash
   kubectl rollout restart deployment/api
   ```
2. Se persistente: disabilitare temporaneamente mTLS (emergency):
   ```bash
   kubectl apply -f - <<EOF
   apiVersion: security.istio.io/v1beta1
   kind: PeerAuthentication
   metadata:
     name: default
     namespace: default
   spec:
     mtls:
       mode: PERMISSIVE
   EOF
   ```

---

### RB-009: Blockchain Smart Contract Failure

**Sintomi:**
- Transaction reverted
- Contract function calls fail
- Alert: `POD contract execution failed`

**Blast Radius:**
- ⚠️ POD verification blocked
- ⚠️ Dispute resolution unavailable
- ✅ POD records queued localmente
- ⚠️ Integrity risk dopo 24h senza blockchain

**Diagnostica:**
```bash
# Verifica contract status
python scripts/check_contract_health.py

# Verifica balance wallet
python scripts/check_wallet_balance.py
```

**Recovery:**
1. Verifica gas balance, top-up se necessario
2. Deploy contract fix se bug trovato
3. Replay failed transactions dopo fix

---

### RB-010: Carbon Calculator Service Down

**Sintomi:**
- Carbon calculation errors
- CSRD report generation fails
- Alert: `GLEC calculation failed`

**Blast Radius:**
- ⚠️ CSRD reporting incomplete
- ⚠️ Carbon offset quotes unavailable
- ✅ Core logistics operations continue
- ✅ Non-critical for operations

**Recovery:**
```bash
# Restart carbon service
docker-compose restart carbon-calculator

# Manual recalculation dopo recovery
python scripts/recalculate_carbon.py --date-from=2026-02-01
```

---

### RB-011: Semantic Cache Degradation

**Sintomi:**
- Cache hit rate < 80%
- Latenza sentiment analysis aumentata
- Costi Hume AI inaspettatamente alti
- Alert: `semantic_cache_hit_rate_low`

**Blast Radius:**
- ⚠️ Costi Hume AI +50%
- ⚠️ Latenza sentiment +2-3s per miss
- ✅ No data loss
- ✅ Fallisce gracefully a Hume API

**Diagnostica:**
```bash
# Verifica cache stats
curl http://localhost:8000/cache/stats

# Verifica dimensione cache
psql -c "SELECT count(*) FROM sentiment_cache;"

# Verifica embedding model
python -c "from sentence_transformers import SentenceTransformer; print('OK')"
```

**Recovery:**
```bash
# Warm cache se necessario
curl -X POST http://localhost:8000/cache/warm \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"transcriptions": ["common phrase 1", "common phrase 2"]}'

# Clear old cache se troppo grande
curl -X POST http://localhost:8000/cache/clear-old \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"days": 30}'
```

---

### RB-012: FRANCO Retention Agent Failure

**Sintomi:**
- Chiamate retention non partono
- Queue spedizioni 7 giorni accumulata
- Alert: `franco_retention_backlog`

**Blast Radius:**
- ⚠️ Mancata retention clienti post-consegna
- ⚠️ Potenziale churn aumentato
- ✅ Nessun impatto su spedizioni attive

**Diagnostica:**
```bash
# Verifica stats FRANCO
curl http://localhost:8000/franco/stats

# Verifica circuit breaker
curl http://localhost:8000/metrics/circuit_breakers | grep franco

# Trigger manuale per test
curl -X POST http://localhost:8000/franco/internal/trigger \
  -H "Authorization: Bearer $TOKEN"
```

**Recovery:**
```bash
# Reset circuit breaker se aperto
redis-cli del circuit_breaker:franco_retell

# Process backlog manualmente
python scripts/franco_process_backlog.py --max-calls=10
```

---

## Blast Radius Matrix

| Component | Failure Impact | Cascading Effect | Recovery Time | Data Loss Risk |
|-----------|---------------|------------------|---------------|----------------|
| PostgreSQL | 🔴 CRITICAL | All DB operations blocked | 5-30 min | None (backup) |
| Redis | 🟡 MEDIUM | Performance -50% | 2-5 min | None (cache) |
| Hume AI | 🟢 LOW | Fallback to Ollama | 1 min | None |
| SAP ERP | 🟡 MEDIUM | Quotes unsynced | 15-60 min | None (queue) |
| DAT iQ | 🟡 MEDIUM | Pricing less accurate | 5-30 min | None (cache) |
| Polygon | 🟡 MEDIUM | POD delayed | 10-60 min | After 24h |
| Vault | 🔴 CRITICAL | Total degradation | 5-15 min | None (TTL) |
| Istio | 🔴 CRITICAL | Service mesh down | 5-20 min | None |
| Blockchain | 🟡 MEDIUM | POD verification blocked | 10-30 min | After 24h |
| Carbon | 🟢 LOW | Reporting only | 5-10 min | None |
| **Semantic Cache** | 🟢 LOW | Higher costs, no degradation | 2-5 min | None |
| **FRANCO** | 🟢 LOW | No retention calls | 5-10 min | None |

---

## Escalation Matrix

| Livello | Contatto | Ruolo | Quando Contattare |
|---------|----------|-------|-------------------|
| L1 | On-call Engineer | SRE | Tutti gli incidenti |
| L2 | Tech Lead | Engineering | SEV1 > 30 min, SEV2 > 2h |
| L3 | VP Engineering | Management | SEV1 > 1h, multiple SEV2 |
| L4 | CTO | Executive | Customer-impacting > 4h |
| Vendor | Hume/DAT/SAP Support | External | Third-party issues |

**Contatti:**
- On-call: `+39-XXX-XXXX` (PagerDuty)
- Tech Lead: `tech-lead@company.com`
- Slack: `#incidents-war-room`

---

### RB-013: Enclave Attestation Failure (Confidential Computing)

**Sintomi:**
- Health check FAILED: `/health/enclave` → `attestation_valid: false`
- Secrets non provisionati alle enclaves
- Errori `EnclaveNotProvisionedError` nei logs

**Blast Radius:**
- ⚠️ Agenti AI non possono accedere a API keys
- ⚠️ Chiamate vocali in fallback a modalità standard

**Diagnosi:**
```bash
# Verifica attestation report
curl http://localhost:8000/health/enclave | jq .

# Check Vault logs per errori di verifica
kubectl logs -n vault vault-0 | grep -i "attestation"

# Verifica measurement atteso vs actual
kubectl exec -n confidential-agents sara-agent-enclave-xxx -- cat /run/attestation/measurement
```

**Mitigation:**
1. Se simulation mode: riavvia enclave
2. Se SEV-SNP/TDX: verifica hardware (dmesg | grep -i sev)
3. Se measurement mismatch: aggiorna Vault policy con nuovo measurement
4. Force re-attestation: `POST /admin/enclave/re attest`

**Escalation:** Escalare a Platform Team se problema hardware

---

### RB-014: PAOLO Agent Circuit Breaker Open

**Sintomi:**
- Failover non eseguiti nonostante carrier degradati
- Log: `paolo_circuit_breaker_open`
- Metrica `paolo_circuit_breaker_failures >= 5`

**Blast Radius:**
- ⚠️ Carrier failure non gestiti automaticamente
- ⚠️ Rischio shipment delays

**Diagnosi:**
```bash
# Verifica stato PAOLO
curl http://localhost:8000/self-healing/status | jq .agents.paolo

# Check errori recenti
kubectl logs deployment/api | grep -i "paolo" | tail -50
```

**Mitigation:**
1. Identifica causa failures (DB? Blockchain?)
2. Fix causa root
3. Reset circuit breaker: riavvia PAOLO
4. `POST /admin/resume-paolo` per riattivare monitoring

**Workaround:** Failover manuali via `POST /self-healing/failover/execute`

---

### RB-015: GIULIA High Escalation Rate

**Sintomi:**
- Escalation rate > 20% (target < 5%)
- Molte dispute in attesa di human arbitration
- Log: `human_approval_required` frequenti

**Blast Radius:**
- ⚠️ Backlog dispute da risolvere manualmente
- ⚠️ Delay rimborsi/pagamenti

**Diagnosi:**
```bash
# Statistiche escalation
curl http://localhost:8000/self-healing/status | jq .metrics.human_escalation_rate_percent

# Lista dispute pending
curl "http://localhost:8000/self-healing/disputes?only_human=true" | jq .

# Check AI service (Ollama)
curl $OLLAMA_URL/api/tags
```

**Mitigation:**
1. Se Ollama down: riavvia servizio
2. Se confidence bassa: verifica qualità training data
3. Override temporaneo: `POST /admin/override-giulia` (human-only)
4. Processa dispute backlog manualmente

**Escalation:** ML Team se modello AI non performante

---

### RB-016: CarrierEscrow Smart Contract Failure

**Sintomi:**
- Transazioni blockchain fallite
- Errori `transferToNewCarrier` o `resolveDispute`
- Log: `blockchain_resolution_failed`

**Blast Radius:**
- ⚠️ Failover non completati (inconsistenza DB vs Blockchain)
- ⚠️ Fondi bloccati in escrow

**Diagnosi:**
```bash
# Verifica gas price
curl $POLYGON_RPC -X POST -d '{"jsonrpc":"2.0","method":"eth_gasPrice","params":[],"id":1}'

# Check escrow contract balance
cast balance $CARRIER_ESCROW_ADDRESS --rpc-url $POLYGON_RPC

# Verifica nonce stuck
kubectl logs deployment/api | grep -i "nonce"
```

**Mitigation:**
1. Se gas price alto: usa EIP-1559 con maxFeePerGas
2. Se nonce mismatch: reset nonce tracker
3. Se contract bug: `emergencyRefund` da admin wallet
4. Attiva modalità manuale: `PAOLO_BYPASS_BLOCKCHAIN=true`

**Escalation:** Blockchain Team immediatamente

---

## Recovery Procedures

### Disaster Recovery - Site Total Loss

**RTO:** 4 ore  
**RPO:** 15 min (continuos backup)

**Steps:**
1. Attivare DR site (Kubernetes cluster secondario)
2. Restore database da ultimo snapshot (S3)
3. Verifica Vault unseal nel DR site
4. Redirect DNS al DR site
5. Verifica tutti i circuit breakers
6. Replay queued transactions

### Database Point-in-Time Recovery

```bash
# Identifica punto di recovery
echo "2026-02-14 14:30:00" > recovery_time.txt

# Restore da WAL archives
pg_basebackup -D /var/lib/postgresql/recovery -X fetch

# Recovery specifico punto
pg_ctl start -D /var/lib/postgresql/recovery \
  -o "--recovery-target-time='2026-02-14 14:30:00'"
```

### Rollback Deployment

```bash
# Rollback immediato
kubectl rollout undo deployment/api

# O specifica revisione
kubectl rollout undo deployment/api --to-revision=3

# Verifica rollback
kubectl rollout status deployment/api
```

---

## Appendice: Monitoring Queries

### Database Performance
```sql
-- Query lente (>1s)
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 1000
ORDER BY mean_exec_time DESC
LIMIT 10;

-- Locks attivi
SELECT * FROM pg_locks WHERE NOT granted;

-- Connection pool usage
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
```

### Circuit Breaker Status
```bash
# Tutti i circuit breakers
redis-cli keys "circuit_breaker:*" | while read key; do
  echo "$key: $(redis-cli get $key)"
done
```

---

## Version History

### v1.4.0 (2026-02-15)
- Aggiunti RB-013 Enclave Attestation, RB-014 PAOLO CB, RB-015 GIULIA Escalation, RB-016 Escrow Failure
- Aggiornata checklist giornaliera con enclave e self-healing
- Aggiunte procedure recovery per TEE e smart contract

### v1.3.0 (2026-02-15)
- Aggiunti RB-011 Semantic Cache, RB-012 FRANCO
- Aggiornata checklist giornaliera con nuovi servizi
- Aggiornata Blast Radius Matrix

### v1.2.0 (2026-02-14)
- Aggiunti RB-006 through RB-010 per Business Layer
- Aggiornato Blast Radius Matrix
- Aggiunta procedura Vault recovery
- Aggiunti comandi monitoring

### v1.1.0 (2026-01-30)
- Aggiunti RB-004, RB-005 per ERP e Market Data
- Aggiornata escalation matrix

### v1.0.0 (2026-01-15)
- Runbook iniziale (RB-001 through RB-003)
- Foundation procedures
