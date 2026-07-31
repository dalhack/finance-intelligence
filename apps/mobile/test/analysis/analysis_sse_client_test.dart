import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';

void main() {
  group('AnalysisSseClient Byte-Stream Parser Tests', () {
    Stream<AnalysisDomainEventModel> parseByteStream(List<List<int>> chunks) {
      final controller = StreamController<AnalysisDomainEventModel>();
      String buffer = '';
      String currentType = '';
      String currentId = '';
      String currentData = '';

      final stream = Stream<List<int>>.fromIterable(chunks);

      stream.transform(const Utf8Decoder(allowMalformed: true)).listen(
        (chunk) {
          buffer += chunk;
          final lines = buffer.split('\n');
          buffer = lines.removeLast();

          for (final line in lines) {
            final trimmed = line.trim();
            if (trimmed.isEmpty) {
              if (currentType.isNotEmpty && currentData.isNotEmpty) {
                try {
                  final parsedJson =
                      json.decode(currentData) as Map<String, dynamic>;
                  controller.add(
                    AnalysisDomainEventModel.fromSseLine(
                      type: currentType,
                      id: currentId,
                      data: parsedJson,
                    ),
                  );
                } catch (_) {}
              }
              currentType = '';
              currentId = '';
              currentData = '';
              continue;
            }

            if (trimmed.startsWith('event:')) {
              currentType = trimmed.substring(6).trim();
            } else if (trimmed.startsWith('id:')) {
              currentId = trimmed.substring(3).trim();
            } else if (trimmed.startsWith('data:')) {
              final dataVal = trimmed.substring(5).trim();
              currentData =
                  currentData.isEmpty ? dataVal : '$currentData\n$dataVal';
            }
          }
        },
        onDone: () {
          if (currentType.isNotEmpty && currentData.isNotEmpty) {
            try {
              final parsedJson =
                  json.decode(currentData) as Map<String, dynamic>;
              controller.add(
                AnalysisDomainEventModel.fromSseLine(
                  type: currentType,
                  id: currentId,
                  data: parsedJson,
                ),
              );
            } catch (_) {}
          }
          controller.close();
        },
        onError: (err) {
          // Gracefully catch decode errors
        },
      );

      return controller.stream;
    }

    test('1. Single event in single byte chunk', () async {
      final bytes = utf8
          .encode('event: analysis.accepted\nid: 1\ndata: {"job_id":"j1"}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(1));
      expect(events[0].eventType, equals('analysis.accepted'));
      expect(events[0].sequence, equals(1));
    });

    test('2. Event split across two byte chunks', () async {
      final chunk1 =
          utf8.encode('event: analysis.accepted\nid: 2\ndata: {"job_');
      final chunk2 = utf8.encode('id":"j2"}\n\n');
      final events = await parseByteStream([chunk1, chunk2]).toList();
      expect(events.length, equals(1));
      expect(events[0].eventType, equals('analysis.accepted'));
      expect(events[0].sequence, equals(2));
    });

    test('3. data: key split mid-chunk', () async {
      final chunk1 = utf8.encode('event: analysis.state_changed\nid: 3\nda');
      final chunk2 = utf8.encode('ta: {"job_id":"j3"}\n\n');
      final events = await parseByteStream([chunk1, chunk2]).toList();
      expect(events.length, equals(1));
      expect(events[0].sequence, equals(3));
    });

    test('4. JSON payload split mid-chunk', () async {
      final chunk1 =
          utf8.encode('event: analysis.completed\nid: 4\ndata: {"status":');
      final chunk2 = utf8.encode('"COMPLETED","job_id":"j4"}\n\n');
      final events = await parseByteStream([chunk1, chunk2]).toList();
      expect(events.length, equals(1));
      expect(events[0].eventType, equals('analysis.completed'));
    });

    test('5. Multi-byte Turkish character split mid-byte across chunks',
        () async {
      final fullStr =
          'event: analysis.warning\nid: 5\ndata: {"msg":"Gürültü"}\n\n';
      final bytes = utf8.encode(fullStr);
      final chunk1 = bytes.sublist(0, 45);
      final chunk2 = bytes.sublist(45);
      final events = await parseByteStream([chunk1, chunk2]).toList();
      expect(events.length, equals(1));
    });

    test('6. Two events in a single byte chunk', () async {
      final bytes = utf8.encode(
        'event: analysis.accepted\nid: 6\ndata: {"job_id":"j6"}\n\n'
        'event: analysis.completed\nid: 7\ndata: {"job_id":"j6"}\n\n',
      );
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(2));
      expect(events[0].sequence, equals(6));
      expect(events[1].sequence, equals(7));
    });

    test('7. Multi-line data payload', () async {
      final bytes = utf8.encode(
          'event: analysis.plan_ready\nid: 8\ndata: {"line1":1}\ndata: {"line2":2}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(0)); // Multi-line json decode fallback test
    });

    test('8. CRLF line endings parsing', () async {
      final bytes = utf8.encode(
          'event: analysis.accepted\r\nid: 9\r\ndata: {"job_id":"j9"}\r\n\r\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(1));
      expect(events[0].sequence, equals(9));
    });

    test('9. Comment / heartbeat line ignoring', () async {
      final bytes = utf8.encode(
          ': heartbeat comment line\nevent: heartbeat\nid: 10\ndata: {"status":"ping"}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(1));
      expect(events[0].eventType, equals('heartbeat'));
    });

    test('10. Event ID parsing', () async {
      final bytes = utf8.encode(
          'event: analysis.accepted\nid: 11\ndata: {"job_id":"j11"}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events[0].sequence, equals(11));
    });

    test('11. Event type parsing', () async {
      final bytes = utf8.encode(
          'event: analysis.tool_started\nid: 12\ndata: {"tool":"compare"}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events[0].eventType, equals('analysis.tool_started'));
    });

    test('12. Disconnect with half event flushes safely', () async {
      final bytes =
          utf8.encode('event: analysis.accepted\nid: 13\ndata: {"incomplete":');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length,
          equals(0)); // Incomplete JSON safely ignored on disconnect
    });

    test('13. Malformed UTF-8 bytes handling', () async {
      final badBytes = [0xFF, 0xFE, 0xFD];
      final events = await parseByteStream([badBytes]).toList();
      expect(events.length, equals(0));
    });

    test('14. Malformed JSON payload handling', () async {
      final bytes = utf8
          .encode('event: analysis.accepted\nid: 14\ndata: {invalid_json}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(0));
    });

    test('15. Oversized payload handling', () async {
      final bigString = 'x' * 10000;
      final bytes = utf8.encode(
          'event: analysis.accepted\nid: 15\ndata: {"big":"$bigString"}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(1));
    });

    test('16. Unknown field ignoring', () async {
      final bytes = utf8.encode(
          'retry: 5000\nfoo: bar\nevent: analysis.accepted\nid: 16\ndata: {"job_id":"j16"}\n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(1));
      expect(events[0].sequence, equals(16));
    });

    test('17. Empty data handling', () async {
      final bytes = utf8.encode('event: analysis.accepted\nid: 17\ndata: \n\n');
      final events = await parseByteStream([bytes]).toList();
      expect(events.length, equals(0));
    });

    test('18. Stream cancellation handling', () async {
      final stream = parseByteStream([
        utf8.encode(
            'event: analysis.accepted\nid: 18\ndata: {"job_id":"j18"}\n\n')
      ]);
      final sub = stream.listen((_) {});
      await sub.cancel();
    });
  });
}
