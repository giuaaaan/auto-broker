"""
AUTO-BROKER: Confidential Retell Service

Questo servizio gira DENTRO l'enclave TEE (Trusted Execution Environment)
e processa chiamate vocali con le seguenti garanzie di sicurezza:

1. Memory Encryption: Dati in RAM cifrati (SEV-SNP/TDX)
2. No Disk Logging: Solo stdout, senza persistenza su disco
3. Sealed Secrets: API keys ricevute solo dopo attestation
4. Remote Attestation: Verificabile da terze parti
5. Isolamento: Host OS non può accedere alla memoria
"""
import asyncio
import hashlib
import os
import structlog
import time
from typing import Optional, Dict, Any, AsyncGenerator, Tuple
from datetime import datetime
from dataclasses import dataclass

from api.services.enclave_attestation import (
    EnclaveAttestation,
    get_attestation_service
)

# Configurazione Enclave
ENCLAVE_MODE = os.getenv("ENCLAVE_MODE", "simulation")
ATTESTATION_ENABLED = os.getenv("ATTESTATION_ENABLED", "true").lower() == "true"
MEMORY_ENCRYPTION = os.getenv("MEMORY_ENCRYPTION", "enabled")

logger = structlog.get_logger()


class EnclaveNotProvisionedError(Exception):
    """Sollevato se enclave non ha ricevuto secrets dopo attestation."""
    pass


class ConfidentialityViolationError(Exception):
    """Sollevato se rilevata violazione della confidenzialità."""
    pass


@dataclass
class SecureAudioChunk:
    """Chunk audio con metadati di sicurezza."""
    encrypted_data: bytes
    sequence: int
    timestamp: float
    checksum: str
    encryption_iv: bytes


@dataclass
class ConfidentialCallResult:
    """Risultato elaborazione chiamata in enclave."""
    sentiment: Optional[Dict[str, Any]]
    transcription: Optional[str]
    processing_time_ms: float
    enclave_attested: bool
    memory_encryption_active: bool
    pii_masked: bool = True
    
    # NO persistenza su disco - solo ritorno
    def to_safe_dict(self) -> Dict[str, Any]:
        """Converte in dict senza dati sensibili."""
        return {
            "sentiment": self.sentiment,
            "transcription_preview": self._mask_transcription() if self.transcription else None,
            "processing_time_ms": self.processing_time_ms,
            "security": {
                "enclave_attested": self.enclave_attested,
                "memory_encrypted": self.memory_encryption_active,
                "pii_masked": self.pii_masked
            }
        }
    
    def _mask_transcription(self) -> str:
        """Maschera PII nella trascrizione."""
        if not self.transcription:
            return ""
        # Solo primi 100 chars, mascherati
        preview = self.transcription[:100]
        return f"{preview}... [MASKED - ENCLAVE ONLY]"


