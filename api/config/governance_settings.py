"""
AUTO-BROKER: Governance Settings (Pydantic)

Validazione configurazione governance con Pydantic v2.
"""
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import yaml
from pydantic import BaseModel, Field, field_validator, ConfigDict


class PaoloThresholds(BaseModel):
    """Soglie decisionali PAOLO."""
    model_config = ConfigDict(frozen=True)
    
    full_auto_max_eur: Decimal = Field(default=Decimal("5000"), gt=0)
    hot_standby_max_eur: Decimal = Field(default=Decimal("10000"), gt=0)
    human_in_loop_max_eur: Decimal = Field(default=Decimal("50000"), gt=0)
    dual_control_min_eur: Decimal = Field(default=Decimal("50000"), gt=0)
    
    @field_validator('hot_standby_max_eur')
    @classmethod
    def hot_standby_above_full_auto(cls, v: Decimal, info) -> Decimal:
        if 'full_auto_max_eur' in info.data and v <= info.data['full_auto_max_eur']:
            raise ValueError('hot_standby_max_eur must be greater than full_auto_max_eur')
        return v
    
    @field_validator('dual_control_min_eur')
    @classmethod
    def dual_control_above_human_in_loop(cls, v: Decimal, info) -> Decimal:
        if 'human_in_loop_max_eur' in info.data and v < info.data['human_in_loop_max_eur']:
            raise ValueError('dual_control_min_eur must be >= human_in_loop_max_eur')
        return v


class PaoloTimeouts(BaseModel):
    """Timeout PAOLO."""
    model_config = ConfigDict(frozen=True)
    
    veto_window_seconds: int = Field(default=60, ge=10, le=300)
    escalation_first_reminder_seconds: int = Field(default=15, ge=5, le=60)
    escalation_backup_seconds: int = Field(default=30, ge=10, le=120)


class PaoloConfig(BaseModel):
    """Configurazione PAOLO."""
    model_config = ConfigDict(frozen=True)
    
    thresholds: PaoloThresholds = Field(default_factory=PaoloThresholds)
    timeouts: PaoloTimeouts = Field(default_factory=PaoloTimeouts)


class GiuliaThresholds(BaseModel):
    """Soglie decisionali GIULIA."""
    model_config = ConfigDict(frozen=True)
    
    full_auto_max_eur: Decimal = Field(default=Decimal("1000"), gt=0)
    fast_track_max_eur: Decimal = Field(default=Decimal("3000"), gt=0)
    human_in_loop_max_eur: Decimal = Field(default=Decimal("10000"), gt=0)
    
    @field_validator('fast_track_max_eur')
    @classmethod
    def fast_track_above_full_auto(cls, v: Decimal, info) -> Decimal:
        if 'full_auto_max_eur' in info.data and v <= info.data['full_auto_max_eur']:
            raise ValueError('fast_track_max_eur must be greater than full_auto_max_eur')
        return v


class GiuliaConfidence(BaseModel):
    """Soglie confidence GIULIA."""
    model_config = ConfigDict(frozen=True)
    
    fast_track_confidence_min: Decimal = Field(default=Decimal("0.95"), ge=0, le=1)


class GiuliaTimeouts(BaseModel):
    """Timeout GIULIA."""
    model_config = ConfigDict(frozen=True)
    
    standard_approval_hours: int = Field(default=4, ge=1, le=24)
    escalation_senior_hours: int = Field(default=24, ge=4, le=72)


class GiuliaConfig(BaseModel):
    """Configurazione GIULIA."""
    model_config = ConfigDict(frozen=True)
    
    thresholds: GiuliaThresholds = Field(default_factory=GiuliaThresholds)
    confidence: GiuliaConfidence = Field(default_factory=GiuliaConfidence)
    timeouts: GiuliaTimeouts = Field(default_factory=GiuliaTimeouts)


class BusinessHours(BaseModel):
    """Orari lavorativi."""
    model_config = ConfigDict(frozen=True)
    
    start: str = Field(default="09:00", pattern=r"^\d{2}:\d{2}$")
    end: str = Field(default="18:00", pattern=r"^\d{2}:\d{2}$")
    weekend_policy: str = Field(default="emergency_only")
    holidays_policy: str = Field(default="human_in_loop_for_all")
    
    @field_validator('end')
    @classmethod
    def end_after_start(cls, v: str, info) -> str:
        if 'start' in info.data:
            start_h, start_m = map(int, info.data['start'].split(':'))
            end_h, end_m = map(int, v.split(':'))
            if (end_h, end_m) <= (start_h, start_m):
                raise ValueError('business end must be after start')
        return v


