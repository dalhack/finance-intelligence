class UserSummary {
  final String userId;
  final String externalSubject;
  final String displayName;

  const UserSummary({
    required this.userId,
    required this.externalSubject,
    required this.displayName,
  });

  factory UserSummary.fromJson(Map<String, dynamic> json) {
    return UserSummary(
      userId: json['user_id']?.toString() ?? json['id']?.toString() ?? '',
      externalSubject: json['external_subject']?.toString() ?? '',
      displayName: json['display_name']?.toString() ?? '',
    );
  }
}

class OrganizationSummary {
  final String organizationId;
  final String name;
  final String slug;

  const OrganizationSummary({
    required this.organizationId,
    required this.name,
    required this.slug,
  });

  factory OrganizationSummary.fromJson(Map<String, dynamic> json) {
    return OrganizationSummary(
      organizationId:
          json['organization_id']?.toString() ?? json['id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      slug: json['slug']?.toString() ?? '',
    );
  }
}

class Pagination {
  final int page;
  final int pageSize;
  final int totalRows;
  final int totalPages;
  final bool hasNext;
  final bool hasPrevious;

  const Pagination({
    required this.page,
    required this.pageSize,
    required this.totalRows,
    required this.totalPages,
    required this.hasNext,
    required this.hasPrevious,
  });

  factory Pagination.fromJson(Map<String, dynamic> json) {
    return Pagination(
      page: json['page'] as int? ?? 1,
      pageSize: json['page_size'] as int? ?? 20,
      totalRows: json['total_rows'] as int? ?? 0,
      totalPages: json['total_pages'] as int? ?? 1,
      hasNext: json['has_next'] as bool? ?? false,
      hasPrevious: json['has_previous'] as bool? ?? false,
    );
  }

  Map<String, dynamic> toJson() => {
        'page': page,
        'page_size': pageSize,
        'total_rows': totalRows,
        'total_pages': totalPages,
        'has_next': hasNext,
        'has_previous': hasPrevious,
      };
}

class UploadSession {
  final String uploadSessionId;
  final String organizationId;
  final String documentId;
  final String documentVersionId;
  final String status;
  final int expectedSizeBytes;

  const UploadSession({
    required this.uploadSessionId,
    required this.organizationId,
    required this.documentId,
    required this.documentVersionId,
    required this.status,
    required this.expectedSizeBytes,
  });

  factory UploadSession.fromJson(Map<String, dynamic> json) {
    return UploadSession(
      uploadSessionId:
          json['upload_session_id']?.toString() ?? json['id']?.toString() ?? '',
      organizationId: json['organization_id']?.toString() ?? '',
      documentId: json['document_id']?.toString() ?? '',
      documentVersionId: json['document_version_id']?.toString() ?? '',
      status: json['status']?.toString() ?? 'CREATED',
      expectedSizeBytes: json['expected_size_bytes'] as int? ?? 0,
    );
  }
}

class DocumentItem {
  final String documentId;
  final String organizationId;
  final String displayName;

  const DocumentItem({
    required this.documentId,
    required this.organizationId,
    required this.displayName,
  });

  factory DocumentItem.fromJson(Map<String, dynamic> json) {
    return DocumentItem(
      documentId: json['id']?.toString() ?? '',
      organizationId: json['organization_id']?.toString() ?? '',
      displayName: json['display_name']?.toString() ?? '',
    );
  }
}

class IngestionJob {
  final String jobId;
  final String documentId;
  final String organizationId;
  final String documentVersionId;
  final String status;
  final String? failureReason;
  final String? failureCode;

  const IngestionJob({
    required this.jobId,
    this.documentId = '',
    required this.organizationId,
    required this.documentVersionId,
    required this.status,
    this.failureReason,
    this.failureCode,
  });

  static const List<String> canonicalTerminalStatuses = [
    'PROCESSED_SUCCESS',
    'PROCESSED_REVIEW_REQUIRED',
    'PROCESSED_REJECTED',
    'PROCESSED_FAILED',
  ];

