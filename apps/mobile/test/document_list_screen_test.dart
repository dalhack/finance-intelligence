import 'package:finance_intelligence/features/documents/presentation/document_management_screen.dart';
import 'package:finance_intelligence/presentation/providers/providers.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'fixtures/test_mock_repositories.dart';

void main() {
  testWidgets('DocumentManagementScreen renders title and document list', (
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
        child: const MaterialApp(home: DocumentManagementScreen()),
      ),
    );

    await tester.pumpAndSettle();

    expect(find.text('Belge Yönetimi'), findsOneWidget);
    expect(find.text('Belge Yükle'), findsOneWidget);
  });
}
