import pytest
from app.routers.analyses import AnalysisResultDTO


@pytest.mark.unit
def test_result_contract_carries_render_ready_blocks():
    """A client must be able to draw the answer without parsing prose. The
    contract therefore exposes the narrative and the verified dataset's table
    and chart specifications as separate, typed fields."""
    fields = AnalysisResultDTO.model_fields
    for required in (
        "analysis_id",
        "snapshot_id",
        "request_prompt",
        "executive_summary",
        "result_dataset_id",
        "table_spec",
        "chart_specs",
        "data_quality_summary",
        "warnings",
    ):
        assert required in fields, f"{required} missing from the analysis result contract"


@pytest.mark.unit
def test_result_contract_tolerates_an_analysis_without_a_dataset():
    """A completed analysis that produced no dataset must still be returnable;
    the client shows the narrative and no table rather than failing."""
    from datetime import UTC, datetime
    from uuid import uuid4

    dto = AnalysisResultDTO(
        analysis_id=uuid4(),
        snapshot_id=uuid4(),
        schema_version="1.0.0",
        created_at=datetime.now(UTC),
        request_prompt="Toplam aktifleri karşılaştır",
        executive_summary="Analiz tamamlandı.",
    )
    assert dto.table_spec is None
    assert dto.chart_specs == []
    assert dto.result_dataset_id is None