  bool get isTerminal => canonicalTerminalStatuses.contains(status);

  factory IngestionJob.fromJson(Map<String, dynamic> json) {
    final st = json['status']?.toString() ?? 'PENDING';
    const knownStatuses = [
      'PENDING',
      'CLAIMED',
      'PARSING',
      'EXTRACTING',
      'PARSING_COMPLETED',
      'REVIEW_REQUIRED',
      'PROCESSED_SUCCESS',
      'PROCESSED_REVIEW_REQUIRED',
      'PROCESSED_REJECTED',
      'PROCESSED_FAILED',
    ];
    if (!knownStatuses.contains(st)) {
      throw FormatException(
          'UNSUPPORTED_JOB_STATUS: Ingestion job status "$st" is unsupported.');
    }
    return IngestionJob(
      jobId: json['ingestion_job_id']?.toString() ??
          json['id']?.toString() ??
          json['job_id']?.toString() ??
          '',
      documentId: json['document_id']?.toString() ?? '',
      organizationId: json['organization_id']?.toString() ?? '',
      documentVersionId: json['document_version_id']?.toString() ?? '',
      status: st,
      failureReason: json['failure_reason']?.toString(),
      failureCode: json['failure_code']?.toString(),
    );
  }
}

class SemanticMeasureSelector {
  final String semanticMeasureCode;
  final String preferredOrigin;

  const SemanticMeasureSelector({
    required this.semanticMeasureCode,
    this.preferredOrigin = 'AUTO',
  });

  Map<String, dynamic> toJson() => {
        'semantic_measure_code': semanticMeasureCode,
        'preferred_origin': preferredOrigin,
      };
}

class ComparisonRequest {
  final List<String> institutionIds;
  final List<SemanticMeasureSelector> semanticMeasures;
  final List<String> reportingPeriodIds;
  final String reportingBasis;
  final String currency;
  final String displayScale;
  final String valueSourcePolicy;
  final String? sortMeasureCode;
  final String? sortOrigin;
  final String sortDirection;
  final String topNScope;
  final int? topN;
  final int page;
  final int pageSize;

  const ComparisonRequest({
    required this.institutionIds,
    required this.semanticMeasures,
    required this.reportingPeriodIds,
    required this.reportingBasis,
    this.currency = 'TRY',
    this.displayScale = 'MILLION',
    this.valueSourcePolicy = 'PREFER_SOURCE_REPORTED',
    this.sortMeasureCode,
    this.sortOrigin,
    this.sortDirection = 'desc',
    this.topNScope = 'INSTITUTIONS_PER_PERIOD',
    this.topN,
    this.page = 1,
    this.pageSize = 20,
  });

  Map<String, dynamic> toJson() => {
        'institution_ids': institutionIds,
        'semantic_measures': semanticMeasures.map((s) => s.toJson()).toList(),
        'reporting_period_ids': reportingPeriodIds,
        'reporting_basis': reportingBasis,
        'currency': currency,
        'display_scale': displayScale,
        'value_source_policy': valueSourcePolicy,
        if (sortMeasureCode != null) 'sort_measure_code': sortMeasureCode,
        if (sortOrigin != null) 'sort_origin': sortOrigin,
        'sort_direction': sortDirection,
        'top_n_scope': topNScope,
        if (topN != null) 'top_n': topN,
        'page': page,
        'page_size': pageSize,
      };
}

class DataQualitySummary {
  final int expectedCells;
  final int populatedCells;
  final int missingSourceCells;
  final int excludedIneligibleCells;
  final int excludedMismatchCells;
  final int warningCells;
  final int sourceReportedCount;
  final int systemDerivedCount;
  final int reconciliationWarningCount;
  final String completenessPercentage;

