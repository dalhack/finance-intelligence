enum ClarificationCode {
  INSTITUTION_REQUIRED,
  REPORTING_PERIOD_REQUIRED,
  REPORTING_BASIS_REQUIRED,
  MEASURE_REQUIRED,
  DOCUMENT_SCOPE_REQUIRED,
  COMPARISON_SCOPE_AMBIGUOUS,
  UNSUPPORTED_REQUEST_SCOPE,
}

enum ClarificationStatus {
  AWAITING_CLARIFICATION,
  CLARIFICATION_RECEIVED,
  CLARIFICATION_EXPIRED,
  CLARIFICATION_CANCELLED,
}

class ClarificationOptionModel {
  final String id;
  final String label;
  final String? value;

  ClarificationOptionModel({
    required this.id,
    required this.label,
    this.value,
  });

  factory ClarificationOptionModel.fromJson(Map<String, dynamic> json) {
    return ClarificationOptionModel(
      id: json['id'] as String? ?? '',
      label: json['label'] as String? ?? '',
      value: json['value'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'label': label,
        if (value != null) 'value': value,
      };
}

class ClarificationModel {
  final String id;
  final String analysisJobId;
  final ClarificationCode clarificationCode;
  final String promptKey;
  final String question;
  final Map<String, dynamic> allowedResponseSchema;
  final List<ClarificationOptionModel> options;
  final ClarificationStatus status;
  final String requestedAt;
  final String? expiresAt;

  ClarificationModel({
    required this.id,
    required this.analysisJobId,
    required this.clarificationCode,
    required this.promptKey,
    required this.question,
    required this.allowedResponseSchema,
    this.options = const [],
    required this.status,
    required this.requestedAt,
    this.expiresAt,
  });

  factory ClarificationModel.fromJson(Map<String, dynamic> json) {
    final rawCode =
        json['clarification_code'] as String? ?? 'UNSUPPORTED_REQUEST_SCOPE';
    final code = ClarificationCode.values.firstWhere(
      (e) => e.name == rawCode,
      orElse: () => ClarificationCode.UNSUPPORTED_REQUEST_SCOPE,
    );

    final rawStatus = json['status'] as String? ?? 'AWAITING_CLARIFICATION';
    final status = ClarificationStatus.values.firstWhere(
      (e) => e.name == rawStatus,
      orElse: () => ClarificationStatus.AWAITING_CLARIFICATION,
    );

    final optionsRaw = json['options'] as List<dynamic>? ?? [];
    final optionsList = optionsRaw
        .map(
            (e) => ClarificationOptionModel.fromJson(e as Map<String, dynamic>))
        .toList();

    return ClarificationModel(
      id: json['id'] as String? ?? '',
      analysisJobId: json['analysis_job_id'] as String? ??
          json['analysisJobId'] as String? ??
          '',
      clarificationCode: code,
      promptKey: json['prompt_key'] as String? ??
          json['promptKey'] as String? ??
          'clarification.default',
      question:
          json['question'] as String? ?? 'Analiz için ek bilgi gereklidir.',
      allowedResponseSchema:
          json['allowed_response_schema'] as Map<String, dynamic>? ??
              json['allowedResponseSchema'] as Map<String, dynamic>? ??
              {},
      options: optionsList,
      status: status,
      requestedAt: json['requested_at'] as String? ??
          json['requestedAt'] as String? ??
          '',
      expiresAt: json['expires_at'] as String? ?? json['expiresAt'] as String?,
    );
  }
}

class ClarificationResponseRequest {
  final String clarificationId;
  final String idempotencyKey;
  final Map<String, dynamic> responsePayload;

  ClarificationResponseRequest({
    required this.clarificationId,
    required this.idempotencyKey,
    required this.responsePayload,
  });

  Map<String, dynamic> toJson() {
    // Sanitization check: Ensure no forbidden keys exist in request
    final forbiddenKeys = {
      'organization_id',
      'user_id',
      'role',
      'permission',
      'api_key',
      'sql',
      'shell',
      'python',
      'system_prompt'
    };
    for (final k in responsePayload.keys) {
      if (forbiddenKeys.contains(k.toLowerCase())) {
        throw ArgumentError(
            "Forbidden security parameter in clarification response: '$k'");
      }
    }

    return {
      'clarification_id': clarificationId,
      'idempotency_key': idempotencyKey,
      'response_payload': responsePayload,
    };
  }
}

class ClarificationCancelRequest {
  final String clarificationId;
  final String idempotencyKey;
  final String reasonCode;

  ClarificationCancelRequest({
    required this.clarificationId,
    required this.idempotencyKey,
    this.reasonCode = "USER_CANCELLED",
  });

  Map<String, dynamic> toJson() => {
        'clarification_id': clarificationId,
        'idempotency_key': idempotencyKey,
        'reason_code': reasonCode,
      };
}
