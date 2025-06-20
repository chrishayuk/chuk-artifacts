#!/usr/bin/env python3
# diagnostics/ibm_cos_diagnostic.py
"""
IBM COS Diagnostic and Fix Tool

This script helps diagnose and fix common IBM COS configuration issues,
particularly the signature version problems seen in your test output.
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Load environment variables from .env file if available
def load_dotenv():
    """Load environment variables from .env file."""
    env_file = Path(__file__).parent.parent / ".env"
    
    if env_file.exists():
        print(f"📁 Loading environment from: {env_file}")
        try:
            with open(env_file, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        
                        # Only set if not already in environment
                        if key not in os.environ:
                            os.environ[key] = value
                            print(f"  ✅ Loaded {key}")
                        else:
                            print(f"  ⏭️ Skipped {key} (already set)")
            
            print("✅ Environment loaded successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to load .env file: {e}")
            return False
    else:
        print("ℹ️ No .env file found, using system environment variables")
        return True

# Load .env on import
load_dotenv()


def diagnose_environment():
    """Diagnose IBM COS environment configuration."""
    print("🔍 Diagnosing IBM COS Environment Configuration")
    print("=" * 60)
    
    issues = []
    recommendations = []
    
    # Check credentials
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    endpoint = os.getenv("IBM_COS_ENDPOINT")
    region = os.getenv("AWS_REGION")
    bucket = os.getenv("ARTIFACT_BUCKET")
    
    print("📋 Current Configuration:")
    print(f"  AWS_ACCESS_KEY_ID: {'✅ Set' if access_key else '❌ Missing'}")
    print(f"  AWS_SECRET_ACCESS_KEY: {'✅ Set' if secret_key else '❌ Missing'}")
    print(f"  IBM_COS_ENDPOINT: {endpoint or '❌ Not set (using default)'}")
    print(f"  AWS_REGION: {region or '❌ Not set (using default)'}")
    print(f"  ARTIFACT_BUCKET: {bucket or '❌ Not set (using default)'}")
    
    # Validate credentials format
    if access_key:
        if len(access_key) < 10:
            issues.append("AWS_ACCESS_KEY_ID seems too short")
        print(f"  Access Key Length: {len(access_key)} characters")
    else:
        issues.append("AWS_ACCESS_KEY_ID is required for HMAC authentication")
    
    if secret_key:
        if len(secret_key) < 20:
            issues.append("AWS_SECRET_ACCESS_KEY seems too short")
        print(f"  Secret Key Length: {len(secret_key)} characters")
    else:
        issues.append("AWS_SECRET_ACCESS_KEY is required for HMAC authentication")
    
    # Validate endpoint format
    if endpoint:
        if "cloud-object-storage.appdomain.cloud" not in endpoint:
            issues.append("Endpoint doesn't match IBM COS format")
        if not endpoint.startswith("https://"):
            issues.append("Endpoint should use HTTPS")
        print(f"  Endpoint Format: {'✅ Valid' if 'cloud-object-storage.appdomain.cloud' in endpoint else '❌ Invalid'}")
    else:
        recommendations.append("Set IBM_COS_ENDPOINT for better control")
    
    # Check region consistency
    if endpoint and region:
        endpoint_region = None
        if "us-south" in endpoint:
            endpoint_region = "us-south"
        elif "us-east" in endpoint:
            endpoint_region = "us-east"
        elif "eu-gb" in endpoint:
            endpoint_region = "eu-gb"
        
        if endpoint_region and endpoint_region != region:
            issues.append(f"Region mismatch: endpoint suggests {endpoint_region}, AWS_REGION is {region}")
    
    # Print issues and recommendations
    if issues:
        print("\n❌ Issues Found:")
        for issue in issues:
            print(f"  - {issue}")
    
    if recommendations:
        print("\n💡 Recommendations:")
        for rec in recommendations:
            print(f"  - {rec}")
    
    if not issues:
        print("\n✅ Configuration looks good!")
    
    print("\n" + "=" * 60)
    return len(issues) == 0


def show_signature_issue_explanation():
    """Explain the signature issue and solution."""
    print("🔧 IBM COS Signature Configuration Issue")
    print("=" * 60)
    print()
    print("The 'SignatureDoesNotMatch' errors indicate that your IBM COS provider")
    print("is using the wrong signature version. Here's what's happening:")
    print()
    print("❌ PROBLEM:")
    print("  - IBM COS HMAC requires Signature Version 4 ('s3v4')")
    print("  - Your current provider may be using Signature Version 2 ('s3')")
    print("  - This causes authentication failures with IBM COS")
    print()
    print("✅ SOLUTION:")
    print("  - Use signature_version='s3v4' in AioConfig")
    print("  - Enable path-style addressing: addressing_style='path'")
    print("  - Ensure region matches endpoint")
    print()
    print("🔧 Fixed Configuration:")
    print("```python")
    print("config=AioConfig(")
    print("    signature_version='s3v4',  # Changed from 's3'")
    print("    s3={'addressing_style': 'path'},")
    print("    read_timeout=60,")
    print("    connect_timeout=30")
    print(")")
    print("```")
    print()


async def test_signature_versions():
    """Test different signature versions to identify the working one."""
    print("🧪 Testing Different Signature Versions")
    print("=" * 60)
    
    access_key = os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    endpoint = os.getenv("IBM_COS_ENDPOINT", "https://s3.us-south.cloud-object-storage.appdomain.cloud")
    region = os.getenv("AWS_REGION", "us-south")
    bucket = os.getenv("ARTIFACT_BUCKET", "chuk-sandbox-2")
    
    if not (access_key and secret_key):
        print("❌ Cannot test - missing credentials")
        return False
    
    import aioboto3
    from aioboto3.session import AioConfig
    
    # Test different configurations
    test_configs = [
        ("s3v4 + path", AioConfig(signature_version='s3v4', s3={'addressing_style': 'path'})),
        ("s3v4 + virtual", AioConfig(signature_version='s3v4', s3={'addressing_style': 'virtual'})),
        ("s3 + path", AioConfig(signature_version='s3', s3={'addressing_style': 'path'})),
        ("s3 + virtual", AioConfig(signature_version='s3', s3={'addressing_style': 'virtual'})),
        ("default", AioConfig()),
    ]
    
    results = {}
    
    for config_name, config in test_configs:
        print(f"\n🔬 Testing {config_name}...")
        
        try:
            session = aioboto3.Session()
            async with session.client(
                "s3",
                endpoint_url=endpoint,
                region_name=region,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                config=config
            ) as client:
                # Simple head_bucket test
                await client.head_bucket(Bucket=bucket)
                results[config_name] = "✅ SUCCESS"
                print(f"  ✅ {config_name}: HEAD bucket successful")
                
        except Exception as e:
            error_type = "Unknown"
            if "SignatureDoesNotMatch" in str(e):
                error_type = "Signature Error"
            elif "403" in str(e) or "Forbidden" in str(e):
                error_type = "Permission Error"  
            elif "NoSuchBucket" in str(e):
                error_type = "Bucket Not Found"
            elif "InvalidAccessKeyId" in str(e):
                error_type = "Invalid Credentials"
            
            results[config_name] = f"❌ {error_type}"
            print(f"  ❌ {config_name}: {error_type}")
    
    # Print summary
    print(f"\n📊 Test Results Summary:")
    for config_name, result in results.items():
        print(f"  {config_name}: {result}")
    
    # Find the best configuration
    successful_configs = [name for name, result in results.items() if "✅" in result]
    
    if successful_configs:
        print(f"\n🎉 Working configuration(s): {', '.join(successful_configs)}")
        print(f"💡 Recommendation: Use '{successful_configs[0]}' configuration")
        return True
    else:
        print("\n❌ No configuration worked. Check:")
        print("  - Credentials are valid")
        print("  - Bucket exists and you have access")
        print("  - Network connectivity to IBM COS")
        return False


async def test_simple_operation():
    """Test a simple operation with the fixed configuration."""
    print("\n🚀 Testing Simple Operation with Fixed Configuration")
    print("=" * 60)
    
    try:
        # Use the fixed provider
        from chuk_artifacts.providers.ibm_cos import factory
        
        cos_factory = factory()
        
        async with cos_factory() as cos:
            bucket = os.getenv("ARTIFACT_BUCKET", "chuk-sandbox-2")
            
            print(f"🪣 Testing bucket access: {bucket}")
            
            # Test head_bucket
            try:
                await cos.head_bucket(Bucket=bucket)
                print("  ✅ Bucket accessible")
            except Exception as e:
                print(f"  ❌ Bucket access failed: {e}")
                if "403" in str(e):
                    print("     This may be a permissions issue, not a signature issue")
                return False
            
            # Test simple put/get/delete
            test_key = "diagnostic-test.txt"
            test_data = b"IBM COS diagnostic test"
            
            print("📤 Testing put_object...")
            try:
                put_response = await cos.put_object(
                    Bucket=bucket,
                    Key=test_key,
                    Body=test_data,
                    ContentType="text/plain"
                )
                print(f"  ✅ Put successful: {put_response.get('ETag', 'unknown')}")
            except Exception as e:
                print(f"  ❌ Put failed: {e}")
                return False
            
            print("📥 Testing get_object...")
            try:
                get_response = await cos.get_object(Bucket=bucket, Key=test_key)
                if hasattr(get_response["Body"], "read"):
                    retrieved_data = await get_response["Body"].read()
                else:
                    retrieved_data = get_response["Body"]
                
                assert retrieved_data == test_data
                print("  ✅ Get successful")
            except Exception as e:
                print(f"  ❌ Get failed: {e}")
                return False
            
            print("🗑️ Testing delete_object...")
            try:
                await cos.delete_object(Bucket=bucket, Key=test_key)
                print("  ✅ Delete successful")
            except Exception as e:
                print(f"  ❌ Delete failed: {e}")
                return False
            
        print("\n🎉 All operations successful with fixed configuration!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_fixed_provider_file():
    """Create/update the IBM COS provider file with the fix."""
    print("\n🔧 Creating Fixed IBM COS Provider")
    print("=" * 60)
    
    provider_file = Path("src/chuk_artifacts/providers/ibm_cos.py")
    
    if not provider_file.parent.exists():
        print(f"❌ Provider directory not found: {provider_file.parent}")
        return False
    
    # The fixed provider code (from the artifact above)
    fixed_content = '''# -*- coding: utf-8 -*-
# chuk_artifacts/providers/ibm_cos.py
"""
Factory for an aioboto3 client wired for IBM Cloud Object Storage (COS).
Supports both IAM and HMAC auth.

