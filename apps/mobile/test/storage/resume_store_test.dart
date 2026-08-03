import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/data/storage/analysis_resume_store.dart';

void main() {
  group('AnalysisResumeStore & Record Tests', () {
    test('AnalysisResumeRecord serialization round-trip', () {
      final fingerprint = computeSessionBindingHash("user_subject_123");
      final record = AnalysisResumeRecord(
        analysisId: "c794ef64-9b2f-4c12-881a-4d2c88219011",
        lastAppliedSequence: 5,
        lastEventId: "5",
        lifecycleStatus: "NEEDS_CLARIFICATION",
        createdAt: "2026-07-31T15:00:00Z",
        lastConnectedAt: "2026-07-31T15:01:00Z",
        sessionBindingFingerprint: fingerprint,
      );

      final json = record.toJson();
      expect(json['resumeSchemaVersion'], 1);
      expect(json['contractVersion'], "3.0.0");
      expect(json['analysisId'], "c794ef64-9b2f-4c12-881a-4d2c88219011");
      expect(json['lastAppliedSequence'], 5);
      expect(json['sessionBindingFingerprint'], fingerprint);

      // Verify ZERO sensitive fields exist in serialized record JSON
      final forbiddenFields = [
        'authorization',
        'token',
        'prompt',
        'response',
        'summary',
        'title',
        'organizationId',
        'userId',
        'tenantId',
        'apiKey',
      ];
      for (final forbidden in forbiddenFields) {
        expect(json.containsKey(forbidden), false,
            reason: "Resume record contains forbidden key '$forbidden'");
      }

      final restored = AnalysisResumeRecord.fromJson(json);
      expect(restored.analysisId, record.analysisId);
      expect(restored.lastAppliedSequence, record.lastAppliedSequence);
    });

    test(
        'InMemoryAnalysisResumeStore enforces sequence monotonicity & session mismatch',
        () async {
      final store = InMemoryAnalysisResumeStore();
      final fp1 = computeSessionBindingHash("sub1");
      final fp2 = computeSessionBindingHash("sub2");

      final rec = AnalysisResumeRecord(
        analysisId: "job-100",
        lastAppliedSequence: 10,
        lifecycleStatus: "UNDERSTANDING",
        createdAt: "2026-07-31T15:00:00Z",
        lastConnectedAt: "2026-07-31T15:01:00Z",
        sessionBindingFingerprint: fp1,
      );

      await store.write(rec);
      expect((await store.read())?.lastAppliedSequence, 10);

      // Attempt regression sequence update -> Ignored
      await store.updateSequence(8, "8");
      expect((await store.read())?.lastAppliedSequence, 10);

      // Monotonic sequence update -> Accepted
      await store.updateSequence(12, "12");
      expect((await store.read())?.lastAppliedSequence, 12);

      // Session mismatch check -> Clears record
      await store.clearIfSessionMismatch(fp2);
      expect(await store.read(), null);
    });
  });
}
