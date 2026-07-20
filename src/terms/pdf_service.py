"""
src/terms/pdf_service.py

The central Cryptographic Document Engine.
Handles in-memory PDF layout, SHA-256 fingerprinting, PKCS#7 cryptographic sealing,
and true non-blocking asynchronous streaming to Supabase Storage.
"""

import io
import hashlib
import logging
import asyncio
import uuid
import base64
from datetime import datetime, timezone

# -- Cryptography: In-Memory Key Parsing --
from cryptography.hazmat.primitives import serialization
from cryptography import x509

# -- ReportLab: The Visual Presentation Engine --
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors

# -- PyHanko: The Cryptographic Sealing Engine --
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.sign import signers

# -- Infrastructure --
from supabase import acreate_client, AsyncClient
from core.config import settings
from core.exceptions import InfrastructureError

logger = logging.getLogger("HEAL_LEGAL_SECURITY")
logger.setLevel(logging.WARNING)


def _draw_raw_document(client_name: str, client_email: str, ip_address: str, timestamp: datetime) -> io.BytesIO:
    """
    Synchronous CPU-bound function to draw the visual PDF.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, title="Heal Her - Terms of Service Execution",
        author="Heal Her Legal Matrix"
    )
    
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    body_style = styles['Normal']
    body_style.leading = 14
    
    story = []
    
    # 1. Document Header
    story.append(Paragraph("MASTER TERMS OF SERVICE AGREEMENT", title_style))
    story.append(Spacer(1, 20))
    
    # 2. Terms Text Content
    terms_text = """
    This document constitutes a legally binding agreement executed between Heal Her 
    and the verified identity detailed in the cryptographic audit box below. By executing 
    this document via secure One-Time Passcode (OTP), the user explicitly accepts all 
    limitations of liability, jurisdictional governance, and systemic protocols.
    """
    story.append(Paragraph(terms_text, body_style))
    story.append(Spacer(1, 40))
    
    # 3. The Execution Audit Box
    audit_data = [
        ["CRYPTOGRAPHIC AUDIT TRAIL", ""],
        ["Verified Legal Name:", client_name],
        ["Verified Email Contact:", client_email],
        ["Network Footprint (IP):", ip_address],
        ["UTC Execution Timestamp:", timestamp.strftime("%Y-%m-%d %H:%M:%S UTC")],
        ["Execution Status:", "LOCKED & VERIFIED"]
    ]
    
    table = Table(audit_data, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1C1246")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor("#DA8CA0")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#FAFAFA")),
        ('GRID', (0, 0), (-1, -1), 1, colors.HexColor("#2A1F55")),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
    ]))
    
    story.append(table)
    
    # Build the PDF into the memory buffer
    doc.build(story)
    buffer.seek(0)
    
    return buffer


def _apply_cryptographic_seal(raw_pdf_buffer: io.BytesIO) -> io.BytesIO:
    """
    Synchronous CPU-bound function to apply the PyHanko PKCS#7 digital signature.
    Reads base64-encoded PEM strings directly from environment memory.
    """
    try:
        # 1. Decode base64 strings to raw bytes
        key_bytes = base64.b64decode(settings.SIGNING_KEY_PATH)
        cert_bytes = base64.b64decode(settings.SIGNING_CERT_PATH)
        
        # 2. In-Memory Deserialization using cryptography primitives
        private_key = serialization.load_pem_private_key(
            key_bytes,
            password=settings.SIGNING_KEY_PASSPHRASE.encode('utf-8')
        )
        cert = x509.load_pem_x509_certificate(cert_bytes)
        
        # 3. Instantiate the Signer
        signer = signers.SimpleSigner(
            signing_cert=cert,
            signing_key=private_key
        )
    except Exception as e:
        logger.critical(f"[PKI FAILURE] Could not load cryptographic keys from memory: {str(e)}")
        raise InfrastructureError("Internal cryptographic matrix failure.")

    reader = PdfFileReader(raw_pdf_buffer)
    writer = IncrementalPdfFileWriter(reader)
    
    signed_buffer = io.BytesIO()
    
    # Mathematically lock the PDF structure
    signers.sign_pdf(
        writer,
        signers.PdfSignatureMetadata(field_name='HealHer_Cryptographic_Seal'),
        signer=signer,
        out=signed_buffer
    )
    
    signed_buffer.seek(0)
    return signed_buffer


def _compute_sha256(buffer: io.BytesIO) -> str:
    """Computes the deterministic SHA-256 fingerprint of the binary stream."""
    buffer.seek(0)
    file_hash = hashlib.sha256(buffer.read()).hexdigest()
    buffer.seek(0)
    return file_hash


async def generate_and_seal_document(client_name: str, client_email: str, ip_address: str) -> dict:
    """
    The main asynchronous orchestrator. 
    Offloads heavy processing to background threads, streams to Supabase, and returns metadata.
    """
    execution_time = datetime.now(timezone.utc)
    
    # Initialize the true Async Supabase Client
    supabase: AsyncClient = await acreate_client(
        settings.SUPABASE_URL, 
        settings.SUPABASE_SERVICE_ROLE_KEY
    )
    
    # 1. Threaded Drawing (Non-Blocking)
    raw_buffer = await asyncio.to_thread(
        _draw_raw_document, client_name, client_email, ip_address, execution_time
    )
    
    # 2. Threaded Cryptographic Sealing (Non-Blocking)
    signed_buffer = await asyncio.to_thread(_apply_cryptographic_seal, raw_buffer)
    
    # 3. Threaded Fingerprinting
    document_hash = await asyncio.to_thread(_compute_sha256, signed_buffer)
    
    # 4. Stream to Supabase Storage Bucket
    file_uuid = str(uuid.uuid4())
    file_path = f"legal_executions/{execution_time.year}/{file_uuid}.pdf"
    
    try:
        # Read the final bytes
        file_bytes = signed_buffer.read()
        
        # Native await-driven Supabase Upload
        await supabase.storage.from_("legal_documents").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )
        
        # Construct the public/signed URL (Sync string manipulation)
        file_url = supabase.storage.from_("legal_documents").get_public_url(file_path)
        
    except Exception as e:
        logger.error(f"[STORAGE FAILURE] Failed to stream PDF to Supabase: {str(e)}")
        raise InfrastructureError("Document generated but failed to persist to storage.")
    
    finally:
        # Explicit memory cleanup
        raw_buffer.close()
        signed_buffer.close()
        
    return {
        "document_hash": document_hash,
        "storage_url": file_url,
        "signed_at": execution_time
    }