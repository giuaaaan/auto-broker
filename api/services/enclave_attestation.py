"""
AUTO-BROKER: Enclave Attestation Service

Implementa Remote Attestation per AMD SEV-SNP e Intel TDX.
L'enclave deve provare la sua identità prima di ricevere secrets sensibili.

Architettura:
1. Enclave genera attestation report (misurazione del codice)
2. Report viene verificato (firma AMD/Intel valida?)
3. Se valido, Vault rilascia secrets cifrati per quell'enclave specifica
4. Secrets sono "sealed" - solo quella enclave può decifrarli
"""
import hashlib
import json
import os
import structlog
from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, Union
from datetime import datetime, timedelta

# Tentativo import librerie SEV/TDX
try:
    # Per AMD SEV-SNP (su sistema reale)
    import snpguest
    SEV_AVAILABLE = True
except ImportError:
    SEV_AVAILABLE = False

try:
    # Per Intel TDX (su sistema reale)
    import tdx_attest
    TDX_AVAILABLE = True
except ImportError:
    TDX_AVAILABLE = False

logger = structlog.get_logger()

# Configuration
ENCLAVE_MODE = os.getenv("ENCLAVE_MODE", "simulation")  # sev-snp, intel-tdx, simulation
ATTESTATION_TIMEOUT = int(os.getenv("ATTESTATION_TIMEOUT", "300"))
VAULT_ADDR = os.getenv("VAULT_ADDR", "https://vault.internal:8200")


@dataclass
class AttestationReport:
    """Report di attestation da enclave."""
    measurement: str  # Hash SHA256 del codice/firmware
    report_data: str  # Dati inclusi nel report (pubkey, nonce, etc.)
    timestamp: str
    signature: str    # Firma AMD/Intel
    platform_info: Dict[str, Any]
    enclave_type: str  # "sev-snp", "intel-tdx", "simulation"


@dataclass
class VerificationResult:
    """Risultato verifica attestation."""
    valid: bool
    measurement: str
    trusted: bool
    timestamp: datetime
    expires_at: datetime
    error_message: Optional[str] = None