  const DataQualitySummary({
    required this.expectedCells,
    required this.populatedCells,
    required this.missingSourceCells,
    required this.excludedIneligibleCells,
    required this.excludedMismatchCells,
    required this.warningCells,
    required this.sourceReportedCount,
    required this.systemDerivedCount,
    required this.reconciliationWarningCount,
    required this.completenessPercentage,
  });

  factory DataQualitySummary.fromJson(Map<String, dynamic> json) {
    final exp = json['expected_cells'] as int? ?? 0;
    final pop = json['populated_cells'] as int? ?? 0;
    final miss = json['missing_source_cells'] as int? ?? 0;
    final inel = json['excluded_ineligible_cells'] as int? ?? 0;
    final mism = json['excluded_mismatch_cells'] as int? ?? 0;

    final sum = pop + miss + inel + mism;
    if (exp != sum) {
      throw FormatException(
          'DATA_QUALITY_INVARIANT_VIOLATED: expected ($exp) != sum ($sum).');
    }

    return DataQualitySummary(
      expectedCells: exp,
      populatedCells: pop,
      missingSourceCells: miss,
      excludedIneligibleCells: inel,
      excludedMismatchCells: mism,
      warningCells: json['warning_cells'] as int? ?? 0,
      sourceReportedCount: json['source_reported_count'] as int? ?? 0,
      systemDerivedCount: json['system_derived_count'] as int? ?? 0,
      reconciliationWarningCount:
          json['reconciliation_warning_count'] as int? ?? 0,
      completenessPercentage:
          json['completeness_percentage']?.toString() ?? '0.00',
    );
  }
}

class DatasetRowCell {
  final String measureCode;
  final String semanticMeasureCode;
  final String canonicalValue;
  final String displayValue;
  final String valueOrigin;
  final String? factId;
  final String? calculationId;
  final String? evidenceId;
  final String? reconciliationStatus;
  final bool warningFlag;
  final String? warningCode;

  const DatasetRowCell({
    required this.measureCode,
    required this.semanticMeasureCode,
    required this.canonicalValue,
    required this.displayValue,
    required this.valueOrigin,
    this.factId,
    this.calculationId,
    this.evidenceId,
    this.reconciliationStatus,
    this.warningFlag = false,
    this.warningCode,
  });

  factory DatasetRowCell.fromJson(Map<String, dynamic> json) {
    return DatasetRowCell(
      measureCode: json['measure_code']?.toString() ?? '',
      semanticMeasureCode: json['semantic_measure_code']?.toString() ?? '',
      canonicalValue: json['canonical_value']?.toString() ?? '0',
      displayValue: json['display_value']?.toString() ?? '0',
      valueOrigin: json['value_origin']?.toString() ?? 'SOURCE_REPORTED',
      factId: json['fact_id']?.toString(),
      calculationId: json['calculation_id']?.toString(),
      evidenceId: json['evidence_id']?.toString(),
      reconciliationStatus: json['reconciliation_status']?.toString(),
      warningFlag: json['warning_flag'] as bool? ?? false,
      warningCode: json['warning_code']?.toString(),
    );
  }
}

class DatasetRow {
  final String rowId;
  final String institutionId;
  final String institutionName;
  final String reportingPeriodId;
  final String periodLabel;
  final String reportingBasis;
  final Map<String, DatasetRowCell> cells;

  const DatasetRow({
    required this.rowId,
    required this.institutionId,
    required this.institutionName,
    required this.reportingPeriodId,
    required this.periodLabel,
    required this.reportingBasis,
    required this.cells,
  });

  factory DatasetRow.fromJson(Map<String, dynamic> json) {
    final rawCells = json['cells'] as Map<String, dynamic>? ?? {};
    final mappedCells = rawCells.map(
      (key, val) =>
          MapEntry(key, DatasetRowCell.fromJson(val as Map<String, dynamic>)),
    );
    return DatasetRow(
      rowId: json['row_id']?.toString() ?? '',
      institutionId: json['institution_id']?.toString() ?? '',
      institutionName: json['institution_name']?.toString() ?? '',
      reportingPeriodId: json['reporting_period_id']?.toString() ?? '',
      periodLabel: json['period_label']?.toString() ?? '',
      reportingBasis: json['reporting_basis']?.toString() ?? 'SOLO',
      cells: mappedCells,
    );
  }
}

class ResultDataset {
  final String resultDatasetId;
  final String schemaVersion;
  final DataQualitySummary dataQualitySummary;
  final List<DatasetRow> rows;
  final Pagination pagination;

