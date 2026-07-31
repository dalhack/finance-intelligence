import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/features/analysis/presentation/widgets/executive_summary_widget.dart';

void main() {
  testWidgets('ExecutiveSummaryWidget renders sanitized plain text summary',
      (WidgetTester tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: ExecutiveSummaryWidget(
            summaryText:
                'Garanti 2025 Q4 Toplam Aktif tutarı 1.5 Milyar TL olarak doğrulanmıştır.',
          ),
        ),
      ),
    );

    expect(find.text('Yönetici Özeti (Doğrulanmış)'), findsOneWidget);
    expect(find.textContaining('1.5 Milyar TL'), findsOneWidget);
  });
}
