import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/features/analysis/controllers/analysis_controller.dart';
import 'package:finance_intelligence/features/analysis/presentation/widgets/progress_timeline_widget.dart';

void main() {
  testWidgets('ProgressTimelineWidget renders progress steps',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ProgressTimelineWidget(
            statusState: AnalysisStatusState.planning,
            warningMessage: null,
          ),
        ),
      ),
    );

    expect(find.text('Analiz İlerleme Durumu'), findsOneWidget);
    expect(find.text('Talep Alındı'), findsOneWidget);
    expect(find.text('Plan Hazırlanıyor'), findsOneWidget);
  });
}
