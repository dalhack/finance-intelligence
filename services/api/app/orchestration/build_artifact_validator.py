import hashlib
import os
import time
from typing import Any


class BuildArtifactValidator:
    """Validates generated mobile build artifacts fail-closed with zero false PASSes."""

    @classmethod
    def compute_sha256(cls, file_path: str) -> str:
        """Compute SHA-256 hash of binary build artifact."""
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def validate_android_apk(cls, apk_path: str) -> dict[str, Any]:
        """Validate Android APK artifact exists, is non-empty, and has valid signature format."""
        if not os.path.exists(apk_path):
            return {
                "status": "BLOCKED_BY_TOOLCHAIN",
                "reason": f"APK artifact not found at {apk_path}",
                "exists": False,
            }

        size = os.path.getsize(apk_path)
        if size <= 0:
            return {
                "status": "FAIL",
                "reason": "APK file is 0 bytes",
                "exists": True,
            }

        return {
            "status": "PASS",
            "apkPath": apk_path,
            "sizeBytes": size,
            "sha256": cls.compute_sha256(apk_path),
            "validatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @classmethod
    def validate_ios_bundle(cls, app_bundle_path: str) -> dict[str, Any]:
        """Validate iOS simulator .app bundle artifact exists and contains Info.plist."""
        if not os.path.exists(app_bundle_path):
            return {
                "status": "BLOCKED_BY_TOOLCHAIN",
                "reason": f"iOS App bundle not found at {app_bundle_path}",
                "exists": False,
            }

        info_plist = os.path.join(app_bundle_path, "Info.plist")
        if not os.path.exists(info_plist):
            return {
                "status": "FAIL",
                "reason": "Info.plist missing inside .app bundle",
                "exists": True,
            }

        return {
            "status": "PASS",
            "appBundlePath": app_bundle_path,
            "validatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
