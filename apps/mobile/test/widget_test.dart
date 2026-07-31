import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/app/theme/app_theme.dart';
import 'package:finance_intelligence/features/home/presentation/main_dashboard_screen.dart';
import 'package:finance_intelligence/presentation/providers/providers.dart';
import 'fixtures/test_mock_repositories.dart';

void main() {
  testWidgets('App startup renders MainDashboardScreen title', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          documentRepositoryProvider
              .overrideWithValue(TestMockDocumentRepository()),
          factReviewRepositoryProvider
              .overrideWithValue(TestMockFactReviewRepository()),
        ],
        child: MaterialApp(
          theme: AppTheme.lightTheme,
          home: const MainDashboardScreen(),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Finance Intelligence'), findsWidgets);
  });
}