class HealthCheckConfig(BaseModel):
    """Configurazione health check."""
    model_config = ConfigDict(frozen=True)
    
    max_dashboard_downtime_seconds: int = Field(default=30, ge=5, le=300)
    max_notification_downtime_seconds: int = Field(default=60, ge=10, le=600)
    operator_heartbeat_timeout_seconds: int = Field(default=30, ge=5, le=120)


class AuditConfig(BaseModel):
    """Configurazione audit."""
    model_config = ConfigDict(frozen=True)
    
    retention_days: int = Field(default=2555, ge=365)  # 7 anni minimo
    ipfs_enabled: bool = False
    gdpr_article22_compliance: bool = True
    require_rationale_for_veto: bool = True


class EscalationConfig(BaseModel):
    """Configurazione escalation."""
    model_config = ConfigDict(frozen=True)
    
    enabled: bool = True
    primary_timeout_seconds: int = Field(default=30, ge=10, le=120)
    backup_operator_enabled: bool = True


class NotificationsConfig(BaseModel):
    """Configurazione notifiche."""
    model_config = ConfigDict(frozen=True)
    
    channels: dict = Field(default_factory=lambda: {
        "push": True,
        "email": True,
        "sms": True,
        "voice_call": False
    })
    escalation: EscalationConfig = Field(default_factory=EscalationConfig)


class GovernanceSettings(BaseModel):
    """
    Settings complete governance.
    
    Validazione Pydantic v2 con defaults sicuri.
    """
    model_config = ConfigDict(frozen=True)
    
    governance_enabled: bool = Field(default=False)
    
    paolo: PaoloConfig = Field(default_factory=PaoloConfig)
    giulia: GiuliaConfig = Field(default_factory=GiuliaConfig)
    business_hours: BusinessHours = Field(default_factory=BusinessHours)
    holidays: List[str] = Field(default_factory=list)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    audit: AuditConfig = Field(default_factory=AuditConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    current_rollout_phase: str = Field(default="shadow_mode")
    
    @field_validator('holidays')
    @classmethod
    def validate_holiday_dates(cls, v: List[str]) -> List[str]:
        """Valida formato date festività (YYYY-MM-DD)."""
        for date_str in v:
            try:
                from datetime import datetime
                datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                raise ValueError(f'Invalid holiday date format: {date_str}, expected YYYY-MM-DD')
        return v
    
    @classmethod
    def from_yaml(cls, path: str) -> "GovernanceSettings":
        """
        Carica settings da file YAML.
        
        Args:
            path: Percorso file YAML
            
        Returns:
            GovernanceSettings validati
        """
        file_path = Path(path)
        
        if not file_path.exists():
            # Ritorna defaults se file non esiste
            return cls()
        
        with open(file_path, 'r') as f:
            data = yaml.safe_load(f)
        
        return cls.model_validate(data)
    
    def to_yaml(self, path: str) -> None:
        """
        Salva settings su file YAML.
        
        Args:
            path: Percorso file YAML
        """
        file_path = Path(path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.model_dump(mode='json')
        
        with open(file_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)


# Singleton per applicazione
_governance_settings: Optional[GovernanceSettings] = None


def get_governance_settings(config_path: str = "/app/config/governance.yaml") -> GovernanceSettings:
    """
    Factory per GovernanceSettings singleton.
    
    Args:
        config_path: Percorso file YAML
        
    Returns:
        GovernanceSettings validati
    """
    global _governance_settings
    
    if _governance_settings is None:
        _governance_settings = GovernanceSettings.from_yaml(config_path)
    
    return _governance_settings


def reload_governance_settings(config_path: str = "/app/config/governance.yaml") -> GovernanceSettings:
    """
    Forza ricaricamento settings da YAML.
    
    Args:
        config_path: Percorso file YAML
        
    Returns:
        GovernanceSettings aggiornati
    """
    global _governance_settings
    _governance_settings = GovernanceSettings.from_yaml(config_path)
    return _governance_settings