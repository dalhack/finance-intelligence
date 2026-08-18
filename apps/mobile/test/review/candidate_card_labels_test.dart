import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/features/review/presentation/review_queue_screen.dart';

/// A reviewer approves a value into the verified fact store; presenting a bare
/// number with no institution, line item, period or source makes that decision
/// impossible. These tests lock the card's readable content.
void main() {
  Widget host(Widget child) => MaterialApp(home: Scaffold(body: child));

  const candidate = <String, dynamic>{
    'institution_name': 'VakıfBank',
    'metric_label': 'Toplam Mevduat',
    'period_label': '2026/Q1',
    'detected_reporting_basis': 'SOLO',
    'raw_value': '3.186.259.508',
    'raw_currency': 'TRY',
    'raw_scale': 'THOUSAND',
    'extraction_method': 'LLM_ASSISTED',
    'evidence_snippet': 'Toplam Mevduat | 3.186.259.508',
    'source_page': 7,
    'confidence_score': 0.9,
    'review_status': 'PENDING',
  };

  testWidgets('shows institution, metric, period, value and evidence',
      (tester) async {
    await tester.pumpWidget(host(CandidateCardContent(candidate: candidate)));

    expect(find.text('VakıfBank'), findsOneWidget);
    expect(find.textContaining('Toplam Mevduat'), findsWidgets);
    expect(find.textContaining('2026/Q1'), findsOneWidget);
    expect(find.textContaining('SOLO'), findsOneWidget);
    expect(find.text('3.186.259.508'), findsOneWidget);
    expect(find.textContaining('Bin TRY'), findsOneWidget);
    expect(find.text('Model okuması'), findsOneWidget);
    expect(find.textContaining('s.7'), findsOneWidget);
  });

  testWidgets('falls back to the raw label instead of a blank caption',
      (tester) async {
    await tester.pumpWidget(host(const CandidateCardContent(candidate: {
      'raw_label': 'Menkul Değerler',
      'raw_value': '742.552.618',
      'review_status': 'PENDING',
    })));

    expect(find.textContaining('Menkul Değerler'), findsOneWidget);
    expect(find.text('742.552.618'), findsOneWidget);
    // Never the old placeholder wording.
    expect(find.text('Metrik'), findsNothing);
    expect(find.text('Kurum'), findsNothing);
  });
}
