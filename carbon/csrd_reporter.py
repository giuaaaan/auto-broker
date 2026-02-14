"""
AUTO-BROKER CSRD Reporter
Corporate Sustainability Reporting Directive compliance
Enterprise Integration - P1

Features:
- ESRS E1 (Climate Change) reporting
- GHG Protocol Scope 3 Category 4 (Upstream transport)
- XBRL format export
- Audit trail
"""

import logging
from dataclasses import dataclass, asdict
from datetime import datetime, date
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import json
import xml.etree.ElementTree as ET

from carbon.glec_calculator import GLECCalculator, CSRDReportEntry, TransportMode, FuelType

logger = logging.getLogger(__name__)


class ESRSStandard(Enum):
    """European Sustainability Reporting Standards."""
    E1_CLIMATE = "E1"  # Climate Change
    E2_POLLUTION = "E2"  # Pollution
    E3_WATER = "E3"  # Water and Marine Resources
    E4_BIODIVERSITY = "E4"  # Biodiversity
    E5_RESOURCES = "E5"  # Resource Use and Circular Economy


class GHGScope(Enum):
    """GHG Protocol Scopes."""
    SCOPE_1 = "Scope 1"  # Direct emissions
    SCOPE_2 = "Scope 2"  # Indirect energy
    SCOPE_3 = "Scope 3"  # Value chain


class GHGCategory(Enum):
    """Scope 3 Categories."""
    CAT_1_PURCHASED_GOODS = "1"
    CAT_2_CAPITAL_GOODS = "2"
    CAT_3_FUEL_ENERGY = "3"
    CAT_4_UPSTREAM_TRANSPORT = "4"  # Relevant for AUTO-BROKER
    CAT_5_WASTE = "5"
    CAT_6_BUSINESS_TRAVEL = "6"
    CAT_7_EMPLOYEE_COMMUTING = "7"
    CAT_8_UPSTREAM_LEASED = "8"
    CAT_9_DOWNSTREAM_TRANSPORT = "9"
    CAT_10_PROCESSING_PRODUCTS = "10"
    CAT_11_USE_PRODUCTS = "11"
    CAT_12_END_OF_LIFE = "12"
    CAT_13_DOWNSTREAM_LEASED = "13"
    CAT_14_FRANCHISES = "14"
    CAT_15_INVESTMENTS = "15"


@dataclass
class ESRSDataPoint:
    """Single ESRS data point."""
    standard: ESRSStandard
    disclosure_requirement: str
    datapoint_id: str
    datapoint_name: str
    value: Any
    unit: str
    financial_year: int
    comparison_year: Optional[int] = None
    comparison_value: Optional[Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'standard': self.standard.value,
            'disclosure_requirement': self.disclosure_requirement,
            'datapoint_id': self.datapoint_id,
            'datapoint_name': self.datapoint_name,
            'value': self.value,
            'unit': self.unit,
            'financial_year': self.financial_year,
            'comparison_year': self.comparison_year,
            'comparison_value': self.comparison_value
        }


@dataclass
class GHGInventory:
    """GHG Protocol inventory."""
    scope: GHGScope
    category: Optional[GHGCategory]
    emissions_tons_co2e: float
    methodology: str
    calculation_date: datetime
    verification_status: str  # Unverified, Third-party verified
    verification_body: Optional[str] = None


@dataclass
class CSRDReport:
    """Complete CSRD sustainability report."""
    entity_name: str
    entity_id: str
    lei_code: Optional[str]  # Legal Entity Identifier
    reporting_period_start: date
    reporting_period_end: date
    publication_date: date
    
    # Governance
    board_responsibility: str
    audit_committee_oversight: bool
    
    # Double materiality assessment
    impact_materiality_topics: List[str]
    financial_materiality_topics: List[str]
    
    # Environmental data
    ghg_inventories: List[GHGInventory]
    energy_consumption_mwh: float
    renewable_energy_pct: float
    
    # Transport specific
    transport_emissions: List[CSRDReportEntry]
    
    # ESRS datapoints
    esrs_datapoints: List[ESRSDataPoint]
    
    # Assurance
    assurance_provider: Optional[str]
    assurance_level: str  # Limited, Reasonable
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'entity_name': self.entity_name,
            'entity_id': self.entity_id,
            'lei_code': self.lei_code,
            'reporting_period': {
                'start': self.reporting_period_start.isoformat(),
                'end': self.reporting_period_end.isoformat()
            },
            'publication_date': self.publication_date.isoformat(),
            'governance': {
                'board_responsibility': self.board_responsibility,
                'audit_committee_oversight': self.audit_committee_oversight
            },
            'materiality': {
                'impact_materiality': self.impact_materiality_topics,
                'financial_materiality': self.financial_materiality_topics
            },
            'environmental': {
                'ghg_inventories': [
                    {
                        'scope': inv.scope.value,
                        'category': inv.category.value if inv.category else None,
                        'emissions_tons': inv.emissions_tons_co2e,
                        'methodology': inv.methodology,
                        'verification': inv.verification_status
                    }
                    for inv in self.ghg_inventories
                ],
                'energy_consumption_mwh': self.energy_consumption_mwh,
                'renewable_energy_pct': self.renewable_energy_pct
            },
            'transport_emissions': [
                {
                    'mode': entry.transport_mode,
                    'ton_km': entry.total_ton_km,
                    'emissions_tons': entry.total_emissions_tons_co2e,
                    'intensity': entry.intensity_kg_co2e_per_ton_km
                }
                for entry in self.transport_emissions
            ],
            'assurance': {
                'provider': self.assurance_provider,
                'level': self.assurance_level
            }
        }


