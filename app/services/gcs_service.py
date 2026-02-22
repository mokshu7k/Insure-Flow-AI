"""
Google Cloud Storage service for InsureFlow AI.

Provides graceful upload, download, and signed-URL generation for claim
documents.  All operations are no-ops (return None / False) when
``GCS_BUCKET_NAME`` is not configured, so the application works in local
development without any GCP credentials.

Storage layout inside the bucket:
    claim-documents/{claim_id}/{doc_id}/{original_filename}

Usage:
    from app.services import gcs_service

    # Upload (sync — wrap with run_in_executor in async code):
    path = gcs_service.upload_bytes(blob_name, raw_bytes, content_type)

    # Download:
    data = gcs_service.download_bytes(blob_name)

    # Signed URL (expiry defaults to 60 min):
    url = gcs_service.generate_signed_url(blob_name)
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

# ── Lazy GCS client ───────────────────────────────────────────────────────────
_gcs_client = None


def _get_client():
    """Return a lazily-initialised ``google.cloud.storage.Client``.

    Returns ``None`` if:
    - ``GCS_BUCKET_NAME`` is empty (GCS disabled).
    - ``google-cloud-storage`` is not installed.
    - Credentials are invalid or unavailable.
    """
    global _gcs_client

    if not settings.GCS_BUCKET_NAME:
        return None

    if _gcs_client is not None:
        return _gcs_client

    try:
        from google.cloud import storage as _gcs  # noqa: PLC0415

        if settings.GCS_CREDENTIALS_JSON:
            _gcs_client = _gcs.Client.from_service_account_json(
                settings.GCS_CREDENTIALS_JSON
            )
            logger.info(
                "GCS client initialised with service account JSON for bucket '%s'",
                settings.GCS_BUCKET_NAME,
            )
        else:
            # Application Default Credentials — works with:
            #   • Cloud Run Workload Identity (no key file needed)
            #   • `gcloud auth application-default login` for local dev
            _gcs_client = _gcs.Client()
            logger.info(
                "GCS client initialised via ADC for bucket '%s'",
                settings.GCS_BUCKET_NAME,
            )
    except ImportError:
        logger.error(
            "google-cloud-storage is not installed. "
            "Run `pip install google-cloud-storage` or add it to requirements.txt"
        )
        return None
    except Exception as exc:
        logger.warning("Failed to initialise GCS client: %s", exc)
        return None

    return _gcs_client


def _make_blob_name(claim_id: str, doc_id: str, filename: str | None) -> str:
    """Build a deterministic GCS blob name for a claim document."""
    safe_name = filename or "document"
    # Sanitise: strip path separators that could create unexpected directory nesting
    safe_name = safe_name.replace("/", "_").replace("\\", "_")
    return f"claim-documents/{claim_id}/{doc_id}/{safe_name}"


# ── Public API ────────────────────────────────────────────────────────────────

def upload_bytes(
    blob_name: str,
    data: bytes,
    content_type: str = "application/octet-stream",
) -> Optional[str]:
    """Upload *data* to GCS at *blob_name*.

    Returns the blob name (= ``gcs_path`` stored on ``ClaimDocument``) on
    success.  Returns ``None`` when GCS is not configured or the upload fails.
    The file is stored with ``cache-control: no-store`` so signed-URL
    recipients always get a fresh copy.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.cache_control = "no-store"
        blob.upload_from_string(data, content_type=content_type)
        logger.info(
            "GCS upload OK: gs://%s/%s (%d bytes)",
            settings.GCS_BUCKET_NAME,
            blob_name,
            len(data),
        )
        return blob_name
    except Exception as exc:
        logger.error("GCS upload failed for '%s': %s", blob_name, exc, exc_info=True)
        return None


def download_bytes(blob_name: str) -> Optional[bytes]:
    """Download a blob from GCS.

    Returns the raw bytes on success, or ``None`` when GCS is not configured,
    the blob does not exist, or the download fails.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        data = blob.download_as_bytes()
        logger.info(
            "GCS download OK: gs://%s/%s (%d bytes)",
            settings.GCS_BUCKET_NAME,
            blob_name,
            len(data),
        )
        return data
    except Exception as exc:
        logger.error("GCS download failed for '%s': %s", blob_name, exc, exc_info=True)
        return None


def generate_signed_url(
    blob_name: str,
    expiration_minutes: int = 60,
) -> Optional[str]:
    """Generate a time-limited signed download URL for *blob_name*.

    Signed URLs require that the GCS client was initialised with a service
    account that has the ``iam.serviceAccounts.signBlob`` permission.  When
    running on Cloud Run with Workload Identity the IAM-credentials approach
    is preferred; when running locally you typically use a key file.

    Returns the signed URL string, or ``None`` if GCS is not configured /
    the service account lacks the signing permission.
    """
    client = _get_client()
    if client is None:
        return None

    try:
        bucket = client.bucket(settings.GCS_BUCKET_NAME)
        blob = bucket.blob(blob_name)
        url: str = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
        )
        logger.debug(
            "Signed URL generated for gs://%s/%s (expires in %d min)",
            settings.GCS_BUCKET_NAME,
            blob_name,
            expiration_minutes,
        )
        return url
    except Exception as exc:
        logger.warning(
            "Signed URL generation failed for '%s': %s", blob_name, exc
        )
        return None


# ── Convenience helpers ───────────────────────────────────────────────────────

def build_blob_name(claim_id: str, doc_id: str, filename: str | None) -> str:
    """Public alias for _make_blob_name — used by the service layer."""
    return _make_blob_name(claim_id, doc_id, filename)
