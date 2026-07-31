import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/data/storage/analysis_resume_store.dart';

void main() {
  group('Resume Store Forbidden Field Scanner', () {
    test(
        'Ensures AnalysisResumeRecord serialization contains zero forbidden sensitive fields',
        () {
      final fp = computeSessionBindingHash("scanner_subject_1");
      final record = AnalysisResumeRecord(
        analysisId: "c794ef64-9b2f-4c12-881a-4d2c88219011",
        lastAppliedSequence: 3,
        lastEventId: "3",
        lifecycleStatus: "NEEDS_CLARIFICATION",
        createdAt: "2026-07-31T15:00:00Z",
        lastConnectedAt: "2026-07-31T15:01:00Z",
        sessionBindingFingerprint: fp,
      );

      final json = record.toJson();

      final forbiddenFields = [
        'token',
        'authorization',
        'appCheck',
        'refreshToken',
        'prompt',
        'query',
        'response',
        'result',
        'executiveSummary',
        'financialValue',
        'evidence',
        'snippet',
        'documentTitle',
        'organizationId',
        'tenantId',
        'userId',
        'provider',
        'modelId',
        'apiKey',
        'tableSpec',
        'chartSpec',
        'clarificationResponse',
      ];

      for (final forbidden in forbiddenFields) {
        expect(
          json.containsKey(forbidden),
          false,
          reason:
              "Resume store payload must NOT contain forbidden field '$forbidden'",
        );
      }
    });

    test('Validates envelope checksum verification and corruption recovery',
        () {
      final fp = computeSessionBindingHash("scanner_subject_2");
      final record = AnalysisResumeRecord(
        analysisId: "job-valid-123",
        lastAppliedSequence: 1,
        lifecycleStatus: "UNDERSTANDING",
        createdAt: "2026-07-31T15:00:00Z",
        lastConnectedAt: "2026-07-31T15:01:00Z",
        sessionBindingFingerprint: fp,
      );

      final json = record.toJson();
      expect(json.containsKey('checksum'), true);

      // Corrupt checksum -> expect FormatException
      json['checksum'] = "invalid_corrupted_checksum_hash";
      expect(() => AnalysisResumeRecord.fromJson(json), throwsFormatException);
    });
  });
}
