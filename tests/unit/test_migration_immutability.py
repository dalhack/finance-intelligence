import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
VERSIONS_DIR = REPO_ROOT / "services" / "api" / "alembic" / "versions"

# Authoritative baseline SHA256 hashes of applied historical migrations (001..025)
HISTORICAL_MIGRATION_HASHES = {
    "001_initial_tenant_schema_and_rls.py": "64264f7f570c9b4be24acc22474f2650f645e0b8987eff7cc67346cf642dd8b6",
    "002_document_ingestion_schema.py": "dc043d7b2236b238345b48a2eaffdcf5976dafd034093c2ef742872f6a5a175a",
    "003_role_separation.py": "bb6fea01cb9d0598733107ef5467ea4e7fc95a311a75158c18c59b2962fbca21",
    "004_revoke_app_user.py": "84eb06011bf11dac1bb57da8b48092688b8e3616bfe6f579d577d9295280152c",
    "005_worker_claim_and_guarded_downgrade.py": "dcc96cc95a384ab22cb909a6dc783d642a7d77b4cce1b3234455ce45db9c68e6",
    "006_status_mapping_and_claim_tokens.py": "3db26f020f7affdbef16e22cedaa920c919355a06128b4731d6991b36efc5f49",
    "007_drop_legacy_claim_overload.py": "090d54d4ea69a050d983b28a0bc227321bfd878e63f9a1f99e59362c346b18ad",
    "008_financial_facts_and_command_envelope.py": "31243d317ec7c0c09a684f4723bc5236a728a1004de807f2a0f3df06c9c7467d",
    "009_command_envelope_and_fact_integrity.py": "ecd19484a3ec122c71fdd188e539bacaf3ac8a1829aad4d69b7ac943f4967eac",
    "010_fact_revision_and_active_uniqueness.py": "db88f6cb2cf59144a250472eeb862c01141a59c00ce04c0b9e5aa5108dccfdde",
    "011_calculation_engine_schema.py": "10aaf4aebf1bdb2b63c9ce4df6f1b9b5d40320ab08c1b30865335928a8a14204",
    "012_calculation_correctness_and_unrounded_result.py": "3ead6c334280877adf58424b52ed4247fba3fd25fea17b6afcd6bfc69b42166b",
    "013_calculation_checksum_and_lineage_hardening.py": "3c3739e5e962d2964a0c08ebdd1c2e8936773843c040bdef28e0bc784b8b316c",
    "014_calculation_identity_and_evidence_integrity.py": "18c51ce0f5ead84dfecccfa3b6dfc151f1d7d6f9fa45977138ff814157c3793e",
    "015_sec_context_calc_integrity.py": "820837b24b99351d85979f687ee7a9d699d43942272db808b1e4a00e1a5f1da6",
    "016_traceability_integrity_repair.py": "88591397a4780cd13de2bafb0273f390e8e043b412de40a4ef783cdfd49284aa",
    "017_comparison_dataset.py": "e418091148f394f15fe0ff697023b29eae96bdeeb0df34651cc098ea71d6ab25",
    "018_comparison_dataset_correctness.py": "d0e52c7217c10dda909d84ba17132061627a86a57d60e7858fe1923c6891a7cf",
    "019_comparison_semantics_and_snapshot_integrity.py": "9b84471659c429464c66d696827ae772087ef3bb84ece662713e37be12e3da0f",
    "020_ai_orchestration_foundation.py": "19191c6431ee8035fdd80f2d2435766de019dbe7a4980d7eec2e72d9027f569e",
    "021_ai_runtime_execution_integrity.py": "066e8c1e0f3efe9e0d22ff486c8a858151fa0be489876eee6d976ca20693362e",
    "022_model_provider_and_analysis_events.py": "b31eae7916f79236a8f36a5594dd67a04e0cae2ce7b1d4ffbc4e2c03ecd88da9",
    "023_analysis_clarification_workflow.py": "69f0b9da5c9a9913e6cfc813dad56146215b9fb3310432e6202b33ef15afc469",
    "024_maintenance_scheduler_and_operational_resilience.py": "26077eb15b670e92b1d39c8e36093b7bf165a041f76463271d496054f2919d54",
    "025_distributed_provider_circuit_breaker.py": "214a27a47bcbddc659e88d8438c4d9cb6bfc9fef54d7f267c458b78a940ed286",
}


def test_historical_migration_immutability_checksums():
    """Verifies that all historical applied migrations (001..025) remain 100% byte-level immutable."""
    for filename, expected_hash in HISTORICAL_MIGRATION_HASHES.items():
        file_path = VERSIONS_DIR / filename
        assert file_path.exists(), f"HISTORICAL_MIGRATION_MISSING: {filename} was deleted!"
        actual_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
        assert actual_hash == expected_hash, (
            f"HISTORICAL_MIGRATION_MODIFIED: {filename} has been modified! Expected {expected_hash}, got {actual_hash}"
        )