  const ResultDataset({
    required this.resultDatasetId,
    required this.schemaVersion,
    required this.dataQualitySummary,
    required this.rows,
    required this.pagination,
  });

  factory ResultDataset.fromJson(Map<String, dynamic> json) {
    final ver = json['schema_version']?.toString() ?? '';
    if (ver != '3.0.0' && ver != '2.0.0' && ver != '1.0.0') {
      throw FormatException(
          'DATASET_SCHEMA_VERSION_UNSUPPORTED: Unsupported dataset schema version "$ver".');
    }
    final rawRows = json['rows'] as List<dynamic>? ?? [];
    return ResultDataset(
      resultDatasetId: json['result_dataset_id']?.toString() ?? '',
      schemaVersion: ver,
      dataQualitySummary: DataQualitySummary.fromJson(
          json['data_quality_summary'] as Map<String, dynamic>),
      rows: rawRows
          .map((r) => DatasetRow.fromJson(r as Map<String, dynamic>))
          .toList(),
      pagination:
          Pagination.fromJson(json['pagination'] as Map<String, dynamic>),
    );
  }
}

class EvidenceDetail {
  final String evidenceId;
  final String? documentTitle;
  final String documentVersionId;
  final String? mimeType;
  final bool mimeVerified;
  final int? pageNumber;
  final String? sheetName;
  final String? cellCoordinate;
  final int? rowIndex;
  final int? columnIndex;
  final Map<String, dynamic>? boundingBox;
  final String? sanitizedSnippet;
  final String classification;
  final bool isMasked;

  const EvidenceDetail({
    required this.evidenceId,
    this.documentTitle,
    required this.documentVersionId,
    this.mimeType,
    required this.mimeVerified,
    this.pageNumber,
    this.sheetName,
    this.cellCoordinate,
    this.rowIndex,
    this.columnIndex,
    this.boundingBox,
    this.sanitizedSnippet,
    required this.classification,
    required this.isMasked,
  });

  factory EvidenceDetail.fromJson(Map<String, dynamic> json) {
    return EvidenceDetail(
      evidenceId: json['evidence_id']?.toString() ?? '',
      documentTitle: json['document_title']?.toString(),
      documentVersionId: json['document_version_id']?.toString() ?? '',
      mimeType: json['mime_type']?.toString(),
      mimeVerified: json['mime_verified'] as bool? ?? false,
      pageNumber: json['page_number'] as int?,
      sheetName: json['sheet_name']?.toString(),
      cellCoordinate: json['cell_coordinate']?.toString(),
      rowIndex: json['row_index'] as int?,
      columnIndex: json['column_index'] as int?,
      boundingBox: json['bounding_box'] as Map<String, dynamic>?,
      sanitizedSnippet: json['sanitized_snippet']?.toString(),
      classification: json['classification']?.toString() ?? 'CONFIDENTIAL',
      isMasked: json['is_masked'] as bool? ?? false,
    );
  }
}

class TableColumn {
  final String key;
  final String title;
  final String dataType;
  final String unitLabel;

  const TableColumn({
    required this.key,
    required this.title,
    required this.dataType,
    required this.unitLabel,
  });

  factory TableColumn.fromJson(Map<String, dynamic> json) {
    return TableColumn(
      key: json['key']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      dataType: json['data_type']?.toString() ?? 'string',
      unitLabel: json['unit_label']?.toString() ?? '',
    );
  }
}

class TableSpec {
  final String resultDatasetId;
  final String schemaVersion;
  final List<TableColumn> columns;
  final List<Map<String, dynamic>> rows;
  final Pagination pagination;

