import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def test_ios_bundle_identifier_contract() -> None:
    pbxproj_path = REPO_ROOT / "apps" / "mobile" / "ios" / "Runner.xcodeproj" / "project.pbxproj"
    content = pbxproj_path.read_text(encoding="utf-8")
    assert "com.example.financeIntelligence" not in content, (
        "Placeholder Bundle ID 'com.example.financeIntelligence' found in iOS project"
    )
    assert "PRODUCT_BUNDLE_IDENTIFIER = com.korhanturgut.financeintelligence;" in content, (
        "Authoritative Production Bundle ID 'com.korhanturgut.financeintelligence' missing in iOS project"
    )


def test_android_application_id_contract() -> None:
    gradle_path = REPO_ROOT / "apps" / "mobile" / "android" / "app" / "build.gradle.kts"
    content = gradle_path.read_text(encoding="utf-8")
    assert "com.example.finance_intelligence" not in content, (
        "Placeholder Application ID 'com.example.finance_intelligence' found in Android build.gradle.kts"
    )
    assert 'applicationId = "com.korhanturgut.financeintelligence"' in content, (
        "Authoritative Production Application ID 'com.korhanturgut.financeintelligence' missing in build.gradle.kts"
    )


def test_android_release_signing_contract() -> None:
    gradle_path = REPO_ROOT / "apps" / "mobile" / "android" / "app" / "build.gradle.kts"
    content = gradle_path.read_text(encoding="utf-8")
    assert 'signingConfig = signingConfigs.getByName("debug")' not in content, (
        "CRITICAL SECURITY VIOLATION: Release buildType is configured to use debug signing keys"
    )


def test_flutter_app_config_contract() -> None:
    config_path = REPO_ROOT / "apps" / "mobile" / "lib" / "core" / "config" / "app_config.dart"
    content = config_path.read_text(encoding="utf-8")
    assert "https://finapi.korhanturgut.com/v1" in content, (
        "Authoritative Production API Base URL 'https://finapi.korhanturgut.com/v1' missing in app_config.dart"
    )


def test_ios_privacy_usage_descriptions_contract() -> None:
    plist_path = REPO_ROOT / "apps" / "mobile" / "ios" / "Runner" / "Info.plist"
    content = plist_path.read_text(encoding="utf-8")
    root = ET.fromstring(content)
    assert root is not None
    dict_elem = root.find("dict")
    assert dict_elem is not None

    keys = [elem.text for elem in dict_elem.findall("key")]
    assert "NSCameraUsageDescription" in keys, "Missing NSCameraUsageDescription in Info.plist"
    assert "NSPhotoLibraryUsageDescription" in keys, "Missing NSPhotoLibraryUsageDescription in Info.plist"