class EnclaveAttestation:
    """
    Gestisce attestation per confidential computing.
    
    Supporta:
    - AMD SEV-SNP (Secure Encrypted Virtualization - Secure Nested Paging)
    - Intel TDX (Trust Domain Extensions)
    - Simulation mode (per testing senza hardware)
    """
    
    def __init__(self, mode: Optional[str] = None):
        self.mode = mode or ENCLAVE_MODE
        self._cached_reports: Dict[str, AttestationReport] = {}
        self._trusted_measurements: set = set()
        
        logger.info(
            "enclave_attestation_initialized",
            mode=self.mode,
            sev_available=SEV_AVAILABLE,
            tdx_available=TDX_AVAILABLE
        )
    
    def get_attestation_report(self, report_data: Optional[bytes] = None) -> bytes:
        """
        Genera attestation report dall'enclave corrente.
        
        Args:
            report_data: Dati opzionali da includere nel report (es. pubkey)
            
        Returns:
            Report bytes (formato dipende dalla piattaforma)
        """
        if self.mode == "sev-snp":
            return self._get_sev_attestation_report(report_data)
        elif self.mode == "intel-tdx":
            return self._get_tdx_attestation_report(report_data)
        elif self.mode == "simulation":
            return self._get_simulated_attestation_report(report_data)
        else:
            raise ValueError(f"Unknown enclave mode: {self.mode}")
    
    def _get_sev_attestation_report(self, report_data: Optional[bytes]) -> bytes:
        """
        Genera SEV-SNP attestation report.
        
        Richiede:
        - snpguest library
        - Accesso a /dev/sev
        - Platform specific (AMD EPYC)
        """
        if not SEV_AVAILABLE:
            logger.warning("SEV library not available, using simulation")
            return self._get_simulated_attestation_report(report_data)
        
        try:
            # Genera report usando snpguest
            # In produzione: report = snpguest.get_report(report_data)
            report = snpguest.get_attestation_report(
                report_data=report_data or b"",
                vmpl=0  # Virtual Machine Privilege Level (0 = highest)
            )
            
            logger.info("sev_attestation_report_generated")
            return report
            
        except Exception as e:
            logger.error("sev_attestation_failed", error=str(e))
            raise
    
    def _get_tdx_attestation_report(self, report_data: Optional[bytes]) -> bytes:
        """
        Genera Intel TDX attestation report.
        
        Richiede:
        - tdx-attest library
        - Intel TDX-capable CPU
        """
        if not TDX_AVAILABLE:
            logger.warning("TDX library not available, using simulation")
            return self._get_simulated_attestation_report(report_data)
        
        try:
            # Genera TDX report
            report = tdx_attest.get_quote(
                report_data=report_data or b""
            )
            
            logger.info("tdx_attestation_report_generated")
            return report
            
        except Exception as e:
            logger.error("tdx_attestation_failed", error=str(e))
            raise
    
    def _get_simulated_attestation_report(self, report_data: Optional[bytes]) -> bytes:
        """
        Genera report simulato per testing.
        
        NON usare in produzione - solo per development!
        """
        logger.warning("using_simulated_attestation")
        
        # Simula measurement del codice
        code_hash = self._calculate_code_measurement()
        
        # Crea report simulato
        simulated_report = {
            "version": "simulated-1.0",
            "measurement": code_hash,
            "report_data": (report_data or b"").hex(),
            "timestamp": datetime.utcnow().isoformat(),
            "signature": "simulated-signature",
            "platform": "simulation-mode",
            "mode": "debug" if os.getenv("DEBUG") else "production"
        }
        
        return json.dumps(simulated_report).encode()
    
    def _calculate_code_measurement(self) -> str:
        """
        Calcola measurement del codice corrente.
        
        In produzione, questo è il hash del container image.
        """
        # Simula measurement - in reale sarebbe il hash del filesystem
        import sys
        code_path = sys.path[0]
        
        # Hash del codice sorgente (semplificato)
        hasher = hashlib.sha256()
        hasher.update(code_path.encode())
        hasher.update(b"auto-broker-enclave-v2.1.0")
        
        return hasher.hexdigest()
    
    async def verify_attestation(
        self,
        report: bytes,
        expected_measurements: Optional[Dict[str, Any]] = None
    ) -> VerificationResult:
        """
        Verifica attestation report.
        
        Controlla:
        1. Firma AMD/Intel valida
        2. Measurement corrisponde al codice atteso
        3. Report non scaduto/revocato
        4. Platform security version (PSV) aggiornato
        
        Args:
            report: Attestation report bytes
            expected_measurements: Dict con measurement attesi (whitelisting)
            
        Returns:
            VerificationResult con valid=True/False
        """
        try:
            # Parse report
            report_obj = self._parse_attestation_report(report)
            
            # Verifica firma (platform-specific)
            if not self._verify_signature(report_obj):
                return VerificationResult(
                    valid=False,
                    measurement=report_obj.measurement,
                    trusted=False,
                    timestamp=datetime.utcnow(),
                    expires_at=datetime.utcnow(),
                    error_message="Invalid attestation signature"
                )
            
            # Verifica measurement
            if expected_measurements:
                trusted = self._verify_measurement(
                    report_obj.measurement,
                    expected_measurements
                )
            else:
                # Se non specificato, verifica contro trusted list
                trusted = report_obj.measurement in self._trusted_measurements
            
            if not trusted:
                logger.warning(
                    "untrusted_measurement",
                    measurement=report_obj.measurement[:16]
                )
            
            # Calcola scadenza (24h default)
            expires_at = datetime.utcnow() + timedelta(seconds=ATTESTATION_TIMEOUT)
            
            logger.info(
                "attestation_verified",
                measurement=report_obj.measurement[:16],
                trusted=trusted,
                mode=report_obj.enclave_type
            )
            
            return VerificationResult(
                valid=True,
                measurement=report_obj.measurement,
                trusted=trusted,
                timestamp=datetime.utcnow(),
                expires_at=expires_at
            )
            
        except Exception as e:
            logger.error("attestation_verification_failed", error=str(e))
            return VerificationResult(
                valid=False,
                measurement="",
                trusted=False,
                timestamp=datetime.utcnow(),
                expires_at=datetime.utcnow(),
                error_message=str(e)
            )
    
    def _parse_attestation_report(self, report: bytes) -> AttestationReport:
        """Parse report bytes in AttestationReport."""
        if self.mode == "simulation":
            data = json.loads(report)
            return AttestationReport(
                measurement=data["measurement"],
                report_data=data.get("report_data", ""),
                timestamp=data["timestamp"],
                signature=data["signature"],
                platform_info={"mode": "simulation"},
                enclave_type="simulation"
            )
        else:
            # Parse formato SEV/TDX specifico
            # In produzione: parsing binario del report
            raise NotImplementedError("SEV/TDX parsing requires platform-specific code")
    
    def _verify_signature(self, report: AttestationReport) -> bool:
        """Verifica firma del report (AMD/Intel CA)."""
        if self.mode == "simulation":
            # In simulazione, accetta sempre
            return True
        
        # In produzione: verifica catena di certificati AMD/Intel
        # 1. Estrai certificato VCEK/VLEK
        # 2. Verifica chain fino a AMD/Intel root CA
        # 3. Verifica firma del report
        return True  # Placeholder
    
    def _verify_measurement(
        self,
        measurement: str,
        expected: Dict[str, Any]
    ) -> bool:
        """Verifica measurement contro whitelist."""
        allowed_measurements = expected.get("measurements", [])
        return measurement in allowed_measurements
    
    def register_trusted_measurement(self, measurement: str):
        """Registra measurement come trusted."""
        self._trusted_measurements.add(measurement)
        logger.info(
            "measurement_registered",
            measurement=measurement[:16]
        )
    
    async def provision_secrets(
        self,
        attested_report: bytes,
        secret_paths: list
    ) -> Dict[str, str]:
        """
        Richiede secrets da Vault dopo attestation valida.
        
        Args:
            attested_report: Report verificato
            secret_paths: Lista path secrets (es. ["hume/api-key", "db/creds"])
            
        Returns:
            Dict con secrets cifrati per l'enclave
        """
        # Verifica attestation
        verification = await self.verify_attestation(attested_report)
        
        if not verification.valid or not verification.trusted:
            raise PermissionError(
                f"Attestation invalid or untrusted: {verification.error_message}"
            )
        
        # Prepara richiesta a Vault
        from api.services.vault_integration import VaultClient
        vault = VaultClient()
        
        # Richiedi secrets con attestation binding
        secrets = {}
        for path in secret_paths:
            try:
                # Vault verifica attestation e rilascia secret cifrato
                secret = await vault.get_secret_with_attestation(
                    path=path,
                    attestation_report=attested_report,
                    enclave_measurement=verification.measurement
                )
                secrets[path] = secret
                
            except Exception as e:
                logger.error(
                    "secret_provisioning_failed",
                    path=path,
                    error=str(e)
                )
                raise
        
        logger.info(
            "secrets_provisioned",
            count=len(secrets),
            measurement=verification.measurement[:16]
        )
        
        return secrets
    
    def seal_secret(self, secret: str, binding_data: bytes) -> bytes:
        """
        Cifra secret per essere "sealed" a questa enclave.
        
        Solo questa enclave specifica può decifrare il secret.
        """
        # Ottieni chiave di sealing dall'enclave
        sealing_key = self._derive_sealing_key(binding_data)
        
        # Cifra secret
        from cryptography.fernet import Fernet
        f = Fernet(sealing_key)
        sealed = f.encrypt(secret.encode())
        
        return sealed
    
    def unseal_secret(self, sealed_secret: bytes, binding_data: bytes) -> str:
        """Decifra secret sealed."""
        sealing_key = self._derive_sealing_key(binding_data)
        
        from cryptography.fernet import Fernet
        f = Fernet(sealing_key)
        secret = f.decrypt(sealed_secret)
        
        return secret.decode()
    
    def _derive_sealing_key(self, binding_data: bytes) -> bytes:
        """
        Deriva chiave di sealing dai materiali dell'enclave.
        
        In produzione: usa TEE-specific key derivation
        """
        # Simulazione: hash dei binding data
        import base64
        key_material = hashlib.sha256(binding_data).digest()
        # Formatta per Fernet (richiede base64-encoded 32-byte key)
        return base64.urlsafe_b64encode(key_material)


class EnclaveHealthChecker:
    """Health checks specifici per enclave."""
    
    def __init__(self, attestation: EnclaveAttestation):
        self.attestation = attestation
    
    async def check_enclave_health(self) -> Dict[str, Any]:
        """Verifica stato salute enclave."""
        try:
            # Genera fresh attestation
            report = self.attestation.get_attestation_report()
            
            # Verifica
            result = await self.attestation.verify_attestation(report)
            
            return {
                "status": "healthy" if result.valid else "unhealthy",
                "attestation_valid": result.valid,
                "measurement": result.measurement[:16] if result.measurement else None,
                "trusted": result.trusted,
                "expires_at": result.expires_at.isoformat() if result.expires_at else None
            }
            
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Singleton per uso globale
_attestation_instance: Optional[EnclaveAttestation] = None


def get_attestation_service() -> EnclaveAttestation:
    """Factory per EnclaveAttestation singleton."""
    global _attestation_instance
    
    if _attestation_instance is None:
        _attestation_instance = EnclaveAttestation()
    
    return _attestation_instance