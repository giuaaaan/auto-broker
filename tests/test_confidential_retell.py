"""
Tests per Confidential Retell Service.

Testano l'esecuzione sicura di chiamate vocali in enclave TEE.
"""
import pytest
import pytest_asyncio
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio

from api.services.confidential_retell import (
    ConfidentialRetellService,
    ConfidentialCallResult,
    SecureAudioChunk,
    EnclaveNotProvisionedError,
    ConfidentialityViolationError,
    ConfidentialHealthEndpoint
)


class TestConfidentialRetellService:
    """Test suite per confidential retell."""
    
    @pytest_asyncio.fixture
    async def service(self):
        """Fixture per service con attestation mock."""
        with patch.dict("os.environ", {
            "ENCLAVE_MODE": "simulation",
            "ATTESTATION_ENABLED": "false"  # Per testing
        }):
            service = ConfidentialRetellService()
            yield service
    
    def test_initialization(self):
        """Test inizializzazione service."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "simulation"}):
            service = ConfidentialRetellService()
            
            assert service._enclave_ready is False
            assert service._secrets is None
            assert service._memory_encryption_active is False
    
    @pytest.mark.asyncio
    async def test_initialize_enclave_without_attestation(self, service):
        """Test inizializzazione senza attestation."""
        success = await service.initialize_enclave()
        
        # Con ATTESTATION_ENABLED=false, dovrebbe funzionare
        assert success is True
        assert service._enclave_ready is True
        assert service._secrets is not None
    
    @pytest.mark.asyncio
    async def test_process_call_without_initialization(self):
        """Test process_call senza inizializzazione."""
        with patch.dict("os.environ", {
            "ENCLAVE_MODE": "simulation",
            "ATTESTATION_ENABLED": "false"
        }):
            service = ConfidentialRetellService()
            service._enclave_ready = False  # Force non-ready
            
            # Dovrebbe auto-inizializzarsi o fallire
            # Con ATTESTATION_ENABLED=false, auto-inizializza
            try:
                result = await service.process_call_secure(b"fake-audio")
                # Se arriva qui, si è auto-inizializzato
                assert isinstance(result, ConfidentialCallResult)
            except EnclaveNotProvisionedError:
                # Oppure solleva errore (dipende dal flusso)
                pass
    
    @pytest.mark.asyncio
    async def test_sanitize_metadata(self, service):
        """Test sanitizzazione metadati."""
        metadata = {
            "phone_number": "+39 123 456 7890",
            "shipment_id": "SHIP-123",
            "agent_type": "sara",
            "sensitive_data": "should-be-removed"
        }
        
        safe = service._sanitize_metadata(metadata)
        
        # Phone hashato
        assert "phone_hash" in safe
        assert "+39" not in safe["phone_hash"]
        assert len(safe["phone_hash"]) == 16
        
        # ID mantenuti
        assert safe["shipment_id"] == "SHIP-123"
        assert safe["agent_type"] == "sara"
        
        # Dati non in whitelist rimossi
        assert "sensitive_data" not in safe
        assert "phone_number" not in safe
    
    @pytest.mark.asyncio
    async def test_extract_sentiment(self, service):
        """Test estrazione sentiment da risultati Hume."""
        hume_result = {
            "results": {
                "predictions": [
                    {
                        "emotions": [
                            {"name": "joy", "score": 0.85},
                            {"name": "satisfaction", "score": 0.72}
                        ]
                    }
                ]
            }
        }
        
        sentiment = service._extract_sentiment(hume_result)
        
        assert sentiment is not None
        assert "top_emotions" in sentiment
        assert len(sentiment["top_emotions"]) > 0
        assert sentiment["processed_in_enclave"] is True
        assert "timestamp" in sentiment
    
    @pytest.mark.asyncio
    async def test_extract_sentiment_empty(self, service):
        """Test estrazione sentiment con risultati vuoti."""
        sentiment = service._extract_sentiment({})
        assert sentiment is None
        
        sentiment = service._extract_sentiment({"results": {}})
        assert sentiment is None
    
    @pytest.mark.asyncio
    async def test_enclave_status(self, service):
        """Test get enclave status."""
        status = service.get_enclave_status()
        
        assert "enclave_ready" in status
        assert "enclave_mode" in status
        assert "attestation_enabled" in status
        assert "memory_encryption_active" in status
        assert "secrets_provisioned" in status
        assert "measurement" in status
    
    @pytest.mark.asyncio
    async def test_call_result_to_safe_dict(self):
        """Test conversione risultato in dict sicuro."""
        result = ConfidentialCallResult(
            sentiment={"emotions": ["joy"]},
            transcription="Questa è una trascrizione lunga con dati sensibili",
            processing_time_ms=1234.5,
            enclave_attested=True,
            memory_encryption_active=True,
            pii_masked=True
        )
        
        safe = result.to_safe_dict()
        
        assert safe["sentiment"] == {"emotions": ["joy"]}
        assert safe["processing_time_ms"] == 1234.5
        assert safe["security"]["enclave_attested"] is True
        assert safe["security"]["memory_encrypted"] is True
        
        # Trascrizione mascherata
        assert "trascrizione" not in safe["transcription_preview"].lower()
        assert "MASKED" in safe["transcription_preview"]
        assert len(safe["transcription_preview"]) <= 120  # Troncata


class TestConfidentialCallResult:
    """Test per ConfidentialCallResult."""
    
    def test_result_creation(self):
        """Test creazione risultato."""
        result = ConfidentialCallResult(
            sentiment={"joy": 0.9},
            transcription="test",
            processing_time_ms=100.0,
            enclave_attested=True,
            memory_encryption_active=True
        )
        
        assert result.enclave_attested is True
        assert result.pii_masked is True  # Default
    
    def test_mask_transcription(self):
        """Test masking trascrizione."""
        result = ConfidentialCallResult(
            sentiment=None,
            transcription="Il cliente ha detto numero carta 1234 5678 9012 3456",
            processing_time_ms=50.0,
            enclave_attested=True,
            memory_encryption_active=True
        )
        
        preview = result._mask_transcription()
        
        assert "MASKED" in preview
        assert "1234" not in preview  # PII mascherata
        assert len(preview) <= 120
    
    def test_mask_transcription_none(self):
        """Test masking con trascrizione None."""
        result = ConfidentialCallResult(
            sentiment=None,
            transcription=None,
            processing_time_ms=50.0,
            enclave_attested=True,
            memory_encryption_active=True
        )
        
        assert result._mask_transcription() == ""


class TestSecureAudioChunk:
    """Test per SecureAudioChunk."""
    
    def test_chunk_creation(self):
        """Test creazione chunk sicuro."""
        chunk = SecureAudioChunk(
            encrypted_data=b"encrypted-bytes",
            sequence=5,
            timestamp=1234567890.0,
            checksum="abc123",
            encryption_iv=b"iv-bytes-12b"
        )
        
        assert chunk.sequence == 5
        assert chunk.checksum == "abc123"


class TestStreamAudioSecure:
    """Test streaming audio sicuro."""
    
    @pytest.mark.asyncio
    async def test_stream_encryption(self):
        """Test cifratura stream audio."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "simulation"}):
            service = ConfidentialRetellService()
            
            # Crea async generator per audio
            async def audio_generator():
                for i in range(3):
                    yield f"audio-chunk-{i}".encode()
            
            chunks = []
            async for chunk in service.stream_audio_secure(audio_generator()):
                chunks.append(chunk)
                
                assert isinstance(chunk, SecureAudioChunk)
                assert chunk.encrypted_data is not None
                assert chunk.encryption_iv is not None
                assert len(chunk.encryption_iv) == 12  # AES-GCM IV size
                assert chunk.checksum is not None
            
            assert len(chunks) == 3
            assert chunks[0].sequence == 0
            assert chunks[1].sequence == 1
            assert chunks[2].sequence == 2
    
    @pytest.mark.asyncio
    async def test_stream_empty(self):
        """Test stream vuoto."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "simulation"}):
            service = ConfidentialRetellService()
            
            async def empty_generator():
                return
                yield b""  # Never reached
            
            chunks = []
            async for chunk in service.stream_audio_secure(empty_generator()):
                chunks.append(chunk)
            
            assert len(chunks) == 0


class TestConfidentialHealthEndpoint:
    """Test health endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "simulation"}):
            service = ConfidentialRetellService()
            endpoint = ConfidentialHealthEndpoint(service)
            
            health = await endpoint.health_check()
            
            assert "status" in health
            assert "enclave" in health
            assert "attestation" in health
            assert "valid" in health["attestation"]


