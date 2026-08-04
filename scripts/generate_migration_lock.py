#!/usr/bin/env python3
"""Generate a Linux AMD64 migration lock with uv's PEP 440 resolver."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.tags import compatible_tags, cpython_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version

REQUIREMENTS_IN_NAME = "requirements-migration.in"
UV_VERSION = "0.12.1"
TARGET_PYTHON_VERSION = "3.11"
TARGET_UV_PLATFORM = "x86_64-manylinux_2_36"
TARGET_ABI = "cp311"
RESOLUTION_CUTOFF = "2026-08-04T00:00:00Z"

FORBIDDEN_PACKAGES = {"google-cloud-secret-manager-v1", "scamper"}


@dataclass(frozen=True)
class ResolvedPackage:
    name: str
    version: str
    hashes: tuple[str, ...]
    target_artifacts: tuple[str, ...]
    requires_dist: tuple[str, ...]
    requested: bool

    @property
    def canonical_name(self) -> str:
        return canonicalize_name(self.name)


def _target_marker_environment() -> dict[str, str]:
    environment = default_environment()
    environment.update(
        {
            "implementation_name": "cpython",
            "platform_machine": "x86_64",
            "platform_python_implementation": "CPython",
            "python_full_version": "3.11.0",
            "python_version": TARGET_PYTHON_VERSION,
            "sys_platform": "linux",
        }
    )
    return cast(dict[str, str], environment)


def _target_tags() -> frozenset:
    platforms = [f"manylinux_2_{minor}_x86_64" for minor in range(36, 16, -1)]
    platforms.extend(["manylinux2014_x86_64", "manylinux2010_x86_64", "manylinux1_x86_64"])
    return frozenset(
        list(cpython_tags((3, 11), abis=["cp311", "abi3", "none"], platforms=platforms))
        + list(compatible_tags((3, 11), interpreter="cp311", platforms=platforms))
    )


def _uv_executable() -> str:
    executable = shutil.which("uv")
    if executable is None:
        candidate = Path(sys.executable).with_name("uv")
        if candidate.exists():
            executable = str(candidate)
    if executable is None:
        raise RuntimeError(f"FAIL_CLOSED_UV_ERROR: uv=={UV_VERSION} is required")
    result = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
    version_match = re.match(r"^uv ([0-9]+(?:\.[0-9]+){2})(?:\s|$)", result.stdout.strip())
    if result.returncode != 0 or version_match is None or version_match.group(1) != UV_VERSION:
        raise RuntimeError(
            f"FAIL_CLOSED_UV_ERROR: expected uv {UV_VERSION}, got {result.stdout.strip() or result.stderr.strip()}"
        )
    return executable


def _compile_lock(requirements_path: Path, output_path: Path) -> None:
    command = [
        _uv_executable(),
        "pip",
        "compile",
        str(requirements_path),
        "--python-version",
        TARGET_PYTHON_VERSION,
        "--python-platform",
        TARGET_UV_PLATFORM,
        "--only-binary",
        ":all:",
        "--generate-hashes",
        "--exclude-newer",
        RESOLUTION_CUTOFF,
        "--no-header",
        "--custom-compile-command",
        "scripts/generate_migration_lock.py",
        "--output-file",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"FAIL_CLOSED_UV_RESOLUTION_ERROR: {(result.stderr or result.stdout).strip()}")


def _parse_lock(lock_path: Path) -> dict[str, tuple[str, tuple[str, ...]]]:
    parsed: dict[str, tuple[str, tuple[str, ...]]] = {}
    current_name: str | None = None
    current_version: str | None = None
    current_hashes: list[str] = []

    def flush() -> None:
        nonlocal current_name, current_version, current_hashes
        if current_name is None or current_version is None:
            return
        if not current_hashes:
            raise RuntimeError(f"FAIL_CLOSED_HASH_ERROR: {current_name}=={current_version} has no hashes")
        canonical_name = canonicalize_name(current_name)
        if canonical_name in parsed:
            raise RuntimeError(f"FAIL_CLOSED_DUPLICATE_PACKAGE_ERROR: {canonical_name}")
        parsed[canonical_name] = (current_version, tuple(sorted(set(current_hashes))))
        current_name = None
        current_version = None
        current_hashes = []

    for raw_line in lock_path.read_text().splitlines():
        package_match = re.match(r"^([A-Za-z0-9_.-]+)==([^\s\\]+)", raw_line)
        if package_match:
            flush()
            current_name, current_version = package_match.groups()
            continue
        hash_match = re.search(r"--hash=sha256:([a-f0-9]{64})", raw_line)
        if hash_match and current_name is not None:
            current_hashes.append(hash_match.group(1))
    flush()
    if not parsed:
        raise RuntimeError("FAIL_CLOSED_LOCK_PARSE_ERROR: zero packages")
    return parsed


def _direct_requirements(requirements_path: Path) -> list[Requirement]:
    requirements: list[Requirement] = []
    for raw_line in requirements_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        specs = list(requirement.specifier)
        if len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
            raise RuntimeError(f"FAIL_CLOSED_DIRECT_PIN_ERROR: {line}")
        requirements.append(requirement)
    if not requirements:
        raise RuntimeError("FAIL_CLOSED_DIRECT_PIN_ERROR: no direct requirements")
    return requirements


def _fetch_package(
    canonical_name: str,
    version: str,
    hashes: tuple[str, ...],
    direct_names: set[str],
    compatible: frozenset,
) -> ResolvedPackage:
    url = f"https://pypi.org/pypi/{canonical_name}/{version}/json"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "fi-lock-generator/2"})
        ) as response:
            data = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as exc:
        raise RuntimeError(f"FAIL_CLOSED_METADATA_ERROR: {canonical_name}=={version}: {exc}") from exc

    release_hashes: set[str] = set()
    target_artifacts: list[str] = []
    for artifact in data.get("urls") or []:
        sha256 = (artifact.get("digests") or {}).get("sha256")
        if sha256:
            release_hashes.add(sha256)
        filename = artifact.get("filename", "")
        if artifact.get("yanked", False) or not filename.endswith(".whl"):
            continue
        try:
            _, _, _, wheel_tags = parse_wheel_filename(filename)
        except ValueError:
            continue
        if wheel_tags & compatible:
            target_artifacts.append(filename)

    unknown_hashes = set(hashes) - release_hashes
    if unknown_hashes:
        raise RuntimeError(f"FAIL_CLOSED_HASH_OWNERSHIP_ERROR: {canonical_name}=={version}: {sorted(unknown_hashes)}")
    if not target_artifacts:
        raise RuntimeError(f"FAIL_CLOSED_TARGET_WHEEL_ERROR: {canonical_name}=={version}")
    return ResolvedPackage(
        name=data["info"]["name"],
        version=version,
        hashes=hashes,
        target_artifacts=tuple(sorted(target_artifacts)),
        requires_dist=tuple(data["info"].get("requires_dist") or ()),
        requested=canonical_name in direct_names,
    )


def validate_dependency_graph(
    packages: list[ResolvedPackage], direct_requirements: list[Requirement]
) -> list[dict[str, str]]:
    selected = {package.canonical_name: package for package in packages}
    environment = _target_marker_environment()
    active_extras: dict[str, set[str]] = {}
    pending: list[tuple[str, Requirement]] = [("<direct>", req) for req in direct_requirements]
    edges: list[dict[str, str]] = []
    processed: set[tuple[str, str, tuple[str, ...]]] = set()

    for requirement in direct_requirements:
        active_extras.setdefault(canonicalize_name(requirement.name), set()).update(requirement.extras)

    while pending:
        parent, requirement = pending.pop(0)
        child_name = canonicalize_name(requirement.name)
        contexts = (active_extras.get(parent) or {""}) if parent != "<direct>" else {""}
        if requirement.marker and not any(
            requirement.marker.evaluate({**environment, "extra": extra}) for extra in contexts
        ):
            continue
        package = selected.get(child_name)
        if package is None:
            raise RuntimeError(f"FAIL_CLOSED_UNRESOLVED_EDGE_ERROR: {parent} requires {requirement}")
        if requirement.specifier and Version(package.version) not in requirement.specifier:
            raise RuntimeError(
                f"FAIL_CLOSED_PEP440_ERROR: {parent} requires {requirement}, selected {package.name}=={package.version}"
            )
        active_extras.setdefault(child_name, set()).update(requirement.extras)
        key = (parent, str(requirement), tuple(sorted(active_extras[child_name])))
        if key in processed:
            continue
        processed.add(key)
        edges.append(
            {
                "package": package.name,
                "selected_version": package.version,
                "required_by": parent,
                "constraint": str(requirement.specifier) or "*",
                "constraint_result": "PASS",
            }
        )
        pending.extend((child_name, Requirement(text)) for text in package.requires_dist)
    return edges


def _write_manifest(packages: list[ResolvedPackage], edges: list[dict[str, str]], path: Path) -> None:
    payload = {
        "schemaVersion": 2,
        "resolver": {"name": "uv", "version": UV_VERSION, "excludeNewer": RESOLUTION_CUTOFF},
        "target": {
            "platform": "linux/amd64",
            "uvPlatform": TARGET_UV_PLATFORM,
            "pythonVersion": TARGET_PYTHON_VERSION,
            "abi": TARGET_ABI,
        },
        "packages": [
            {
                "package": package.name,
                "version": package.version,
                "direct": package.requested,
                "hashes": list(package.hashes),
                "targetArtifacts": list(package.target_artifacts),
            }
            for package in sorted(packages, key=lambda item: item.canonical_name)
        ],
        "edges": edges,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def generate_lock(api_dir: Path, output_path: Path, manifest_path: Path) -> None:
    requirements_path = api_dir / REQUIREMENTS_IN_NAME
    direct_requirements = _direct_requirements(requirements_path)
    with tempfile.NamedTemporaryFile(suffix=".lock", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    try:
        _compile_lock(requirements_path, temporary_path)
        parsed = _parse_lock(temporary_path)
        direct_names = {str(canonicalize_name(requirement.name)) for requirement in direct_requirements}
        compatible = _target_tags()
        packages = [
            _fetch_package(name, version, hashes, direct_names, compatible)
            for name, (version, hashes) in sorted(parsed.items())
        ]
        edges = validate_dependency_graph(packages, direct_requirements)
        output_path.write_text(temporary_path.read_text())
        _write_manifest(packages, edges, manifest_path)
    finally:
        temporary_path.unlink(missing_ok=True)
    print(f"SUCCESS: uv resolved {len(packages)} packages and validated {len(edges)} PEP 440 edges.")


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    api = root / "services" / "api"
    try:
        generate_lock(
            api,
            api / "requirements-migration.lock",
            api / "requirements-migration.manifest.json",
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
