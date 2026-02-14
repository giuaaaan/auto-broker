# ADR-017: Revenue-Driven Progressive Scaling

## Status
PROPOSED

## Context

AUTO-BROKER deve gestire costi infrastrutturali che variano da €50/mese (bootstrap) a €35k/mese (enterprise), con un burn rate completo di €56.7k/mese includendo il team. Attivare tutte le risorse sin dal giorno 1 creerebbe:

- Cash burn insostenibile senza revenue corrispondente
- Risk di failure per mancanza di runway
- Over-engineering per volumi iniziali bassi

Serve un sistema che **attivi componenti cloud solo quando il fatturato lo giustifica**.

## Decision

Implementare **Revenue-Driven Progressive Scaling**: un sistema automatico che:

1. **Traccia MRR** (Monthly Recurring Revenue) in tempo reale
2. **Definisce 5 livelli economici** con soglie revenue
3. **Attiva componenti progressivamente** da cold → warm → hot
4. **Enforce safety limit**: max 90% costo/revenue
5. **Supporta rollback** automatico in caso di churn

### Livelli Economici

| Livello | Revenue | Max Burn | Componenti | Debounce |
|---------|---------|----------|------------|----------|
| 0 | €0-449 | €450 | SQLite, Ollama | N/A |
| 1 | €450-799 | €800 | EKS Control Plane | 1 mese |
| 2 | €800-2,999 | €3k | Hume AI, K8s Workers | 2 mesi |
| 3 | €3k-9,999 | €10k | Vault HA, Dat-IQ | 2 mesi |
| 4 | €10k+ | €35k | TEE, Full Escrow | 3 mesi |

### Stato Risorse

```
COLD    → Codice statico, non deployato
WARMING → Deploy in corso
WARM    → Deployato, fermo (replicas: 0) - costo minimo
HOT     → Attivo e operativo
```

### Safety Checks

1. **Cost-Revenue Ratio**: Blocco se costo > 90% revenue
2. **Debounce Logic**: Richiede N mesi consecutivi sopra soglia
3. **Circuit Breaker**: Fail-fast su errori provisioner
4. **Manual Override**: Possibile con approvazione esplicita

## Consequences

### Positive

- **Cash-efficient**: Nessun costo anticipato
- **Risk mitigation**: Componenti attivati solo con revenue garantita
- **Scalability**: Crescita naturale con business
- **Observability**: Metriche chiare su costi vs revenue
- **Auto-rollback**: Protezione da churn improvviso

### Negative

- **Cold start latency**: Attivazione warm→hot richiede 1-5 minuti
- **Complexity**: Più codice da mantenere (monitor, orchestrator)
- **Testing**: Scenari più complessi (multi-stato componenti)
- **Dependency**: Forte accoppiamento costi ↔ architettura

### Risks

| Risk | Mitigation |
|------|------------|
| Attivazione troppo lenta | Pre-warming mantenendo risorse warm |
| Revenue fittizia/spike | Media 3 mesi + debounce logic |
| Churn non rilevato | Monitoraggio giornaliero + auto-rollback |
| Costo nascosto | Tracking esplicito + alert 80% threshold |

## Alternatives Considered

### Alternative 1: Fixed Infrastructure
Tutti i componenti sempre attivi, scaling manuale.

**Rejected**: Costo €31.7k/mese dal giorno 1, runway insufficiente.

### Alternative 2: Usage-Based Only
Attivazione 100% usage-based, nessun livello predefinito.

**Rejected**: Troppo complesso gestire dipendenze componenti, difficile prevedere costi.

### Alternative 3: Time-Based Scaling
Attivazione programmata (es: dopo 6 mesi).

**Rejected**: Non correlata al business, rischio attivazione senza revenue.

## Implementation

### Services

```
api/services/revenue_monitor.py          # 624 lines
api/services/provisioning_orchestrator.py # 533 lines
```

### Database

```sql
revenue_snapshots         -- MRR/ARR tracking
economic_scaling_log      -- Audit trail
component_activation_states -- Stato componenti
revenue_threshold_config  -- Config runtime
```

### Configuration

```yaml
# config/revenue_thresholds.yaml
level_2_growth:
  revenue_range:
    min: 800
    max: 2999
  required_consecutive_months: 2
  auto_enable:
    - hume_ai_prosody
    - kubernetes_workers
```

## Metrics

```
revenue_mrr_gauge              # €/mese
revenue_cost_ratio_percentage  # 0-100%
component_activation_state     # 0=cold, 1=warm, 2=hot
provisioning_duration_seconds  # Tempo attivazione
```

## Testing Strategy

- Unit: 95% coverage (mock providers cloud)
- Integration: Test sequenza livelli
- Load: Simula revenue spike 10x
- Chaos: Verifica rollback su revenue drop

## References

- [REVENUE_DRIVEN_SCALING.md](../REVENUE_DRIVEN_SCALING.md)
- [COST_ANALYSIS_CORRECTED.md](../COST_ANALYSIS_CORRECTED.md)
- Migration: `2026_02_16_revenue_scaling.py`

## Decision Record

| Date | Author | Decision |
|------|--------|----------|
| 2026-02-16 | AI Engineer | PROPOSED Revenue-Driven Scaling |
| 2026-02-XX | Tech Lead | ACCEPTED after review |

---

**ADR Number**: 017  
**Created**: 2026-02-16  
**Supersedes**: N/A  
**Superseded by**: N/A