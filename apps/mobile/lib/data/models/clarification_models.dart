enum ClarificationCode {
  institutionRequired,
  reportingPeriodRequired,
  reportingBasisRequired,
  measureRequired,
  documentScopeRequired,
  comparisonScopeAmbiguous,
  unsupportedRequestScope;

  String get wireValue {
    switch (this) {
      case ClarificationCode.institutionRequired:
        return 'INSTITUTION_REQUIRED';
      case ClarificationCode.reportingPeriodRequired:
        return 'REPORTING_PERIOD_REQUIRED';
      case ClarificationCode.reportingBasisRequired:
        return 'REPORTING_BASIS_REQUIRED';
      case ClarificationCode.measureRequired:
        return 'MEASURE_REQUIRED';
      case ClarificationCode.documentScopeRequired:
        return 'DOCUMENT_SCOPE_REQUIRED';
      case ClarificationCode.comparisonScopeAmbiguous:
        return 'COMPARISON_SCOPE_AMBIGUOUS';
      case ClarificationCode.unsupportedRequestScope:
        return 'UNSUPPORTED_REQUEST_SCOPE';
    }
  }

  static ClarificationCode fromWire(String? raw) {
    switch (raw) {
      case 'INSTITUTION_REQUIRED':
        return ClarificationCode.institutionRequired;
      case 'REPORTING_PERIOD_REQUIRED':
        return ClarificationCode.reportingPeriodRequired;
      case 'REPORTING_BASIS_REQUIRED':
        return ClarificationCode.reportingBasisRequired;
      case 'MEASURE_REQUIRED':
        return ClarificationCode.measureRequired;
      case 'DOCUMENT_SCOPE_REQUIRED':
        return ClarificationCode.documentScopeRequired;
      case 'COMPARISON_SCOPE_AMBIGUOUS':
        return ClarificationCode.comparisonScopeAmbiguous;
      default:
        return ClarificationCode.unsupportedRequestScope;
    }
  }
}

enum ClarificationStatus {
  awaitingClarification,
  clarificationReceived,
  clarificationExpired,
  clarificationCancelled;

  String get wireValue {
    switch (this) {
      case ClarificationStatus.awaitingClarification:
        return 'AWAITING_CLARIFICATION';
      case ClarificationStatus.clarificationReceived:
        return 'CLARIFICATION_RECEIVED';
      case ClarificationStatus.clarificationExpired:
        return 'CLARIFICATION_EXPIRED';
      case ClarificationStatus.clarificationCancelled:
        return 'CLARIFICATION_CANCELLED';
    }
  }

  static ClarificationStatus fromWire(String? raw) {
    switch (raw) {
      case 'CLARIFICATION_RECEIVED':
        return ClarificationStatus.clarificationReceived;
      case 'CLARIFICATION_EXPIRED':
        return ClarificationStatus.clarificationExpired;
      case 'CLARIFICATION_CANCELLED':
        return ClarificationStatus.clarificationCancelled;
      default:
        return ClarificationStatus.awaitingClarification;
    }
  }
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
    final rawCode = json['clarification_code'] as String? ??
        json['clarificationCode'] as String?;
    final code = ClarificationCode.fromWire(rawCode);

    final rawStatus = json['status'] as String?;
    final status = ClarificationStatus.fromWire(rawStatus);

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
