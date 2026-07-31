import 'dart:io';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Production Hardcoded Data & Mock Removal Scanner', () {
    test(
        'Production lib code contains zero hardcoded _mockDocuments or hardcoded _candidates arrays',
        () {
      final libDir = Directory('lib');
      expect(libDir.existsSync(), isTrue);

      final files = libDir
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'));
      final forbiddenPatterns = [
        '_mockDocuments',
        '_candidates = [',
        'inst-garan:period-2025-q4',
      ];

      final violations = <String>[];

      for (final file in files) {
        final content = file.readAsStringSync();
        for (final pattern in forbiddenPatterns) {
          if (content.contains(pattern)) {
            violations.add(
                '${file.path} contains forbidden hardcoded pattern "$pattern"');
          }
        }
      }

      expect(violations, isEmpty,
          reason:
              'Production lib code must contain zero hardcoded demo data: ${violations.join(', ')}');
    });
  });
}
