"""Industry Survey Reports - list and link to industry surveys and data from S3."""
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from config.settings import Settings

logger = logging.getLogger(__name__)
router = APIRouter()
_settings = Settings()

# Base URL for public bucket access (no auth)
S3_PUBLIC_BASE = "https://{bucket}.s3.{region}.amazonaws.com/{key}"


def _short_display_name(folder: str) -> str:
    """Short, non-numeric display name for folder: strip digits, keep letters, first token or two."""
    if not folder or not folder.strip():
        return "Other"
    import re
    s = folder.strip().replace("_", " ").replace("-", " ")
    s = re.sub(r"[0-9]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    parts = [p for p in s.split() if p.isalpha()][:2]
    out = " ".join(parts).strip() or "Other"
    return out[:20] if len(out) > 20 else out


def _pretty_file_title(name: str) -> str:
    """Human-friendly title: strip extension, strip leading numbers/separators so title starts with a letter."""
    if not name:
        return ""
    import os
    import re
    base = os.path.splitext(name)[0]
    # Strip from the start any run of digits, underscores, hyphens, dots, spaces (so we start with a letter)
    s = re.sub(r"^[\d_\-\s\.]+", "", base).strip()
    # Replace remaining separators with space for readability
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return base[:50]  # fallback if name was all numbers/symbols
    return s[:60] if len(s) > 60 else s


@router.get("/s3")
async def list_industry_surveys_s3():
    """
    List objects in the configured S3 bucket under Dat_for_model_Training/.
    Returns file names, sizes, last modified, and download URLs.
    Uses AWS credentials from env if set; otherwise builds public URLs for the bucket.
    """
    bucket = _settings.S3_INDUSTRY_BUCKET or "model-training1"
    prefix = _settings.S3_INDUSTRY_PREFIX or "Dat_for_model_Training/"
    region = _settings.AWS_REGION or "ap-south-1"
    access_key = _settings.AWS_ACCESS_KEY_ID or ""
    secret_key = _settings.AWS_SECRET_ACCESS_KEY or ""

    items = []
    use_presigned = bool(access_key.strip() and secret_key.strip())

    try:
        if use_presigned:
            import boto3
            from botocore.exceptions import ClientError

            try:
                client = boto3.client(
                    "s3",
                    region_name=region,
                    aws_access_key_id=access_key.strip(),
                    aws_secret_access_key=secret_key.strip(),
                )
                paginator = client.get_paginator("list_objects_v2")
            except Exception as e:
                logger.warning("S3 client init failed: %s", e)
                raise HTTPException(
                    status_code=503,
                    detail="Failed to create S3 client. Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env.",
                )
            try:
                paginate = paginator.paginate(Bucket=bucket, Prefix=prefix)
            except ClientError as e:
                err = e.response.get("Error", {}) or {}
                if err.get("Code") == "AccessDenied":
                    logger.warning("S3 AccessDenied: %s", e)
                    raise HTTPException(
                        status_code=403,
                        detail="S3 access denied. Check that AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY have ListBucket permission on the bucket.",
                    )
                raise
            for page in paginate:
                for obj in page.get("Contents") or []:
                    key = obj.get("Key", "")
                    if not key or key.endswith("/"):
                        continue
                    # Derive group/industry from key; short non-numeric display name
                    rel = key[len(prefix):] if key.startswith(prefix) else key
                    folder = rel.split("/", 1)[0] if "/" in rel else ""
                    group = folder or "Other"
                    group_display = _short_display_name(group)
                    name = key.split("/")[-1]
                    title = _pretty_file_title(name)
                    try:
                        url = client.generate_presigned_url(
                            "get_object",
                            Params={"Bucket": bucket, "Key": key},
                            ExpiresIn=3600,
                        )
                    except Exception:
                        url = S3_PUBLIC_BASE.format(bucket=bucket, region=region, key=key)
                    items.append({
                        "key": key,
                        "name": name,
                        "name_display": title,
                        "group": group,
                        "group_display": group_display,
                        "size": obj.get("Size", 0),
                        "last_modified": (obj.get("LastModified") or "").isoformat() if obj.get("LastModified") else None,
                        "url": url,
                    })
        else:
            # No credentials: try public list via boto3 (anonymous) or return public URLs for known structure
            try:
                import boto3
                from botocore import UNSIGNED
                from botocore.config import Config

                client = boto3.client(
                    "s3",
                    region_name=region,
                    config=Config(signature_version=UNSIGNED),
                )
                paginator = client.get_paginator("list_objects_v2")
                for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                    for obj in page.get("Contents") or []:
                        key = obj.get("Key", "")
                        if not key or key.endswith("/"):
                            continue
                        rel = key[len(prefix):] if key.startswith(prefix) else key
                        folder = rel.split("/", 1)[0] if "/" in rel else ""
                        group = folder or "Other"
                        group_display = _short_display_name(group)
                        name = key.split("/")[-1]
                        title = _pretty_file_title(name)
                        url = S3_PUBLIC_BASE.format(bucket=bucket, region=region, key=key)
                        items.append({
                            "key": key,
                            "name": name,
                            "name_display": title,
                            "group": group,
                            "group_display": group_display,
                            "size": obj.get("Size", 0),
                            "last_modified": (obj.get("LastModified") or "").isoformat() if obj.get("LastModified") else None,
                            "url": url,
                        })
            except Exception as e:
                logger.warning("S3 list (anonymous) failed: %s. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY for private bucket.", e)
                raise HTTPException(
                    status_code=403,
                    detail="S3 access denied. The bucket is private. Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY in .env (see .env.example) and restart the server.",
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("S3 list_industry_surveys_s3 failed")
        raise HTTPException(status_code=503, detail=f"S3 error: {str(e)}")

    return {
        "bucket": bucket,
        "prefix": prefix,
        "items": items,
    }
