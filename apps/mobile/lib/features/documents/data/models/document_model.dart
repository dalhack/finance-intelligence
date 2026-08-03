class DocumentModel {
  final String id;
  final String organizationId;
  final String displayName;
  final String documentType;
  final String classification;
  final String status;
  final String createdAt;
  final String? ingestionStatus;
  final String? extractionStatus;

  DocumentModel({
    required this.id,
    required this.organizationId,
    required this.displayName,
    required this.documentType,
    required this.classification,
    required this.status,
    required this.createdAt,
    this.ingestionStatus,
    this.extractionStatus,
  });

  factory DocumentModel.fromJson(Map<String, dynamic> json) {
    final latestVer = json['latest_version'] as Map<String, dynamic>?;
    return DocumentModel(
      id: json['id'] as String,
      organizationId: json['organization_id'] as String,
      displayName: json['display_name'] as String,
      documentType: json['document_type'] as String? ?? 'GENERAL',
      classification: json['classification'] as String? ?? 'CONFIDENTIAL',
      status: json['status'] as String? ?? 'ACTIVE',
      createdAt: json['created_at'] as String,
      ingestionStatus: latestVer?['ingestion_status'] as String?,
      extractionStatus: latestVer?['extraction_status'] as String?,
    );
  }
}