FIXED VERSION with correct signature configuration for IBM COS.
"""

from __future__ import annotations
import os, aioboto3
from aioboto3.session import AioConfig
from typing import Optional, Callable, AsyncContextManager


def factory(
    *,
    endpoint_url: Optional[str] = None,
    region: str = "us-south",
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
) -> Callable[[], AsyncContextManager]:
    """
    Return an async-context S3 client for IBM COS (HMAC only).
    
    CRITICAL: IBM COS requires specific configuration for HMAC authentication:
    - Signature version must be 's3v4' (not 's3')
    - Path-style addressing is required
    - Region must match the endpoint
    """
    endpoint_url = endpoint_url or os.getenv(
        "IBM_COS_ENDPOINT",
        "https://s3.us-south.cloud-object-storage.appdomain.cloud",
    )
    access_key = access_key or os.getenv("AWS_ACCESS_KEY_ID")
    secret_key = secret_key or os.getenv("AWS_SECRET_ACCESS_KEY")
    
    # ✅ Extract and validate region from endpoint
    if endpoint_url:
        if "us-south" in endpoint_url:
            region = "us-south"
        elif "us-east" in endpoint_url:
            region = "us-east"  # Note: not us-east-1 for IBM COS
        elif "eu-gb" in endpoint_url:
            region = "eu-gb"
        elif "eu-de" in endpoint_url:
            region = "eu-de"
        elif "jp-tok" in endpoint_url:
            region = "jp-tok"
        elif "au-syd" in endpoint_url:
            region = "au-syd"
    
    # Check AWS_REGION environment variable as override
    env_region = os.getenv('AWS_REGION')
    if env_region:
        region = env_region

    if not (access_key and secret_key):
        raise RuntimeError(
            "HMAC credentials missing. "
            "Set AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY "
            "or generate an HMAC key for your COS instance."
        )

    def _make() -> AsyncContextManager:
        session = aioboto3.Session()
        return session.client(
            "s3",
            endpoint_url=endpoint_url,
            region_name=region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            # ✅ CRITICAL: IBM COS HMAC requires Signature Version 4 AND path-style addressing
            config=AioConfig(
                signature_version='s3v4',  # Changed from 's3' to 's3v4'
                s3={
                    'addressing_style': 'path'  # IBM COS requires path-style
                },
                # Additional configurations for IBM COS compatibility
                read_timeout=60,
                connect_timeout=30,
                retries={
                    'max_attempts': 3,
                    'mode': 'adaptive'
                }
            )
        )

    return _make


# Backward compatibility - direct client function  
def client(
    *,
    endpoint_url: Optional[str] = None,
    region: Optional[str] = None,
    access_key: Optional[str] = None,
    secret_key: Optional[str] = None,
):
    """
    Return an aioboto3 S3 client context manager for IBM COS.
    
    This is a convenience function for direct usage.
    The factory() function is preferred for use with ArtifactStore.
    """
    session = aioboto3.Session()
    
    # Use the same endpoint and region logic as factory
    endpoint_url = endpoint_url or os.getenv(
        "IBM_COS_ENDPOINT",
        "https://s3.us-south.cloud-object-storage.appdomain.cloud"
    )
    
    # Extract region from endpoint if not provided
    if not region:
        if "us-south" in endpoint_url:
            region = "us-south"
        elif "us-east" in endpoint_url:
            region = "us-east"
        elif "eu-gb" in endpoint_url:
            region = "eu-gb"
        else:
            region = "us-south"  # Default
    
    return session.client(
        "s3",
        endpoint_url=endpoint_url,
        region_name=region,
        aws_access_key_id=access_key or os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=secret_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
        config=AioConfig(
            signature_version='s3v4',  # Fixed signature version
            s3={'addressing_style': 'path'},
            read_timeout=60,
            connect_timeout=30
        )
    )
'''
    
    try:
        # Backup existing file
        if provider_file.exists():
            backup_file = provider_file.with_suffix('.py.backup')
            provider_file.rename(backup_file)
            print(f"  💾 Backed up existing file to: {backup_file}")
        
        # Write fixed version
        provider_file.write_text(fixed_content, encoding='utf-8')
        print(f"  ✅ Created fixed provider: {provider_file}")
        print("  🔧 Key changes made:")
        print("    - signature_version changed from 's3' to 's3v4'")
        print("    - Added path-style addressing requirement")
        print("    - Added timeouts and retry configuration")
        return True
        
    except Exception as e:
        print(f"  ❌ Failed to create fixed provider: {e}")
        return False


async def main():
    """Main diagnostic routine."""
    print("🏥 IBM COS Diagnostic and Fix Tool")
    print("=" * 60)
    print()
    
    # Step 1: Diagnose environment
    env_ok = diagnose_environment()
    
    # Step 2: Show signature issue explanation
    show_signature_issue_explanation()
    
    # Step 3: Test different signature versions
    print("\n" + "=" * 60)
    await test_signature_versions()
    
    # Step 4: Create fixed provider
    print("\n" + "=" * 60)
    provider_fixed = create_fixed_provider_file()
    
    # Step 5: Test with fixed configuration
    if provider_fixed:
        await test_simple_operation()
    
    # Final recommendations
    print("\n" + "=" * 60)
    print("🎯 SUMMARY AND NEXT STEPS")
    print("=" * 60)
    
    if env_ok and provider_fixed:
        print("✅ Environment configuration looks good")
        print("✅ Fixed provider has been created")
        print()
        print("🚀 Next steps:")
        print("  1. Run the IBM COS tests again:")
        print("     uv run diagnostics/ibm_cos_hmac_runner.py")
        print("  2. If you still see signature errors, check:")
        print("     - Your HMAC credentials are for IBM COS (not AWS)")
        print("     - The bucket exists and you have access")
        print("     - Your network can reach IBM COS endpoints")
    else:
        print("❌ Issues found that need to be addressed:")
        if not env_ok:
            print("  - Fix environment configuration issues")
        if not provider_fixed:
            print("  - Fix provider file creation issues")
        print()
        print("💡 If problems persist:")
        print("  - Verify HMAC credentials in IBM Cloud Console")
        print("  - Check bucket permissions and existence")
        print("  - Try with a different bucket for testing")


if __name__ == "__main__":
    asyncio.run(main())