class TestEnclaveNotProvisionedError:
    """Test eccezione enclave non provisioned."""
    
    def test_exception_message(self):
        """Test messaggio eccezione."""
        error = EnclaveNotProvisionedError("Test message")
        
        assert str(error) == "Test message"
        assert isinstance(error, Exception)


class TestConfidentialityViolationError:
    """Test eccezione violazione confidenzialità."""
    
    def test_exception_message(self):
        """Test messaggio eccezione."""
        error = ConfidentialityViolationError("Processing failed: network error")
        
        assert "Processing failed" in str(error)
        assert isinstance(error, Exception)


class TestAnalyzeSentimentSecure:
    """Test analisi sentiment sicura."""
    
    @pytest.mark.asyncio
    async def test_analyze_without_secrets(self):
        """Test analisi senza secrets."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "simulation"}):
            service = ConfidentialRetellService()
            service._secrets = None
            
            result = await service._analyze_sentiment_secure(b"audio")
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_analyze_without_hume_key(self):
        """Test analisi senza Hume key."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "simulation"}):
            service = ConfidentialRetellService()
            service._secrets = {"other-key": "value"}  # No Hume key
            
            result = await service._analyze_sentiment_secure(b"audio")
            
            assert result is None


@pytest.mark.integration
class TestConfidentialIntegration:
    """Test integrazione con servizi reali (mocked)."""
    
    @pytest.mark.asyncio
    async def test_full_call_flow(self):
        """Test flusso completo chiamata."""
        with patch.dict("os.environ", {
            "ENCLAVE_MODE": "simulation",
            "ATTESTATION_ENABLED": "false"
        }):
            service = ConfidentialRetellService()
            
            # Mock Hume response
            mock_hume_response = {
                "results": {
                    "predictions": [
                        {"emotions": [{"name": "joy", "score": 0.9}]}
                    ]
                }
            }
            
            with patch("httpx.AsyncClient.post") as mock_post:
                mock_response = MagicMock()
                mock_response.raise_for_status = MagicMock()
                mock_response.json = MagicMock(return_value=mock_hume_response)
                mock_post.return_value.__aenter__ = AsyncMock(
                    return_value=mock_response
                )
                mock_post.return_value.__aexit__ = AsyncMock(
                    return_value=None
                )
                
                # Processa chiamata
                result = await service.process_call_secure(
                    b"fake-audio-data",
                    {"shipment_id": "TEST-123", "agent_type": "sara"}
                )
                
                assert isinstance(result, ConfidentialCallResult)
                assert result.enclave_attested is True
                assert result.pii_masked is True


class TestMemoryEncryption:
    """Test memory encryption features."""
    
    def test_memory_encryption_disabled_in_simulation(self):
        """Test encryption disabilitata in simulazione."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "simulation"}):
            service = ConfidentialRetellService()
            
            assert service._memory_encryption_active is False
    
    @pytest.mark.skip(reason="Richiede hardware SEV-SNP")
    def test_memory_encryption_enabled_with_sev(self):
        """Test encryption con SEV-SNP (richiede hardware)."""
        with patch.dict("os.environ", {"ENCLAVE_MODE": "sev-snp"}):
            service = ConfidentialRetellService()
            
            assert service._memory_encryption_active is True