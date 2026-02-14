# AUTO-BROKER Business Layer

## Overview

The Business Layer implements core enterprise integrations for AUTO-BROKER:

- **ERP Connectors**: SAP S/4HANA, NetSuite, Microsoft Dynamics 365
- **Market Intelligence**: DAT iQ, Teleroute
- **Blockchain**: Polygon smart contracts for POD verification
- **Carbon Tracking**: GLEC Framework / ISO 14083 emissions calculation
- **Chaos Engineering**: Resilience testing

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        AUTO-BROKER API                          │
├─────────────────────────────────────────────────────────────────┤
│  ERP Connectors    │  Market Data      │  Pricing Engine V2   │
│  ├── SAP S/4HANA   │  ├── DAT iQ       │  ├── Cost + Margin   │
│  ├── NetSuite      │  └── Teleroute    │  ├── Market Adj      │
│  └── Dynamics 365  │                   │  └── Confidence CI   │
├─────────────────────────────────────────────────────────────────┤
│  Blockchain        │  Carbon Tracking  │  Chaos Engineering   │
│  ├── POD Contract  │  ├── GLEC Calc    │  ├── Experiments     │
│  └── IPFS Storage  │  └── CSRD Report  │  └── Failure Inject  │
├─────────────────────────────────────────────────────────────────┤
│                    Vault (Dynamic Credentials)                  │
└─────────────────────────────────────────────────────────────────┘
```

## ERP Connectors

### SAP S/4HANA Adapter

OData v4 integration for SAP S/4HANA Cloud/On-Premise.

```python
from connectors.erp.sap_s4hana_adapter import SAPS4HANAAdapter

async with SAPS4HANAAdapter() as sap:
    # Master data
    material = await sap.get_material("MAT001")
    customer = await sap.get_customer("C001")
    
    # Transactional data
    orders = await sap.get_sales_orders(from_date=datetime.now() - timedelta(days=7))
    deliveries = await sap.get_delivery_notes()
    
    # POD confirmation
    await sap.post_pod_confirmation(
        delivery_id="80000001",
        received_by="John Doe",
        received_at=datetime.now(),
        quantity_received=100
    )
```

### NetSuite Adapter

RESTlet v2 integration with SuiteQL support.

```python
from connectors.erp.netsuite_adapter import NetSuiteAdapter

async with NetSuiteAdapter() as ns:
    # SuiteQL queries
    orders = await ns.execute_suiteql("""
        SELECT id, transactionname, entity, total 
        FROM transaction 
        WHERE type = 'SalesOrd' AND trandate >= '2024-01-01'
    """)
    
    # Create fulfillment
    await ns.create_item_fulfillment(
        order_id="12345",
        items=[{"item_id": "ITEM001", "quantity": 10}],
        tracking_number="TRK123456"
    )
```

### Dynamics 365 Adapter

OData v4 with OAuth 2.0 client credentials flow.

```python
from connectors.erp.dynamics365_adapter import Dynamics365Adapter

async with Dynamics365Adapter() as d365:
    orders = await d365.get_sales_orders(
        customer_account="CUST001",
        status="OpenOrder"
    )
    
    lines = await d365.get_sales_order_lines("SO-001")
```

### Sync Orchestrator

Bidirectional sync with conflict resolution.

```python
from connectors.erp.sync_orchestrator import (
    SyncOrchestrator, SyncRule, SyncDirection, ConflictResolution
)

orchestrator = SyncOrchestrator(db_pool=db_pool)

# Register adapters
orchestrator.register_adapter(SAPS4HANAAdapter())
orchestrator.register_adapter(NetSuiteAdapter())
orchestrator.register_adapter(Dynamics365Adapter())

# Configure sync rules
orchestrator.configure_sync_rule(SyncRule(
    entity_type="sales_order",
    direction=SyncDirection.ERP_TO_AB,
    conflict_resolution=ConflictResolution.TIMESTAMP_WINS,
    sync_interval_minutes=15
))

# Run sync
result = await orchestrator.sync_sales_orders("sap")
```

## Market Intelligence

### DAT iQ Client

Real-time spot rate benchmarking.

```python
from market_data.dat_iq_client import DATiQClient, DATRouteType