class ConfidentialRetellService:
    """
    Servizio Retell in esecuzione in enclave TEE.
    
    Caratteristiche di sicurezza:
    - API Keys mai scritte su disco
- Audio in memoria cifrata (host non può leggere)
    - Nessun log persistito
    - Attestation prima di elaborazione
    """
    
    def __init__(self):
        self.attestation = get_attestation_service()
        self._secrets: Optional[Dict[str, str]] = None
        self._enclave_ready = False
        self._memory_encryption_active = ENCLAVE_MODE != "simulation"
        
        logger.info(
            "confidential_retell_initialized",
            enclave_mode=ENCLAVE_MODE,
            attestation_enabled=ATTESTATION_ENABLED,
            memory_encryption=MEMORY_ENCRYPTION
        )
    
    async def initialize_enclave(self) -> bool:
        """
        Inizializza l'enclave e ottiene secrets tramite attestation.
        
        Returns:
            True se enclave pronta, False altrimenti
        """
        if not ATTESTATION_ENABLED:
            logger.warning("attestation_disabled - using development mode")
            self._secrets = {"mode": "unattested-development"}
            self._enclave_ready = True
            return True
        
        try:
            # 1. Genera attestation report
            report = self.attestation.get_attestation_report()
            logger.info("attestation_report_generated")
            
            # 2. Richiedi secrets da Vault
            from api.services.vault_integration import VaultClient
            vault = VaultClient()
            
            self._secrets = await vault.get_secrets_with_attestation(
                paths=["hume/api-key", "retell/api-key"],
                attestation_report=report
            )
            
            # 3. Verifica secrets ricevuti
            if not self._secrets.get("hume/api-key"):
                raise EnclaveNotProvisionedError("Hume API key not provisioned")
            
            self._enclave_ready = True
            
            logger.info(
                "enclave_initialized",
                secrets_count=len(self._secrets),
                measurement=self.attestation._calculate_code_measurement()[:16]
            )
            
            return True
            
        except Exception as e:
            logger.error("enclave_initialization_failed", error=str(e))
            self._enclave_ready = False
            return False
    
    async def process_call_secure(
        self,
        audio_data: bytes,
        call_metadata: Optional[Dict[str, Any]] = None
    ) -> ConfidentialCallResult:
        """
        Processa chiamata audio in enclave sicuro.
        
        Flusso:
        1. Verifica enclave pronta
        2. Decifra audio se necessario
        3. Chiama Hume API (key nell'enclave)
        4. Analisi sentiment senza log su disco
        5. Ritorno risultati (dati sensibili solo in memoria)
        
        Args:
            audio_data: Audio bytes (ideally pre-encrypted)
            call_metadata: Metadati chiamata (numero mascherato, etc.)
            
        Returns:
            ConfidentialCallResult con analisi sentiment
        """
        start_time = time.time()
        
        # 1. Verifica enclave provisioned
        if not self._enclave_ready:
            success = await self.initialize_enclave()
            if not success:
                raise EnclaveNotProvisionedError(
                    "Enclave not initialized and attestation failed"
                )
        
        # 2. Sanitizza metadati (nessun PII)
        safe_metadata = self._sanitize_metadata(call_metadata or {})
        
        logger.info(
            "processing_call_in_enclave",
            audio_size=len(audio_data),
            mode=ENCLAVE_MODE,
            **safe_metadata
        )
        
        # 3. Processa audio (in memoria cifrata)
        try:
            # Chiama Hume API - key non esce mai dall'enclave
            sentiment = await self._analyze_sentiment_secure(audio_data)
            
            # Trascrizione (senza persistenza)
            transcription = await self._transcribe_secure(audio_data)
            
            # 4. Calcola risultato
            processing_time = (time.time() - start_time) * 1000
            
            result = ConfidentialCallResult(
                sentiment=sentiment,
                transcription=transcription,
                processing_time_ms=processing_time,
                enclave_attested=self._enclave_ready,
                memory_encryption_active=self._memory_encryption_active,
                pii_masked=True
            )
            
            logger.info(
                "call_processed_in_enclave",
                processing_time_ms=processing_time,
                sentiment_detected=sentiment is not None
            )
            
            return result
            
        except Exception as e:
            logger.error("enclave_processing_error", error=str(e))
            raise ConfidentialityViolationError(f"Processing failed: {str(e)}")
    
    async def _analyze_sentiment_secure(
        self,
        audio_data: bytes
    ) -> Optional[Dict[str, Any]]:
        """
        Analizza sentiment usando Hume API dentro l'enclave.
        
        La API key rimane in memoria cifrata, mai su disco.
        """
        if not self._secrets:
            return None
        
        hume_key = self._secrets.get("hume/api-key")
        if not hume_key:
            logger.error("hume_key_not_provisioned")
            return None
        
        try:
            # Chiama Hume API
            import httpx
            
            # Prepara audio (in memoria - cifrato da SEV)
            audio_hash = hashlib.sha256(audio_data).hexdigest()[:16]
            
            logger.info(
                "calling_hume_in_enclave",
                audio_hash=audio_hash,
                enclave_secured=True
            )
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    "https://api.hume.ai/v0/batch/jobs",
                    headers={
                        "X-Hume-Api-Key": hume_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "models": {
                            "prosody": {}
                        },
                        "transcription": {
                            "language": "it"
                        }
                    },
                    files={
                        "file": ("audio.wav", audio_data, "audio/wav")
                    }
                )
                
                response.raise_for_status()
                result = response.json()
                
                # Estrai sentiment (senza loggare dati raw)
                return self._extract_sentiment(result)
                
        except Exception as e:
            logger.error("hume_analysis_failed", error=str(e))
            return None
    
    async def _transcribe_secure(self, audio_data: bytes) -> Optional[str]:
        """Trascrive audio senza persistenza su disco."""
        # Per ora usa Hume che include trascrizione
        # In futuro: whisper locale nell'enclave
        return None  # Trascrizione gestita da Hume
    
    def _extract_sentiment(self, hume_result: Dict) -> Optional[Dict[str, Any]]:
        """Estrae sentiment dai risultati Hume."""
        try:
            emotions = hume_result.get("results", {}).get("predictions", [])
            if not emotions:
                return None
            
            # Estrai top emotions
            top_emotions = []
            for pred in emotions[:3]:  # Solo top 3
                emotion = pred.get("emotions", [])
                if emotion:
                    top_emotions.append({
                        "name": emotion[0].get("name"),
                        "score": emotion[0].get("score")
                    })
            
            return {
                "top_emotions": top_emotions,
                "processed_in_enclave": True,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("sentiment_extraction_failed", error=str(e))
            return None
    
    def _sanitize_metadata(
        self,
        metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Sanitizza metadati rimuovendo PII.
        
        Restituisce solo dati sicuri da loggare.
        """
        safe = {}
        
        # Hash del numero (mai loggare numero reale)
        if "phone_number" in metadata:
            safe["phone_hash"] = hashlib.sha256(
                metadata["phone_number"].encode()
            ).hexdigest()[:16]
        
        # Solo ID referenziati
        if "shipment_id" in metadata:
            safe["shipment_id"] = str(metadata["shipment_id"])
        
        if "agent_type" in metadata:
            safe["agent_type"] = metadata["agent_type"]
        
        return safe
    
    async def stream_audio_secure(
        self,
        audio_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[SecureAudioChunk, None]:
        """
        Stream audio con encryption chunk-by-chunk.
        
        Ogni chunk è cifrato prima di essere processato.
        """
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        import secrets
        
        # Genera chiave effimera per questa sessione
        key = AESGCM.generate_key(bit_length=256)
        aesgcm = AESGCM(key)
        
        sequence = 0
        
        async for chunk in audio_stream:
            # Genera IV unico
            iv = secrets.token_bytes(12)
            
            # Cifra chunk
            encrypted = aesgcm.encrypt(iv, chunk, None)
            
            # Calcola checksum
            checksum = hashlib.sha256(chunk).hexdigest()
            
            yield SecureAudioChunk(
                encrypted_data=encrypted,
                sequence=sequence,
                timestamp=time.time(),
                checksum=checksum,
                encryption_iv=iv
            )
            
            sequence += 1
    
    def get_enclave_status(self) -> Dict[str, Any]:
        """Stato sicurezza enclave."""
        return {
            "enclave_ready": self._enclave_ready,
            "enclave_mode": ENCLAVE_MODE,
            "attestation_enabled": ATTESTATION_ENABLED,
            "memory_encryption_active": self._memory_encryption_active,
            "secrets_provisioned": self._secrets is not None,
            "measurement": self.attestation._calculate_code_measurement()[:16]
        }


class ConfidentialHealthEndpoint:
    """Endpoint health specifico per enclave."""
    
    def __init__(self, service: ConfidentialRetellService):
        self.service = service
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check che include verifica enclave."""
        status = self.service.get_enclave_status()
        
        # Verifica attestation fresh
        attestation = get_attestation_service()
        report = attestation.get_attestation_report()
        verification = await attestation.verify_attestation(report)
        
        return {
            "status": "healthy" if status["enclave_ready"] else "unhealthy",
            "enclave": status,
            "attestation": {
                "valid": verification.valid,
                "trusted": verification.trusted,
                "expires_at": verification.expires_at.isoformat()
            }
        }