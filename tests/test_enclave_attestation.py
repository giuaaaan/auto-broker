"""
Tests per Enclave Attestation Service.

Nota: Questi test usano simulation mode per compatibilità
con ambienti senza hardware SEV-SNP/TDX.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock

from api.services.enclave_attestation import (
    EnclaveAttestation,
    EnclaveHealthChecker,
    AttestationReport,
    VerificationResult,
    get_attestation_service
)


class TestEnclaveAttestation:
    """Test suite per attestation service."""
    
    @pytest_asyncio.fixture
    async def attestation(self):
        """Fixture per attestation service."""
        service = EnclaveAttestation(mode="simulation")
        yield service
    
    def test_initialization(self):
        """Test inizializzazione service."""
        attestation = EnclaveAttestation(mode="simulation")
        
        assert attestation.mode == "simulation"
        assert len(attestation._trusted_measurements) == 0
    
    def test_get_simulated_attestation_report(self, attestation):
        """Test generazione report simulato."""
        import json
        
        report = attestation.get_attestation_report()
        
        # Parse JSON report
        data = json.loads(report)
        
        assert data["version"] == "simulated-1.0"
        assert "measurement" in data
        assert "timestamp" in data
        assert "signature" in data
        assert data["platform"] == "simulation-mode"
    
    def test_attestation_with_report_data(self, attestation):
        """Test attestation con custom report data."""
        import json
        
        custom_data = b"public-key-12345"
        report = attestation.get_attestation_report(report_data=custom_data)
        
        data = json.loads(report)
        assert data["report_data"] == custom_data.hex()
    
    @pytest.mark.asyncio
    async def test_verify_valid_attestation(self, attestation):
        """Test verifica attestation valida."""
        report = attestation.get_attestation_report()
        
        # Verifica senza expected measurements
        result = await attestation.verify_attestation(report)
        
        assert result.valid is True
        assert result.measurement != ""
        assert result.error_message is None
    
    @pytest.mark.asyncio
    async def test_verify_trusted_measurement(self, attestation):
        """Test verifica con trusted measurement."""
        report = attestation.get_attestation_report()
        
        # Parse per ottenere measurement
        import json
        data = json.loads(report)
        measurement = data["measurement"]
        
        # Registra come trusted
        attestation.register_trusted_measurement(measurement)
        
        # Verifica
        result = await attestation.verify_attestation(report)
        
        assert result.valid is True
        assert result.trusted is True
    
    @pytest.mark.asyncio
    async def test_verify_untrusted_measurement(self, attestation):
        """Test verifica con measurement non trusted."""
        report = attestation.get_attestation_report()
        
        # Non registrare measurement
        result = await attestation.verify_attestation(report)
        
        assert result.valid is True
        assert result.trusted is False  # Non in trusted list
    
    @pytest.mark.asyncio
    async def test_verify_with_expected_measurements(self, attestation):
        """Test verifica contro lista attesa."""
        report = attestation.get_attestation_report()
        
        import json
        data = json.loads(report)
        measurement = data["measurement"]
        
        # Verifica con expected che include il measurement
        expected = {"measurements": [measurement]}
        result = await attestation.verify_attestation(report, expected)
        
        assert result.valid is True
        assert result.trusted is True
    
    @pytest.mark.asyncio
    async def test_verify_with_wrong_expected(self, attestation):
        """Test verifica con expected sbagliato."""
        report = attestation.get_attestation_report()
        
        # Verifica con lista che NON include il measurement
        expected = {"measurements": ["wrong-measurement-123"]}
        result = await attestation.verify_attestation(report, expected)
        
        assert result.valid is True
        assert result.trusted is False
    
    def test_calculate_code_measurement(self, attestation):
        """Test calcolo measurement."""
        measurement = attestation._calculate_code_measurement()
        
        assert len(measurement) == 64  # SHA256 hex
        assert all(c in "0123456789abcdef" for c in measurement)
    
    def test_measurement_consistency(self, attestation):
        """Test che measurement sia consistente."""
        m1 = attestation._calculate_code_measurement()
        m2 = attestation._calculate_code_measurement()
        
        assert m1 == m2
    
    def test_register_trusted_measurement(self, attestation):
        """Test registrazione trusted measurement."""
        measurement = "test-measurement-123"
        
        attestation.register_trusted_measurement(measurement)
        
        assert measurement in attestation._trusted_measurements
    
    @pytest.mark.asyncio
    async def test_provision_secrets_without_attestation(self, attestation):
        """Test provisioning senza attestation valida fallisce."""
        # Crea report invalido
        invalid_report = b"invalid-report"
        
        with pytest.raises(PermissionError):
            await attestation.provision_secrets(
                invalid_report,
                ["hume/api-key"]
            )
    
    def test_seal_and_unseal_secret(self, attestation):
        """Test sealing e unsealing secret."""
        secret = "my-super-secret-api-key"
        binding_data = b"enclave-binding-123"
        
        # Seal
        sealed = attestation.seal_secret(secret, binding_data)
        
        # Unseal
        unsealed = attestation.unseal_secret(sealed, binding_data)
        
        assert unsealed == secret
        assert sealed != secret.encode()
    
    def test_unseal_with_wrong_binding(self, attestation):
        """Test unseal con binding sbagliato fallisce."""
        import pytest
        from cryptography.fernet import InvalidToken
        
        secret = "my-secret"
        binding_data = b"correct-binding"
        wrong_binding = b"wrong-binding"
        
        sealed = attestation.seal_secret(secret, binding_data)
        
        # Dovrebbe fallire con binding sbagliato
        with pytest.raises(InvalidToken):
            attestation.unseal_secret(sealed, wrong_binding)
    
    def test_parse_simulation_report(self, attestation):
        """Test parsing report simulato."""
        import json
        
        report_data = {
            "version": "simulated-1.0",
            "measurement": "abc123",
            "report_data": "data123",
            "timestamp": "2024-01-01T00:00:00",
            "signature": "sig123"
        }
        report = json.dumps(report_data).encode()
        
        parsed = attestation._parse_attestation_report(report)
        
        assert isinstance(parsed, AttestationReport)
        assert parsed.measurement == "abc123"
        assert parsed.enclave_type == "simulation"


class TestEnclaveHealthChecker:
    """Test per health checker."""
    
    @pytest_asyncio.fixture
    async def checker(self):
        """Fixture per health checker."""
        attestation = EnclaveAttestation(mode="simulation")
        return EnclaveHealthChecker(attestation)
    
    @pytest.mark.asyncio
    async def test_health_check(self, checker):
        """Test health check enclave."""
        health = await checker.check_enclave_health()
        
        assert "status" in health
        assert "attestation_valid" in health
        assert "measurement" in health
        assert "trusted" in health
    
    @pytest.mark.asyncio
    async def test_healthy_enclave(self, checker):
        """Test stato healthy."""
        # Registra measurement per trusted
        report = checker.attestation.get_attestation_report()
        import json
        data = json.loads(report)
        checker.attestation.register_trusted_measurement(data["measurement"])
        
        health = await checker.check_enclave_health()
        
        assert health["status"] == "healthy"
        assert health["attestation_valid"] is True
        assert health["trusted"] is True


class TestGetAttestationService:
    """Test factory singleton."""
    
    def test_singleton_pattern(self):
        """Test che ritorna stessa istanza."""
        service1 = get_attestation_service()
        service2 = get_attestation_service()
        
        assert service1 is service2
    
    def test_singleton_initialized(self):
        """Test che singleton sia inizializzato."""
        service = get_attestation_service()
        
        assert isinstance(service, EnclaveAttestation)


class TestEnclaveModes:
    """Test diversi modi enclave."""
    
    def test_simulation_mode(self):
        """Test simulation mode."""
        attestation = EnclaveAttestation(mode="simulation")
        assert attestation.mode == "simulation"
        
        report = attestation.get_attestation_report()
        assert report is not None
    
    @pytest.mark.skip(reason="Richiede libreria snpguest")
    def test_sev_snp_mode(self):
        """Test SEV-SNP mode (richiede hardware)."""
        # Questo test è skip di default
        attestation = EnclaveAttestation(mode="sev-snp")
        
        # Se libreria non disponibile, fallback a simulation
        report = attestation.get_attestation_report()
        assert report is not None
    
    @pytest.mark.skip(reason="Richiede libreria tdx-attest")
    def test_intel_tdx_mode(self):
        """Test Intel TDX mode (richiede hardware)."""
        attestation = EnclaveAttestation(mode="intel-tdx")
        
        # Se libreria non disponibile, fallback a simulation
        report = attestation.get_attestation_report()
        assert report is not None


class TestVerificationResult:
    """Test VerificationResult dataclass."""
    
    def test_valid_result(self):
        """Test risultato valido."""
        from datetime import datetime
        
        result = VerificationResult(
            valid=True,
            measurement="abc123",
            trusted=True,
            timestamp=datetime.utcnow(),
            expires_at=datetime.utcnow()
        )
        
        assert result.valid is True
        assert result.error_message is None
    
    def test_invalid_result(self):
        """Test risultato invalido."""
        from datetime import datetime
        
        result = VerificationResult(
            valid=False,
            measurement="",
            trusted=False,
            timestamp=datetime.utcnow(),
            expires_at=datetime.utcnow(),
            error_message="Invalid signature"
        )
        
        assert result.valid is False
        assert result.error_message == "Invalid signature"


class TestAttestationReport:
    """Test AttestationReport dataclass."""
    
    def test_report_creation(self):
        """Test creazione report."""
        report = AttestationReport(
            measurement="sha256:abc123",
            report_data="public-key-data",
            timestamp="2024-01-01T00:00:00",
            signature="signature-123",
            platform_info={"cpu": "AMD-EPYC", "version": "1.0"},
            enclave_type="sev-snp"
        )
        
        assert report.measurement == "sha256:abc123"
        assert report.enclave_type == "sev-snp"
        assert report.platform_info["cpu"] == "AMD-EPYC"


@pytest.mark.integration
class TestAttestationIntegration:
    """Test di integrazione (richiedono Vault mock)."""
    
    @pytest.mark.asyncio
    async def test_full_attestation_flow(self):
        """Test flusso completo attestation."""
        from unittest.mock import AsyncMock
        
        attestation = EnclaveAttestation(mode="simulation")
        
        # 1. Genera report
        report = attestation.get_attestation_report()
        assert report is not None
        
        # 2. Verifica
        import json
        data = json.loads(report)
        attestation.register_trusted_measurement(data["measurement"])
        
        result = await attestation.verify_attestation(report)
        assert result.valid is True
        assert result.trusted is True
        
        # 3. Mock Vault client per provisioning
        with patch("api.services.vault_integration.VaultClient") as mock_vault:
            mock_instance = MagicMock()
            mock_instance.get_secrets_with_attestation = AsyncMock(
                return_value={"hume/api-key": "test-key-123"}
            )
            mock_vault.return_value = mock_instance
            
            # Provisioning
            secrets = await attestation.provision_secrets(
                report,
                ["hume/api-key"]
            )
            
            assert "hume/api-key" in secrets
            mock_instance.get_secrets_with_attestation.assert_called_once()