async with DATiQClient() as dat:
    # Get spot rate
    rate = await dat.get_spot_rate(
        origin="IT-MIL",
        destination="IT-ROM",
        route_type=DATRouteType.VAN
    )
    
    # Historical analysis
    history = await dat.get_historical_rates(
        origin="IT-MIL",
        destination="IT-ROM",
        days=30
    )
    
    # Market conditions
    market = await dat.get_market_conditions("IT-MIL", "IT-ROM")
    
    # Pricing context
    context = await dat.get_pricing_context(
        origin="IT-MIL",
        destination="IT-ROM",
        cargo_weight_kg=5000
    )
```

### Teleroute Client

European freight exchange integration.

```python
from market_data.teleroute_client import TelerouteClient, TelerouteEquipment

async with TelerouteClient() as tr:
    # Search freight offers
    offers = await tr.search_freight_offers(
        loading_country="IT",
        loading_city="Milano",
        unloading_country="IT",
        equipment=TelerouteEquipment.TENT
    )
    
    # Post vehicle offer
    await tr.post_vehicle_offer(
        current_location=location,
        available_date=datetime.now(),
        equipment=TelerouteEquipment.TENT,
        weight_capacity_kg=24000,
        volume_capacity_m3=90
    )
```

## Pricing Engine V2

Real-time pricing with market rate integration.

```python
from pricing.pricing_engine_v2 import PricingEngineV2, PricingInput, PricingStrategy
from market_data.dat_iq_client import DATRouteType

engine = PricingEngineV2(dat_client=dat_client)

result = await engine.calculate_price(
    shipment_id="SHP001",
    input_data=PricingInput(
        origin_country="IT",
        origin_city="Milano",
        dest_country="IT",
        dest_city="Roma",
        distance_km=500,
        weight_kg=5000,
        equipment_type=DATRouteType.VAN,
        adr=False,
        temperature_controlled=False
    ),
    strategy=PricingStrategy.MARKET_BASED,
    target_margin_pct=15.0
)

# Result includes:
# - customer_price: Final customer price
# - carrier_price: Carrier payout
# - margin_eur: Absolute margin
# - breakdown: Detailed cost components
# - confidence: 95% confidence interval
# - market_rate: Current DAT iQ rate
```

**Pricing Formula:**
```
Customer Price = Base Cost + Margin + Market Adjustment

Base Cost = Fuel + Tolls + Driver + Insurance + Surcharges
Margin = max(Base Cost × Margin%, Minimum Margin)
Market Adjustment = f(DAT iQ benchmark, current price)
```

## Blockchain

### POD Smart Contract (Polygon)

Solidity contract for Proof of Delivery verification.

```solidity
// Key functions:
- createDelivery()      // Create delivery record
- confirmPickup()       // Carrier confirms pickup
- completeDelivery()    // Upload POD to IPFS, record hash
- confirmDelivery()     // Consignee confirms receipt
- openDispute()         // Initiate dispute
- resolveDispute()      // Arbiter resolves dispute
```

### Python Integration

```python
from blockchain.blockchain_service import BlockchainService

service = BlockchainService()

# Upload POD document
result = await service.complete_delivery(
    shipment_id="SHP001",
    document_content=pod_pdf_bytes,
    quantity_delivered=100
)
# Returns: transaction_hash, ipfs_hash, block_number

# Verify document
is_valid = await service.verify_document(
    shipment_id="SHP001",
    document_content=pod_pdf_bytes
)

# Get delivery record
delivery = await service.get_delivery("SHP001")
```

## Carbon Tracking

### GLEC Calculator

ISO 14083:2023 compliant emissions calculation.

```python
from carbon.glec_calculator import GLECCalculator, TransportMode, FuelType

calculator = GLECCalculator()

# Calculate shipment emissions
emissions = calculator.calculate_shipment_emissions(
    shipment_id="SHP001",
    transport_mode=TransportMode.ROAD_HGV,
    fuel_type=FuelType.DIESEL,
    distance_km=500,
    weight_kg=5000,
    temperature_controlled=True
)

