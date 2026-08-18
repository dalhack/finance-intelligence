import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Document ingestion status', () {
    test('reads the latest version status from the API payload', () {
      final doc = DocumentItem.fromJson(const {
        'id': 'doc-1',
        'organization_id': 'org-1',
        'display_name': 'Solo_VAKBN_31.03.2026__TR.pdf',
        'latest_version': {'ingestion_status': 'PARSING'},
      });
      expect(doc.ingestionStatus, 'PARSING');
      expect(doc.isProcessing, isTrue);
    });

    test('a document without a version yet still reads as processing', () {
      final doc = DocumentItem.fromJson(const {
        'id': 'doc-1',
        'organization_id': 'org-1',
        'display_name': 'x.pdf',
      });
      expect(doc.ingestionStatus, '');
      expect(doc.isProcessing, isTrue,
          reason: 'the UI must keep watching instead of claiming completion');
    });

    test('terminal states stop the watch', () {
      for (final status in [
        'COMPLETED',
        'COMPLETED_WITH_WARNINGS',
        'AWAITING_REVIEW',
        'FAILED',
        'REJECTED',
      ]) {
        final doc = DocumentItem.fromJson({
          'id': 'doc-1',
          'organization_id': 'org-1',
          'display_name': 'x.pdf',
          'latest_version': {'ingestion_status': status},
        });
        expect(doc.isProcessing, isFalse, reason: '$status is terminal');
      }
    });
  });
}