  const TableSpec({
    required this.resultDatasetId,
    required this.schemaVersion,
    required this.columns,
    required this.rows,
    required this.pagination,
  });

  factory TableSpec.fromJson(Map<String, dynamic> json) {
    return TableSpec(
      resultDatasetId: json['result_dataset_id']?.toString() ?? '',
      schemaVersion: json['schema_version']?.toString() ?? '3.0.0',
      columns: (json['columns'] as List<dynamic>?)
              ?.map((c) => TableColumn.fromJson(c as Map<String, dynamic>))
              .toList() ??
          [],
      rows: (json['rows'] as List<dynamic>?)
              ?.map((r) => r as Map<String, dynamic>)
              .toList() ??
          [],
      pagination: Pagination.fromJson(
        json['pagination'] as Map<String, dynamic>? ?? {},
      ),
    );
  }
}

class AnalysisJobModel {
  final String id;
  final String organizationId;
  final String userId;
  final String status;
  final String requestPrompt;
  final Map<String, dynamic> normalizedRequest;
  final String createdAt;
  final String updatedAt;

  const AnalysisJobModel({
    required this.id,
    required this.organizationId,
    required this.userId,
    required this.status,
    required this.requestPrompt,
    required this.normalizedRequest,
    required this.createdAt,
    required this.updatedAt,
  });

  factory AnalysisJobModel.fromJson(Map<String, dynamic> json) {
    return AnalysisJobModel(
      id: json['id']?.toString() ?? '',
      organizationId: json['organization_id']?.toString() ?? '',
      userId: json['user_id']?.toString() ?? '',
      status: json['status']?.toString() ?? 'RECEIVED',
      requestPrompt: json['request_prompt']?.toString() ?? '',
      normalizedRequest:
          json['normalized_request'] as Map<String, dynamic>? ?? {},
      createdAt: json['created_at']?.toString() ?? '',
      updatedAt: json['updated_at']?.toString() ?? '',
    );
  }
}

class AnalysisDomainEventModel {
  final String eventType;
  final int sequence;
  final String analysisId;
  final Map<String, dynamic> payload;

  const AnalysisDomainEventModel({
    required this.eventType,
    required this.sequence,
    required this.analysisId,
    required this.payload,
  });

  factory AnalysisDomainEventModel.fromSseLine({
    required String type,
    required String id,
    required Map<String, dynamic> data,
  }) {
    const allowedEvents = [
      'analysis.accepted',
      'analysis.state_changed',
      'analysis.plan_ready',
      'analysis.tool_started',
      'analysis.tool_completed',
      'analysis.clarification_required',
      'analysis.clarification_received',
      'analysis.resumed',
      'analysis.clarification_expired',
      'analysis.warning',
      'analysis.partial_result',
      'analysis.completed',
      'analysis.failed',
      'analysis.cancelled',
      'heartbeat',
    ];

    if (!allowedEvents.contains(type)) {
      throw FormatException(
          'UNSUPPORTED_ANALYSIS_EVENT: Event type "$type" is not allowed.');
    }

    return AnalysisDomainEventModel(
      eventType: type,
      sequence: int.tryParse(id) ?? 0,
      analysisId: data['analysis_job_id']?.toString() ??
          data['job_id']?.toString() ??
          '',
      payload: data,
    );
  }
}

class AnalysisCreateRequestModel {
  final String userQuery;
  final List<String>? selectedDocumentIds;
  final String idempotencyKey;

  const AnalysisCreateRequestModel({
    required this.userQuery,
    this.selectedDocumentIds,
    required this.idempotencyKey,
  });

  Map<String, dynamic> toJson() {
    return {
      'prompt': userQuery,
      if (selectedDocumentIds != null)
        'selected_document_ids': selectedDocumentIds,
      'idempotency_key': idempotencyKey,
    };
  }
}