class CSRDReporter:
    """
    CSRD (Corporate Sustainability Reporting Directive) Reporter.
    
    Generates ESRS-compliant sustainability reports with:
    - GHG Protocol Scope 3 Category 4 (Upstream transport)
    - XBRL format for regulatory filing
    - Audit trail for verification
    
    ESRS Standards:
    - E1: Climate Change
    - E2: Pollution
    - E3: Water
    - E4: Biodiversity
    - E5: Resource use
    """
    
    # ESRS E1 Disclosure Requirements
    E1_DISCLOSURES = {
        'E1-1': 'Transition plan for climate change mitigation',
        'E1-2': 'Policies related to climate change mitigation and adaptation',
        'E1-3': 'Actions and resources related to climate change',
        'E1-4': 'Targets related to climate change mitigation and adaptation',
        'E1-5': 'Energy consumption and mix',
        'E1-6': 'Gross Scopes 1, 2, 3 and Total GHG emissions',
        'E1-7': 'GHG removals and mitigation projects',
        'E1-8': 'Internal carbon pricing',
        'E1-9': 'Anticipated financial effects from material physical and transition risks'
    }
    
    def __init__(self, calculator: Optional[GLECCalculator] = None):
        """
        Initialize CSRD reporter.
        
        Args:
            calculator: GLEC calculator instance
        """
        self.calculator = calculator or GLECCalculator()
        self.reports: List[CSRDReport] = []
        self.audit_log: List[Dict] = []
    
    def create_report(
        self,
        entity_name: str,
        entity_id: str,
        lei_code: Optional[str],
        reporting_period_start: date,
        reporting_period_end: date,
        shipments: List[Dict[str, Any]]
    ) -> CSRDReport:
        """
        Create CSRD report from shipment data.
        
        Args:
            entity_name: Company legal name
            entity_id: Tax/VAT identifier
            lei_code: LEI code if available
            reporting_period_start: Start of reporting period
            reporting_period_end: End of reporting period
            shipments: List of shipment data for emissions calculation
            
        Returns:
            CSRDReport
        """
        # Calculate transport emissions
        transport_entries = []
        mode_emissions: Dict[str, List] = {}
        
        for shipment in shipments:
            emissions = self.calculator.calculate_shipment_emissions(
                shipment_id=shipment['id'],
                transport_mode=shipment['mode'],
                fuel_type=shipment.get('fuel', FuelType.DIESEL),
                distance_km=shipment['distance_km'],
                weight_kg=shipment['weight_kg'],
                temperature_controlled=shipment.get('temp_controlled', False)
            )
            
            mode = emissions.transport_mode.value
            if mode not in mode_emissions:
                mode_emissions[mode] = []
            mode_emissions[mode].append(emissions)
        
        # Aggregate by transport mode
        for mode, emissions_list in mode_emissions.items():
            total_ton_km = sum(
                e.weight_tons * e.distance_km for e in emissions_list
            )
            total_emissions = sum(e.wtw_emissions for e in emissions_list)
            
            entry = CSRDReportEntry(
                reporting_period=reporting_period_end,
                entity_name=entity_name,
                transport_mode=mode,
                total_ton_km=total_ton_km,
                total_emissions_tons_co2e=total_emissions / 1000,
                intensity_kg_co2e_per_ton_km=(
                    total_emissions / total_ton_km if total_ton_km > 0 else 0
                ),
                methodology="GLEC Framework v3.0 / ISO 14083:2023",
                assurance_level="Limited"
            )
            transport_entries.append(entry)
        
        # Calculate total Scope 3 Category 4
        total_scope3_cat4 = sum(
            entry.total_emissions_tons_co2e for entry in transport_entries
        )
        
        # Create GHG inventories
        ghg_inventories = [
            GHGInventory(
                scope=GHGScope.SCOPE_3,
                category=GHGCategory.CAT_4_UPSTREAM_TRANSPORT,
                emissions_tons_co2e=total_scope3_cat4,
                methodology="GHG Protocol / GLEC Framework v3.0",
                calculation_date=datetime.now(),
                verification_status="Unverified"
            )
        ]
        
        # Create ESRS datapoints
        datapoints = self._create_esrs_datapoints(
            reporting_period_end.year,
            total_scope3_cat4,
            transport_entries
        )
        
        report = CSRDReport(
            entity_name=entity_name,
            entity_id=entity_id,
            lei_code=lei_code,
            reporting_period_start=reporting_period_start,
            reporting_period_end=reporting_period_end,
            publication_date=date.today(),
            board_responsibility="Board of Directors responsible for sustainability reporting",
            audit_committee_oversight=True,
            impact_materiality_topics=[
                "Climate change",
                "Air pollution",
                "Resource use"
            ],
            financial_materiality_topics=[
                "Carbon pricing risk",
                "Fuel cost volatility",
                "Regulatory compliance"
            ],
            ghg_inventories=ghg_inventories,
            energy_consumption_mwh=0,  # Would be calculated from fuel consumption
            renewable_energy_pct=0,  # Would be tracked separately
            transport_emissions=transport_entries,
            esrs_datapoints=datapoints,
            assurance_provider=None,
            assurance_level="Limited"
        )
        
        self.reports.append(report)
        
        # Audit log
        self.audit_log.append({
            'action': 'report_created',
            'entity': entity_name,
            'period': f"{reporting_period_start} to {reporting_period_end}",
            'total_emissions_tons': total_scope3_cat4,
            'created_at': datetime.now().isoformat()
        })
        
        return report
    
    def _create_esrs_datapoints(
        self,
        financial_year: int,
        total_emissions: float,
        transport_entries: List[CSRDReportEntry]
    ) -> List[ESRSDataPoint]:
        """Create ESRS E1 datapoints."""
        datapoints = []
        
        # E1-6: GHG emissions
        datapoints.append(ESRSDataPoint(
            standard=ESRSStandard.E1_CLIMATE,
            disclosure_requirement="E1-6",
            datapoint_id="E1-6_Scope3",
            datapoint_name="Scope 3 GHG emissions",
            value=round(total_emissions, 2),
            unit="tCO2e",
            financial_year=financial_year
        ))
        
        # E1-6: Breakdown by category
        datapoints.append(ESRSDataPoint(
            standard=ESRSStandard.E1_CLIMATE,
            disclosure_requirement="E1-6",
            datapoint_id="E1-6_Scope3_Cat4",
            datapoint_name="Scope 3 Category 4 - Upstream transport",
            value=round(total_emissions, 2),
            unit="tCO2e",
            financial_year=financial_year
        ))
        
        # Transport intensity by mode
        for entry in transport_entries:
            datapoints.append(ESRSDataPoint(
                standard=ESRSStandard.E1_CLIMATE,
                disclosure_requirement="E1-6",
                datapoint_id=f"E1-6_Intensity_{entry.transport_mode}",
                datapoint_name=f"GHG intensity - {entry.transport_mode}",
                value=round(entry.intensity_kg_co2e_per_ton_km, 4),
                unit="kgCO2e/tkm",
                financial_year=financial_year
            ))
        
        # E1-5: Energy consumption (estimated from emissions)
        # Assuming diesel at 0.85 kg/L, 43 MJ/kg, 35% efficiency
        estimated_energy_mwh = total_emissions * 0.85 * 43 * 0.35 / 3.6
        datapoints.append(ESRSDataPoint(
            standard=ESRSStandard.E1_CLIMATE,
            disclosure_requirement="E1-5",
            datapoint_id="E1-5_TotalEnergy",
            datapoint_name="Total energy consumption",
            value=round(estimated_energy_mwh, 2),
            unit="MWh",
            financial_year=financial_year
        ))
        
        return datapoints
    
    def export_xbrl(self, report: CSRDReport, filename: Optional[str] = None) -> str:
        """
        Export report to XBRL format.
        
        XBRL (eXtensible Business Reporting Language) is the
        standard format for CSRD digital reporting.
        """
        # Create XBRL root
        root = ET.Element(
            "xbrl",
            attrib={
                "xmlns": "http://www.xbrl.org/2003/instance",
                "xmlns:esrs": "http://xbrl.efrag.org/esrs/2023"
            }
        )
        
        # Context
        context = ET.SubElement(root, "context", id="CurrentYear")
        entity = ET.SubElement(context, "entity")
        ET.SubElement(entity, "identifier", scheme="http://standards.iso.org/iso/17442").text = report.lei_code or report.entity_id
        
        period = ET.SubElement(context, "period")
        ET.SubElement(period, "startDate").text = report.reporting_period_start.isoformat()
        ET.SubElement(period, "endDate").text = report.reporting_period_end.isoformat()
        
        # Units
        unit_tco2e = ET.SubElement(root, "unit", id="tCO2e")
        ET.SubElement(unit_tco2e, "measure").text = "tCO2e"
        
        # GHG emissions
        for inv in report.ghg_inventories:
            fact = ET.SubElement(
                root,
                f"esrs:Scope{inv.scope.value[-1]}GHGEmissions",
                contextRef="CurrentYear",
                unitRef="tCO2e",
                decimals="2"
            )
            fact.text = str(round(inv.emissions_tons_co2e, 2))
        
        # Transport emissions breakdown
        for entry in report.transport_emissions:
            fact = ET.SubElement(
                root,
                f"esrs:TransportGHGEmissions{entry.transport_mode.title()}",
                contextRef="CurrentYear",
                unitRef="tCO2e",
                decimals="2"
            )
            fact.text = str(round(entry.total_emissions_tons_co2e, 2))
        
        # Convert to string
        xml_str = ET.tostring(root, encoding='unicode')
        
        # Pretty print
        import xml.dom.minidom
        dom = xml.dom.minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ")
        
        if filename:
            with open(filename, 'w') as f:
                f.write(pretty_xml)
        
        return pretty_xml
    
    def export_json(self, report: CSRDReport, filename: Optional[str] = None) -> str:
        """Export report to JSON format."""
        data = report.to_dict()
        json_str = json.dumps(data, indent=2)
        
        if filename:
            with open(filename, 'w') as f:
                f.write(json_str)
        
        return json_str
    
    def generate_assurance_pack(
        self,
        report: CSRDReport,
        supporting_evidence: List[str]
    ) -> Dict[str, Any]:
        """
        Generate assurance package for auditors.
        
        Includes:
        - Methodology documentation
        - Calculation logs
        - Supporting evidence references
        - Data quality assessments
        """
        return {
            'report_summary': {
                'entity': report.entity_name,
                'period': f"{report.reporting_period_start} to {report.reporting_period_end}",
                'total_scope3_cat4_tons': sum(
                    inv.emissions_tons_co2e
                    for inv in report.ghg_inventories
                    if inv.category == GHGCategory.CAT_4_UPSTREAM_TRANSPORT
                ),
                'assurance_level': report.assurance_level
            },
            'methodology': {
                'standard': 'GHG Protocol Corporate Value Chain (Scope 3)',
                'calculation_framework': 'GLEC Framework v3.0',
                'emission_factors': 'ISO 14083:2023 default factors',
                'transport_modes_covered': [
                    entry.transport_mode for entry in report.transport_emissions
                ]
            },
            'data_quality': {
                'primary_data_pct': 85,  # Assuming 85% primary data
                'secondary_data_pct': 15,
                'uncertainty_assessment': 'Medium - based on GLEC uncertainty ranges'
            },
            'supporting_evidence': supporting_evidence,
            'calculation_log': self.calculator.calculation_log,
            'audit_trail': self.audit_log
        }
    
    def compare_with_targets(
        self,
        report: CSRDReport,
        targets: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare emissions with SBTi targets."""
        total_emissions = sum(
            inv.emissions_tons_co2e for inv in report.ghg_inventories
        )
        
        baseline_year = targets.get('baseline_year')
        baseline_emissions = targets.get('baseline_emissions_tons')
        target_year = targets.get('target_year')
        reduction_pct = targets.get('reduction_percentage', 0)
        
        if baseline_emissions:
            current_reduction = (
                (baseline_emissions - total_emissions) / baseline_emissions * 100
            )
        else:
            current_reduction = 0
        
        # Calculate required trajectory
        years_elapsed = report.reporting_period_end.year - baseline_year
        total_years = target_year - baseline_year
        expected_reduction = reduction_pct * (years_elapsed / total_years)
        
        return {
            'current_emissions_tons': round(total_emissions, 2),
            'baseline_emissions_tons': baseline_emissions,
            'current_reduction_pct': round(current_reduction, 2),
            'target_reduction_pct': reduction_pct,
            'expected_reduction_pct': round(expected_reduction, 2),
            'trajectory_status': 'On track' if current_reduction >= expected_reduction * 0.9 else 'Behind',
            'gap_to_target_tons': round(
                baseline_emissions * (1 - reduction_pct / 100) - total_emissions, 2
            ) if baseline_emissions else None
        }
