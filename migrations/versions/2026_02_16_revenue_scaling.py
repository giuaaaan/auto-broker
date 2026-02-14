"""
AUTO-BROKER Migration: Revenue-Driven Progressive Scaling

Aggiunge tabelle per tracciamento revenue e log scaling economico.
Livelli: 0-4 con attivazione progressiva basata su MRR.

Revision ID: 2026_02_16_revenue_scaling
Revises: 2026_02_15_governance_core
Create Date: 2026-02-16 14:00:00.000000+00:00
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import Numeric, Text, Enum

# revision identifiers
revision = '2026_02_16_revenue_scaling'
down_revision = '2026_02_15_governance_core'
branch_labels = None
depends_on = None


def upgrade():
    # ============== Tabella Revenue Snapshot ==============
    # Snapshot mensile del fatturato per tracciamento MRR/ARR
    op.create_table(
        'revenue_snapshots',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('snapshot_date', sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column('period_type', sa.Enum('daily', 'weekly', 'monthly', 'yearly', name='revenue_period_type'), nullable=False, default='monthly'),
        
        # Metriche revenue
        sa.Column('mrr', Numeric(18, 6), nullable=False, comment='Monthly Recurring Revenue'),
        sa.Column('arr', Numeric(18, 6), nullable=False, comment='Annual Recurring Revenue'),
        sa.Column('total_revenue', Numeric(18, 6), nullable=False, comment='Revenue totale nel periodo'),
        
        # Dettaglio fonti revenue
        sa.Column('shipment_revenue', Numeric(18, 6), default=0),
        sa.Column('subscription_revenue', Numeric(18, 6), default=0),
        sa.Column('commission_revenue', Numeric(18, 6), default=0),
        sa.Column('other_revenue', Numeric(18, 6), default=0),
        
        # Metriche di crescita
        sa.Column('previous_period_revenue', Numeric(18, 6)),
        sa.Column('growth_rate_period_over_period', Numeric(8, 4)),  # Es: 0.15 = 15%
        
        # Metadata
        sa.Column('record_count', sa.Integer, default=0, comment='Numero record spedizioni/pagamenti'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('calculated_by', sa.String(50), default='system'),
        
        sa.Index('ix_revenue_snapshots_date_period', 'snapshot_date', 'period_type'),
        sa.Index('ix_revenue_snapshots_mrr', 'mrr'),
    )
    
    # ============== Tabella Economic Scaling Log ==============
    # Log di tutte le attivazioni/disattivazioni livelli economici
    op.create_table(
        'economic_scaling_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), index=True),
        
        # Identificazione livello
        sa.Column('level_id', sa.String(50), nullable=False, index=True, comment='Es: level_0_survival, level_1_bootstrap'),
        sa.Column('level_name', sa.String(100)),
        
        # Tipo azione
        sa.Column('action_type', sa.Enum(
            'activation',      # Attivazione nuovo livello
            'deactivation',    # Deattivazione (rollback)
            'pre_warming',     # Pre-riscaldamento
            'simulation',      # Simulazione (dry run)
            'safety_blocked',  # Blocco per safety check
            name='scaling_action_type'
        ), nullable=False),
        
        # Trigger
        sa.Column('triggered_by', sa.Enum(
            'automatic_revenue_threshold',  # Trigger automatico su soglia
            'manual_override',               # Override manuale
            'scheduled',                     # Programmato
            'simulation',                    # Solo simulazione
            name='scaling_trigger_type'
        ), nullable=False),
        
        # Metriche al momento dell'azione
        sa.Column('mrr_at_action', Numeric(18, 6), nullable=False),
        sa.Column('arr_at_action', Numeric(18, 6)),
        sa.Column('consecutive_months_above_threshold', sa.Integer, default=0),
        
        # Costi
        sa.Column('max_monthly_burn_eur', Numeric(18, 6), nullable=False),
        sa.Column('estimated_monthly_cost_eur', Numeric(18, 6)),
        sa.Column('revenue_cost_ratio', Numeric(5, 4), comment='Es: 0.85 = 85%'),
        
        # Componenti
        sa.Column('components_activated', postgresql.ARRAY(sa.String(100)), default=[]),
        sa.Column('components_deactivated', postgresql.ARRAY(sa.String(100)), default=[]),
        sa.Column('components_failed', postgresql.ARRAY(sa.String(100)), default=[]),
        
        # Risultato
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('duration_seconds', sa.Numeric(8, 2)),
        sa.Column('error_message', Text),
        
        # Safety override
        sa.Column('safety_check_passed', sa.Boolean, default=True),
        sa.Column('manual_override_applied', sa.Boolean, default=False),
        sa.Column('override_reason', Text),
        sa.Column('override_approved_by', sa.String(100)),
        
        # Tracciamento
        sa.Column('correlation_id', sa.String(36), index=True),
        sa.Column('ipfs_audit_hash', sa.String(64), nullable=True),
    )
    
    # ============== Tabella Component Activation State ==============
    # Stato corrente di ogni componente cloud
    op.create_table(
        'component_activation_states',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        
        sa.Column('component_name', sa.String(100), nullable=False, unique=True, index=True),
        sa.Column('component_type', sa.Enum(
            'kubernetes', 'database', 'cache', 'ai_service',
            'security', 'monitoring', 'blockchain', 'storage',
            name='component_type'
        ), nullable=False),
        
        # Stato
        sa.Column('state', sa.Enum(
            'cold',          # Non deployato
            'warming',       # Deploy in corso
            'warm',          # Deployato ma fermo (replicas: 0)
            'activating',    # Attivazione in corso
            'hot',           # Attivo e operativo
            'deactivating',  # Decommissioning
            'error',         # Errore
            name='resource_state'
        ), nullable=False, default='cold'),
        
        # Livello economico associato
        sa.Column('minimum_level_id', sa.String(50), comment='Livello minimo per attivazione'),
        sa.Column('current_level_id', sa.String(50)),
        
        # Costi
        sa.Column('monthly_cost_eur', Numeric(18, 6), default=0),
        sa.Column('cost_model', sa.Enum('flat', 'usage_based', 'hybrid', name='cost_model'), default='flat'),
        
        # Configurazione
        sa.Column('configuration', postgresql.JSONB, default={}),
        sa.Column('cloud_provider', sa.String(50)),
        sa.Column('region', sa.String(50)),
        sa.Column('resource_id', sa.String(200), comment='ID risorsa nel cloud provider'),
        
        # Metriche
        sa.Column('last_activation_at', sa.DateTime(timezone=True)),
        sa.Column('last_deactivation_at', sa.DateTime(timezone=True)),
        sa.Column('total_activations', sa.Integer, default=0),
        sa.Column('total_uptime_hours', sa.Numeric(10, 2), default=0),
        
        # Health
        sa.Column('health_status', sa.Enum('healthy', 'degraded', 'unhealthy', 'unknown', name='component_health'), default='unknown'),
        sa.Column('last_health_check', sa.DateTime(timezone=True)),
    )
    
    # ============== Tabella Revenue Threshold Config ==============
    # Configurazione dinamica soglie (override runtime)
    op.create_table(
        'revenue_threshold_config',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        
        sa.Column('level_id', sa.String(50), nullable=False, unique=True),
        sa.Column('level_name', sa.String(100), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        
        # Soglie
        sa.Column('revenue_min', Numeric(18, 6), nullable=False),
        sa.Column('revenue_max', Numeric(18, 6)),
        
        # Requisiti
        sa.Column('required_consecutive_months', sa.Integer, default=1),
        sa.Column('requires_manual_approval', sa.Boolean, default=False),
        
        # Limiti
        sa.Column('max_monthly_burn_eur', Numeric(18, 6), nullable=False),
        sa.Column('safety_cost_threshold_pct', sa.Numeric(5, 2), default=90.00),
        
        # Configurazione YAML
        sa.Column('config_yaml', Text),
        
        # Audit
        sa.Column('created_by', sa.String(100), default='system'),
        sa.Column('updated_by', sa.String(100)),
        sa.Column('version', sa.Integer, default=1),
    )
    
    # ============== Foreign Keys ==============
    # Nessuna FK necessaria per queste tabelle (sono indipendenti)
    
    # ============== Commenti ==============
    op.create_table_comment('revenue_snapshots', 'Snapshot mensile fatturato per calcolo MRR/ARR')
    op.create_table_comment('economic_scaling_log', 'Audit trail di tutte le azioni di scaling economico')
    op.create_table_comment('component_activation_states', 'Stato attuale di ogni componente cloud')
    op.create_table_comment('revenue_threshold_config', 'Configurazione runtime soglie revenue')
    
    # ============== Insert default config ==============
    # Inserisci configurazione default per i 5 livelli
    op.execute("""
        INSERT INTO revenue_threshold_config 
            (level_id, level_name, revenue_min, revenue_max, max_monthly_burn_eur, 
             required_consecutive_months, safety_cost_threshold_pct, config_yaml)
        VALUES 
            ('level_0_survival', 'Survival Mode', 0, 449, 450, 0, 90.00, 'manual_process: true'),
            ('level_1_bootstrap', 'Bootstrap Mode', 450, 799, 800, 1, 90.00, 'eks_control_plane: true'),
            ('level_2_growth', 'Growth Mode', 800, 2999, 3000, 2, 90.00, 'hume_ai: true, kubernetes_workers: true'),
            ('level_3_scale', 'Scale Mode', 3000, 9999, 10000, 2, 90.00, 'vault_ha: true, dat_iq: true'),
            ('level_4_enterprise', 'Enterprise Mode', 10000, NULL, 35000, 3, 90.00, 'tee_confidential: true, escrow_full: true')
    """)


def downgrade():
    # Elimina in ordine inverso
    op.drop_table('revenue_threshold_config')
    op.drop_table('component_activation_states')
    op.drop_table('economic_scaling_log')
    op.drop_table('revenue_snapshots')
    
    # Elimina enum types
    op.execute('DROP TYPE IF EXISTS revenue_period_type')
    op.execute('DROP TYPE IF EXISTS scaling_action_type')
    op.execute('DROP TYPE IF EXISTS scaling_trigger_type')
    op.execute('DROP TYPE IF EXISTS component_type')
    op.execute('DROP TYPE IF EXISTS resource_state')
    op.execute('DROP TYPE IF EXISTS cost_model')
    op.execute('DROP TYPE IF EXISTS component_health')