# Results:
# - wtw_emissions: Well-to-wheel CO2e (kg)
# - wtt_emissions: Well-to-tank CO2e (kg)
# - ttw_emissions: Tank-to-wheel CO2e (kg)
# - intensity: kg CO2e per ton-km
# - uncertainty range: Based on GLEC methodology
```

### CSRD Reporting

Corporate Sustainability Reporting Directive compliance.

```python
from carbon.csrd_reporter import CSRDReporter

reporter = CSRDReporter(calculator=calculator)

# Generate report
report = reporter.create_report(
    entity_name="Company S.p.A.",
    entity_id="IT12345678901",
    lei_code="529900T8BM49AURSDO55",
    reporting_period_start=date(2024, 1, 1),
    reporting_period_end=date(2024, 12, 31),
    shipments=shipment_data
)

# Export to XBRL (regulatory format)
xbrl = reporter.export_xbrl(report, filename="csrd_2024.xbrl")

# Generate assurance pack for auditors
assurance = reporter.generate_assurance_pack(
    report=report,
    supporting_evidence=["fuel_receipts.pdf", "distance_logs.csv"]
)
```

## Chaos Engineering

### Experiment Runner

System resilience testing.

```python
from chaos.experiment_runner import (
    ExperimentRunner, ExperimentConfig, 
    FailureType, EXPERIMENT_TEMPLATES
)

runner = ExperimentRunner(db_pool=db_pool, redis_client=redis)

# Run experiment
config = ExperimentConfig(
    name="api_latency_test",
    description="Test API resilience under 2s latency",
    target_service="api:8000",
    failure_type=FailureType.LATENCY,
    failure_params={'latency_ms': 2000, 'jitter_pct': 20},
    duration_seconds=300,
    abort_condition_failures=50
)

result = await runner.run_experiment(
    config=config,
    steady_state_check=my_health_check,
    load_generator=my_load_generator
)

# Results include:
# - hypothesis_validated: Did system maintain steady state?
# - total_requests / failed_requests
# - latency stats (avg, p99, min, max)
# - recommendations for improvement
```

## Configuration

### Vault Secrets Structure

```
secret/
├── erp/
│   ├── sap-s4hana      # {base_url, username, password}
│   ├── netsuite        # {account, consumer_key, consumer_secret, token_key, token_secret}
│   └── dynamics365     # {organization_url, tenant_id, client_id, client_secret}
├── market-data/
│   ├── dat-iq          # {api_key, api_secret}
│   └── teleroute       # {username, password, client_id, client_secret}
├── blockchain/
│   ├── polygon         # {provider_url, contract_address}
│   └── wallet          # {private_key}
└── carbon/
    └── glec            # {custom_factors}
```

### Environment Variables

```bash
# ERP
SAP_BASE_URL=https://my-sap-instance.sap.com
NETSUITE_ACCOUNT=123456
D365_URL=https://my-org.operations.dynamics.com

# Market Data
DAT_API_KEY=xxx
TELEROUTE_USERNAME=xxx

# Blockchain
POLYGON_RPC_URL=https://polygon-rpc.com
POD_CONTRACT_ADDRESS=0x...

# IPFS
IPFS_API_URL=http://localhost:5001
```

## Testing

Run business layer tests:

```bash
# Pricing engine
pytest tests/unit/test_pricing_engine_v2.py -v

# Carbon calculator
pytest tests/unit/test_glec_calculator.py -v

# All business layer tests
pytest tests/unit/ -k "pricing or glec or csrd" -v
```

## Compliance

- **ERP Integration**: SOC 2 Type II, ISO 27001
- **Market Data**: GDPR Article 6(1)(f) legitimate interest
- **Blockchain**: eIDAS electronic signature compliance
- **Carbon Reporting**: ISO 14083:2023, GLEC Framework v3.0, CSRD/ESRS E1

## Support

For technical support or feature requests:
- Enterprise Integration: enterprise-support@autobroker.it
- API Documentation: https://docs.autobroker.it/api
- Status Page: https://status.autobroker.it
