import 'package:finance_intelligence/features/analysis/presentation/analysis_result_view.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// The answer must be drawn from server-verified data. These tests lock the two
/// behaviours that matter: a dataset is rendered as a table, and its absence is
/// stated plainly instead of being papered over.
void main() {
  Widget host(Widget child) => MaterialApp(home: Scaffold(body: child));

  const withDataset = <String, dynamic>{
    'analysis_id': 'a-1',
    'request_prompt': 'Toplam aktifleri karşılaştır',
    'executive_summary': 'İki bankanın toplam aktifleri karşılaştırıldı.',
    'result_dataset_id': 'ds-1',
    'schema_version': '3.0.0',
    'data_quality_summary': {
      'total_cells': 2,
      'verified_cells': 2,
      'missing_cells': 0,
      'estimated_cells': 0,
    },
    'rows': <dynamic>[],
    'table_spec': {
      'result_dataset_id': 'ds-1',
      'schema_version': '3.0.0',
      'columns': <dynamic>[],
      'rows': <dynamic>[],
      'pagination': <String, dynamic>{},
    },
    'chart_specs': [
      {'chart_type': 'vertical_bar'},
    ],
    'warnings': ['SCALE_ASSUMED'],
  };

  testWidgets('renders the four answer tabs and the narrative', (tester) async {
    await tester
        .pumpWidget(host(const AnalysisResultView(result: withDataset)));
    await tester.pumpAndSettle();

    expect(find.text('Özet'), findsOneWidget);
    expect(find.text('Tablo'), findsOneWidget);
    expect(find.text('Grafik'), findsOneWidget);
    expect(find.text('Kaynak'), findsOneWidget);
    expect(find.textContaining('toplam aktifleri karşılaştırıldı'),
        findsOneWidget);
    // Data-quality warnings travel with the answer.
    expect(find.textContaining('SCALE_ASSUMED'), findsOneWidget);
  });

  testWidgets('says so when the analysis produced no dataset', (tester) async {
    await tester.pumpWidget(host(const AnalysisResultView(result: {
      'executive_summary': 'Yeterli veri bulunamadı.',
      'chart_specs': <dynamic>[],
      'warnings': <dynamic>[],
    })));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Tablo'));
    await tester.pumpAndSettle();
    expect(find.textContaining('doğrulanmış bir veri kümesi üretmedi'),
        findsOneWidget);

    await tester.tap(find.text('Grafik'));
    await tester.pumpAndSettle();
    expect(find.textContaining('grafik üretilmedi'), findsOneWidget);
  });
}
