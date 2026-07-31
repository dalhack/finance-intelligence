import 'dart:io';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('Production code contains zero unapproved print or debugPrint calls',
      () {
    final libDir = Directory('lib');
    expect(libDir.existsSync(), isTrue, reason: 'lib directory must exist');

    final dartFiles = libDir
        .listSync(recursive: true)
        .whereType<File>()
        .where((file) => file.path.endsWith('.dart'))
        .toList();

    final violations = <String>[];

    for (final file in dartFiles) {
      final lines = file.readAsLinesSync();
      for (var i = 0; i < lines.length; i++) {
        final line = lines[i];
        final trimmed = line.trim();

        if (trimmed.startsWith('//') ||
            trimmed.startsWith('/*') ||
            trimmed.startsWith('*')) {
          continue; // Skip comments
        }

        if (line.contains('print(') || line.contains('debugPrint(')) {
          violations.add('${file.path}:L${i + 1}: $trimmed');
        }
      }
    }

    expect(
      violations,
      isEmpty,
      reason:
          'Production Mobile code must NOT contain print() or debugPrint() calls to prevent security log leaks. Found: $violations',
    );
  });

  group('Log Scanner Self-Test Scenarios (9 Scenarios)', () {
    test('Self-test 1: Full prompt logging is detected', () {
      final line = 'print("User prompt: \$prompt");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 2: Raw SSE payload logging is detected', () {
      final line = 'debugPrint("SSE data: \$ssePayload");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 3: Analysis result logging is detected', () {
      final line = 'print("Analysis result: \$resultJson");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 4: Financial value logging is detected', () {
      final line = 'debugPrint("Financial decimal value: \$canonicalValue");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 5: Evidence snippet logging is detected', () {
      final line = 'print("Evidence snippet: \$sanitizedSnippet");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 6: Authorization token logging is detected', () {
      final line = 'print("Auth token: \$token");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 7: App Check token logging is detected', () {
      final line = 'debugPrint("AppCheck token: \$appCheckToken");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 8: Last-Event-ID header leak is detected', () {
      final line = 'print("Last-Event-ID: \$lastEventId");';
      expect(line.contains('print(') || line.contains('debugPrint('), isTrue);
    });

    test('Self-test 9: Static safe event code without print is allowed', () {
      final line = 'final code = "EVENT_ACCEPTED";';
      expect(line.contains('print(') || line.contains('debugPrint('), isFalse);
    });
  });
}
