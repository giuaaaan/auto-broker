"""
AUTO-BROKER: Email Service
"""
import os
from typing import Optional, Dict, Any, List
import httpx
import structlog
from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = structlog.get_logger()

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
RESEND_API_URL = "https://api.resend.com"
COMPANY_NAME = os.getenv("COMPANY_NAME", "Logistik AI")

# Initialize Jinja2 templates
template_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
jinja_env = Environment(
    loader=FileSystemLoader(template_dir),
    autoescape=select_autoescape(['html', 'xml'])
)


class EmailService:
    def __init__(self):
        self.api_key = RESEND_API_KEY
        self.api_url = RESEND_API_URL
        self.from_email = f"noreply@{COMPANY_NAME.lower().replace(' ', '')}.com"
        self.from_name = COMPANY_NAME
    
    async def send_email(
        self,
        to: str,
        subject: str,
        html_content: str,
        from_email: Optional[str] = None
    ) -> Dict[str, Any]:
        if not self.api_key:
            return {"id": f"mock_email_{hash(to + subject)}", "status": "sent", "mock": True}
        
        payload = {
            "from": f"{self.from_name} <{from_email or self.from_email}>",
            "to": [to],
            "subject": subject,
            "html": html_content
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_url}/emails",
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload
            )
            response.raise_for_status()
            data = response.json()
            return {"id": data["id"], "status": "sent"}
    
    async def send_proposal(
        self,
        to: str,
        nome_cliente: str,
        azienda: str,
        preventivo_id: str,
        corriere_nome: str,
        prezzo_kg: float,
        prezzo_totale: float,
        tempi_consegna: int,
        lane_origine: str,
        lane_destinazione: str,
        docusign_url: Optional[str] = None
    ) -> Dict[str, Any]:
        try:
            template = jinja_env.get_template("email_proposal.html")
        except:
            # Fallback if template not found
            html = f"""
            <h1>Proposta Commerciale - {COMPANY_NAME}</h1>
            <p>Gentile {nome_cliente},</p>
            <p>Ecco la proposta per {azienda}:</p>
            <ul>
                <li>Corriere: {corriere_nome}</li>
                <li>Tratta: {lane_origine} → {lane_destinazione}</li>
                <li>Prezzo: € {prezzo_totale:.2f}</li>
            </ul>
            """
            return await self.send_email(to, f"Proposta Commerciale - {azienda}", html)
        
        html_content = template.render(
            nome_cliente=nome_cliente,
            azienda=azienda,
            preventivo_id=preventivo_id,
            corriere_nome=corriere_nome,
            prezzo_kg=prezzo_kg,
            prezzo_totale=prezzo_totale,
            tempi_consegna=tempi_consegna,
            lane_origine=lane_origine,
            lane_destinazione=lane_destinazione,
            docusign_url=docusign_url,
            company_name=COMPANY_NAME
        )
        
        return await self.send_email(
            to=to,
            subject=f"Proposta Commerciale - {azienda} - Risparmia fino al 30%",
            html_content=html_content
        )
    
    async def send_followup(self, to: str, nome_cliente: str, azienda: str,
                           tipo: str = "gentile") -> Dict[str, Any]:
        subject_map = {
            "gentile": "Gentile promemoria - Proposta in attesa",
            "urgente": "Urgente: Proposta in scadenza",
            "ultima_chance": "Ultima opportunità - Proposta commerciale"
        }
        
        html = f"""
        <p>Gentile {nome_cliente},</p>
        <p>Volevamo ricordarle la proposta inviata per {azienda}.</p>
        <p>La proposta è valida per 30 giorni.</p>
        """
        
        return await self.send_email(to, subject_map.get(tipo, "Promemoria"), html)
    
    async def send_rejection(self, to: str, nome_cliente: str, azienda: str) -> Dict[str, Any]:
        html = f"""
        <p>Gentile {nome_cliente},</p>
        <p>Grazie per averci contattato per {azienda}.</p>
        <p>Purtroppo al momento non possiamo procedere con una proposta.</p>
        """
        return await self.send_email(to, f"{COMPANY_NAME} - Valutazione richiesta", html)


email_service = EmailService()
