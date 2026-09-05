"""
S3 file storage service for candidate documents.

Handles:
- Pre-signed URL generation (upload directly to S3)
- File verification after upload
- S3 cleanup on candidate deletion
- Fallback to local storage if S3 not configured
"""

import logging
import os
import boto3
from datetime import datetime, timedelta
from typing import Optional, Dict
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Configuration
S3_BUCKET = os.getenv("AWS_S3_BUCKET", "wros-candidate-documents")
S3_REGION = os.getenv("AWS_S3_REGION", "us-east-1")
S3_ENABLED = os.getenv("AWS_S3_ENABLED", "false").lower() == "true"

# Pre-signed URL expiration (15 minutes)
PRESIGNED_URL_EXPIRATION = 15 * 60


class S3UploadService:
    """Service for S3 file uploads with fallback to local storage."""

    def __init__(self):
        """Initialize S3 client if configured."""
        self.s3_enabled = S3_ENABLED
        self.bucket = S3_BUCKET

        if self.s3_enabled:
            try:
                self.s3_client = boto3.client("s3", region_name=S3_REGION)
                self._verify_bucket_exists()
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                self.s3_enabled = False
        else:
            logger.warning("S3 not configured. Using local storage fallback.")
            self.s3_client = None

    def _verify_bucket_exists(self):
        """Verify S3 bucket exists and is accessible."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket)
            logger.info(f"S3 bucket '{self.bucket}' verified")
        except ClientError as e:
            error_code = int(e.response["Error"]["Code"])
            if error_code == 404:
                logger.error(f"S3 bucket '{self.bucket}' does not exist")
            else:
                logger.error(f"Error accessing S3 bucket: {e}")
            raise

    def get_presigned_upload_url(
        self,
        candidate_id: str,
        filename: str,
        file_size_bytes: int,
    ) -> str:
        """
        Generate pre-signed URL for direct browser-to-S3 upload.

        User's browser uploads directly to S3, bypassing our server.
        This prevents 20GB files from going through our API.

        Args:
            candidate_id: Candidate ID
            filename: Original filename
            file_size_bytes: File size in bytes

        Returns:
            Pre-signed S3 URL for upload

        Raises:
            ValueError: If S3 not configured
            ClientError: If S3 request fails
        """
        if not self.s3_enabled:
            logger.warning("S3 not configured, returning local upload URL")
            return f"/api/v1/candidates/{candidate_id}/upload-local"

        try:
            # S3 key format: candidates/{candidate_id}/{timestamp}_{filename}
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            s3_key = f"candidates/{candidate_id}/{timestamp}_{filename}"

            # Generate pre-signed POST policy
            # This allows browser to upload directly to S3
            presigned_post = self.s3_client.generate_presigned_post(
                Bucket=self.bucket,
                Key=s3_key,
                Fields={
                    "Content-Type": "application/octet-stream",
                },
                Conditions=[
                    ["content-length-range", 0, file_size_bytes],
                ],
                ExpiresIn=PRESIGNED_URL_EXPIRATION,
            )

            logger.info(
                f"Generated presigned URL for {candidate_id}: {s3_key} "
                f"(expires in {PRESIGNED_URL_EXPIRATION}s)"
            )

            return presigned_post

        except ClientError as e:
            logger.error(f"Failed to generate presigned URL: {e}", exc_info=True)
            raise ValueError(f"Failed to generate upload URL: {str(e)}")

    def verify_file_uploaded(
        self,
        s3_url: str,
        expected_size_bytes: Optional[int] = None,
    ) -> Dict:
        """
        Verify file was successfully uploaded to S3.

        Called after browser confirms upload to S3.
        Returns S3 metadata to store in database.

        Args:
            s3_url: S3 URL or S3 key from browser
            expected_size_bytes: Expected file size (optional validation)

        Returns:
            {
                "s3_key": "candidates/...",
                "file_size": 1024000,
                "uploaded_at": "2026-09-05T...",
                "download_url": "https://s3.../..."
            }

        Raises:
            ValueError: If file not found or size mismatch
        """
        if not self.s3_enabled:
            logger.warning("S3 not configured, skipping verification")
            return {
                "s3_key": s3_url,
                "file_size": expected_size_bytes or 0,
                "uploaded_at": datetime.utcnow().isoformat(),
                "download_url": s3_url,
            }

        try:
            # Extract S3 key from URL
            # URL format: https://bucket.s3.region.amazonaws.com/key
            # or: bucket/key (if passed as key directly)
            if s3_url.startswith("http"):
                s3_key = s3_url.split("/", 3)[-1]  # Extract key from URL
            else:
                s3_key = s3_url

            # Get object metadata
            response = self.s3_client.head_object(Bucket=self.bucket, Key=s3_key)

            file_size = response.get("ContentLength", 0)

            # Verify size if expected_size provided
            if expected_size_bytes and file_size != expected_size_bytes:
                raise ValueError(
                    f"File size mismatch: expected {expected_size_bytes}, got {file_size}"
                )

            # Generate download URL (time-limited)
            download_url = self.s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": s3_key},
                ExpiresIn=7 * 24 * 60 * 60,  # 7 days
            )

            logger.info(f"Verified S3 file: {s3_key} ({file_size} bytes)")

            return {
                "s3_key": s3_key,
                "file_size": file_size,
                "uploaded_at": datetime.utcnow().isoformat(),
                "download_url": download_url,
            }

        except ClientError as e:
            logger.error(f"Failed to verify S3 file: {e}", exc_info=True)
            raise ValueError(f"File not found or verification failed: {str(e)}")

    def delete_candidate_files(self, candidate_id: str) -> int:
        """
        Delete all S3 files for a candidate.

        Called when candidate is deleted or abandoned.

        Args:
            candidate_id: Candidate ID

        Returns:
            Number of files deleted
        """
        if not self.s3_enabled:
            logger.warning("S3 not configured, skipping deletion")
            return 0

        try:
            # List all objects under candidates/{candidate_id}/
            prefix = f"candidates/{candidate_id}/"
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket,
                Prefix=prefix,
            )

            if "Contents" not in response:
                logger.info(f"No files found for candidate {candidate_id}")
                return 0

            # Delete all objects
            objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]

            if objects_to_delete:
                self.s3_client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": objects_to_delete},
                )

            logger.info(f"Deleted {len(objects_to_delete)} files for candidate {candidate_id}")
            return len(objects_to_delete)

        except ClientError as e:
            logger.error(f"Failed to delete candidate files: {e}", exc_info=True)
            return 0

    def cleanup_stale_files(self, days_old: int) -> int:
        """
        Delete S3 files older than specified days.

        Cleanup job for abandoned uploads.

        Args:
            days_old: Delete files older than this many days

        Returns:
            Number of files deleted
        """
        if not self.s3_enabled:
            return 0

        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)

            response = self.s3_client.list_objects_v2(Bucket=self.bucket)

            if "Contents" not in response:
                return 0

            objects_to_delete = []
            for obj in response["Contents"]:
                if obj["LastModified"].replace(tzinfo=None) < cutoff_date:
                    objects_to_delete.append({"Key": obj["Key"]})

            if objects_to_delete:
                self.s3_client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": objects_to_delete},
                )

            logger.info(f"Cleanup: Deleted {len(objects_to_delete)} stale files")
            return len(objects_to_delete)

        except ClientError as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            return 0


# Singleton instance
_s3_service = None


def get_s3_service() -> S3UploadService:
    """Get S3 service singleton."""
    global _s3_service
    if _s3_service is None:
        _s3_service = S3UploadService()
    return _s3_service
