"""
Example: S3 Upload Handler

Automatically upload batch results to Amazon S3.

This is a template showing how to create a custom result handler
that uploads results to cloud storage.

Configuration:
- AWS_ACCESS_KEY_ID: AWS access key
- AWS_SECRET_ACCESS_KEY: AWS secret key
- AWS_REGION: AWS region (default: us-east-1)
- S3_BUCKET: S3 bucket name
- S3_PREFIX: Optional prefix for object keys (default: batch-results/)
"""

import os
import json
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime

# Optional: Only import if boto3 is available
try:
    import boto3
    from botocore.exceptions import ClientError
    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False

from core.result_handlers.base import ResultHandler

logger = logging.getLogger(__name__)


class S3UploadHandler(ResultHandler):
    """
    Upload batch results to Amazon S3.
    
    Uploads results as JSONL files to S3 for archival or further processing.
    
    Object key format:
    s3://{bucket}/{prefix}/{batch_id}/results.jsonl
    s3://{bucket}/{prefix}/{batch_id}/metadata.json
    
    Example:
    s3://my-bucket/batch-results/batch_abc123/results.jsonl
    s3://my-bucket/batch-results/batch_abc123/metadata.json
    """
    
    def name(self) -> str:
        return "s3_upload"
    
    def enabled(self, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Check if S3 is configured and available."""
        if not S3_AVAILABLE:
            logger.warning("boto3 not installed, S3UploadHandler disabled")
            return False

        bucket = os.getenv('S3_BUCKET')
        return bool(bucket)
    
    def handle(
        self,
        batch_id: str,
        results: List[Dict[str, Any]],
        metadata: Dict[str, Any]
    ) -> bool:
        """
        Upload results to S3.
        
        Args:
            batch_id: Batch identifier
            results: List of batch results
            metadata: Batch metadata
            
        Returns:
            True if upload successful, False otherwise
        """
        # Get S3 configuration
        bucket = os.getenv('S3_BUCKET')
        prefix = os.getenv('S3_PREFIX', 'batch-results/')
        region = os.getenv('AWS_REGION', 'us-east-1')
        
        # Ensure prefix ends with /
        if prefix and not prefix.endswith('/'):
            prefix += '/'
        
        try:
            # Create S3 client
            s3_client = boto3.client('s3', region_name=region)
            
            # Upload results as JSONL
            results_key = f"{prefix}{batch_id}/results.jsonl"
            results_content = '\n'.join([json.dumps(r) for r in results])
            
            logger.info(f"Uploading results to s3://{bucket}/{results_key}")
            
            s3_client.put_object(
                Bucket=bucket,
                Key=results_key,
                Body=results_content.encode('utf-8'),
                ContentType='application/jsonl',
                Metadata={
                    'batch_id': batch_id,
                    'result_count': str(len(results)),
                    'uploaded_at': datetime.utcnow().isoformat()
                }
            )
            
            # Upload metadata as JSON
            metadata_key = f"{prefix}{batch_id}/metadata.json"
            metadata_content = json.dumps(metadata, indent=2)
            
            logger.info(f"Uploading metadata to s3://{bucket}/{metadata_key}")
            
            s3_client.put_object(
                Bucket=bucket,
                Key=metadata_key,
                Body=metadata_content.encode('utf-8'),
                ContentType='application/json'
            )
            
            logger.info(f"✅ Uploaded {len(results)} results to S3")
            logger.info(f"📦 Results: s3://{bucket}/{results_key}")
            logger.info(f"📋 Metadata: s3://{bucket}/{metadata_key}")
            
            return True
            
        except ClientError as e:
            logger.error(f"❌ S3 upload failed: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ S3 upload failed: {e}")
            return False


# Example usage:
# from result_handlers import register_handler
# from result_handlers.examples.s3_upload import S3UploadHandler
#
# handler = S3UploadHandler()
# register_handler(handler)

