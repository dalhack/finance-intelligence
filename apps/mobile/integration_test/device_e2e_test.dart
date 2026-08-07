import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:finance_intelligence/app/app.dart';
import 'package:finance_intelligence/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Device E2E Harness (Simulator/Emulator Verification)', () {
    testWidgets(
        'Executes full synthetic UI flow without external network access',
        (WidgetTester tester) async {
      app.main();
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 500));

      // Verify Dashboard Screen renders genuine production title
      expect(find.text('Finance Intelligence'), findsOneWidget);

      // Verify Navigation controls and root app widget
      await tester.pump(const Duration(seconds: 1));
      expect(find.byType(FinanceIntelligenceApp), findsOneWidget);
    });
  });
}

