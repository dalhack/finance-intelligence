import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/app/navigation_shell.dart';
import 'package:finance_intelligence/app/theme/app_theme.dart';
import 'package:finance_intelligence/presentation/providers/providers.dart';
import '../fixtures/test_mock_repositories.dart';

void main() {
  group('Accessibility & Responsive UI Tests (WCAG 2.1 AA)', () {
    Widget wrapWidget(Widget child) {
      return ProviderScope(
        overrides: [
          documentRepositoryProvider
              .overrideWithValue(TestMockDocumentRepository()),
          factReviewRepositoryProvider
              .overrideWithValue(TestMockFactReviewRepository()),
        ],
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          home: child,
        ),
      );
    }

    testWidgets(
        'Renders NavigationShell without layout overflow at 200% text scaling',
        (tester) async {
      await tester.pumpWidget(
        wrapWidget(
          const MediaQuery(
            data: MediaQueryData(textScaler: TextScaler.linear(2.0)),
            child: NavigationShell(),
          ),
        ),
      );

      await tester.pumpAndSettle();
      expect(find.text('Ana Sayfa'), findsWidgets);
      expect(tester.takeException(), isNull);
    });

    testWidgets('Renders NavigationShell on narrow phone viewport (320x568)',
        (tester) async {
      tester.view.physicalSize = const Size(320, 568);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(wrapWidget(const NavigationShell()));

      await tester.pumpAndSettle();
      expect(find.text('Ana Sayfa'), findsWidgets);
      expect(tester.takeException(), isNull);

      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
    });

    testWidgets('Renders NavigationRail on tablet viewport (1024x768)',
        (tester) async {
      tester.view.physicalSize = const Size(1024, 768);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(wrapWidget(const NavigationShell()));

      await tester.pumpAndSettle();
      expect(find.byType(NavigationRail), findsOneWidget);
      expect(tester.takeException(), isNull);

      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
    });
  });
}
