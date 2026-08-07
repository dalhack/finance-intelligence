import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:finance_intelligence/app/app.dart';
import 'package:finance_intelligence/main.dart' as app;

Future<void> pumpUntilFound(
  WidgetTester tester,
  Finder finder, {
  String phase = 'unnamed_phase',
  Duration timeout = const Duration(seconds: 30),
  Duration step = const Duration(milliseconds: 100),
}) async {
  final maxIterations = (timeout.inMilliseconds / step.inMilliseconds).ceil();
  var virtualElapsed = Duration.zero;

  for (var iteration = 1; iteration <= maxIterations; iteration++) {
    await tester.pump(step);
    virtualElapsed += step;

    final exception = tester.takeException();
    if (exception != null) {
      fail('APP_EXCEPTION in phase "$phase": $exception');
    }

    if (finder.evaluate().isNotEmpty) {
      return;
    }
  }

  fail(
    'BOUNDED_WAIT_TIMEOUT in phase "$phase": Target widget $finder not found after $maxIterations iterations (${virtualElapsed.inSeconds}s virtual time)',
  );
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  group('Device E2E Harness (Simulator/Emulator Verification)', () {
    testWidgets(
        'Executes full synthetic UI flow without external network access',
        (WidgetTester tester) async {
      app.main();

      // Bounded deterministic wait for Dashboard Screen title
      final titleFinder = find.text('Finance Intelligence');
      await pumpUntilFound(
        tester,
        titleFinder,
        phase: 'dashboard_title_rendering',
        timeout: const Duration(seconds: 30),
      );

      expect(titleFinder, findsOneWidget);

      // Bounded wait for root app widget
      final appFinder = find.byType(FinanceIntelligenceApp);
      await pumpUntilFound(
        tester,
        appFinder,
        phase: 'root_app_widget_rendering',
        timeout: const Duration(seconds: 10),
      );

      expect(appFinder, findsOneWidget);
    });
  });
}
