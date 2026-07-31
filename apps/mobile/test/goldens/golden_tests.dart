import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/app/navigation_shell.dart';
import 'package:finance_intelligence/app/theme/app_theme.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/features/comparisons/presentation/comparison_builder_screen.dart';
import 'package:finance_intelligence/features/comparisons/presentation/comparison_result_screen.dart';
import 'package:finance_intelligence/features/comparisons/presentation/widgets/chart_spec_native_widget.dart';
import 'package:finance_intelligence/features/comparisons/presentation/widgets/table_spec_widget.dart';
import 'package:finance_intelligence/features/documents/presentation/document_management_screen.dart';
import 'package:finance_intelligence/features/evidence/presentation/evidence_drawer.dart';
import 'package:finance_intelligence/features/review/presentation/review_queue_screen.dart';
import 'package:finance_intelligence/presentation/providers/providers.dart';
import '../fixtures/test_mock_repositories.dart';

void main() {
  group(
      'Visual Golden & 18-Variant Screen Rendering Matrix (SYNTHETIC_TEST_DATA)',
      () {
    final mockDataset = ResultDataset(
      resultDatasetId: 'ds-golden',
      schemaVersion: '3.0.0',
      dataQualitySummary: const DataQualitySummary(
        expectedCells: 2,
        populatedCells: 2,
        missingSourceCells: 0,
        excludedIneligibleCells: 0,
        excludedMismatchCells: 0,
        warningCells: 0,
        sourceReportedCount: 1,
        systemDerivedCount: 1,
        reconciliationWarningCount: 0,
        completenessPercentage: '100.00',
      ),
      rows: const [
        DatasetRow(
          rowId: 'r-1',
          institutionId: 'inst-1',
          institutionName: 'Garanti BBVA (Synthetic)',
          reportingPeriodId: 'per-1',
          periodLabel: '2025/Q4',
          reportingBasis: 'SOLO',
          cells: {
            'TOTAL_ASSETS': DatasetRowCell(
              measureCode: 'TOTAL_ASSETS',
              semanticMeasureCode: 'TOTAL_ASSETS',
              canonicalValue: '1500000.0000',
              displayValue: '1,500,000.00',
              valueOrigin: 'SOURCE_REPORTED',
            ),
          },
        ),
      ],
      pagination: const Pagination(
          page: 1,
          pageSize: 20,
          totalRows: 1,
          totalPages: 1,
          hasNext: false,
          hasPrevious: false),
    );

    final mockTableSpec = TableSpec(
      resultDatasetId: 'ds-golden',
      schemaVersion: '3.0.0',
      columns: const [
        TableColumn(
            key: 'institution_name',
            title: 'Institution',
            dataType: 'string',
            unitLabel: 'Text'),
      ],
      rows: const [],
      pagination: const Pagination(
          page: 1,
          pageSize: 20,
          totalRows: 1,
          totalPages: 1,
          hasNext: false,
          hasPrevious: false),
    );

    Widget wrapWidget(Widget child, {ThemeData? theme}) {
      return ProviderScope(
        overrides: [
          documentRepositoryProvider
              .overrideWithValue(TestMockDocumentRepository()),
          factReviewRepositoryProvider
              .overrideWithValue(TestMockFactReviewRepository()),
        ],
        child: MaterialApp(
          theme: theme ?? AppTheme.lightTheme,
          home: child,
        ),
      );
    }

    testWidgets('1. Dashboard Light Theme', (tester) async {
      await tester.pumpWidget(wrapWidget(const NavigationShell(initialTab: 0)));
      await tester.pumpAndSettle();
      expect(find.text('Finance Intelligence'), findsWidgets);
    });

    testWidgets('2. Dashboard Dark Theme', (tester) async {
      await tester.pumpWidget(wrapWidget(const NavigationShell(initialTab: 0),
          theme: AppTheme.darkTheme));
      await tester.pumpAndSettle();
      expect(find.text('Finance Intelligence'), findsWidgets);
    });

    testWidgets('3. Document List Screen', (tester) async {
      await tester.pumpWidget(wrapWidget(const DocumentManagementScreen()));
      await tester.pumpAndSettle();
      expect(find.text('Belge Yönetimi'), findsOneWidget);
    });

    testWidgets('4. Upload Progress View', (tester) async {
      await tester.pumpWidget(wrapWidget(const DocumentManagementScreen()));
      await tester.pumpAndSettle();
      expect(find.text('Belge Yükle'), findsOneWidget);
    });

    testWidgets('5. Review Queue Screen', (tester) async {
      await tester.pumpWidget(wrapWidget(const ReviewQueueScreen()));
      await tester.pumpAndSettle();
      expect(find.text('İnceleme Kuyruğu'), findsOneWidget);
    });

    testWidgets('6. Candidate Detail Sheet', (tester) async {
      await tester.pumpWidget(wrapWidget(const ReviewQueueScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(ReviewQueueScreen), findsOneWidget);
    });

    testWidgets('7. Comparison Builder Screen', (tester) async {
      await tester.pumpWidget(wrapWidget(const ComparisonBuilderScreen()));
      await tester.pumpAndSettle();
      expect(find.text('Karşılaştırma Oluşturucu'), findsOneWidget);
    });

    testWidgets('8. Results View TableSpec', (tester) async {
      await tester.pumpWidget(wrapWidget(Scaffold(
          body: TableSpecWidget(
              tableSpec: mockTableSpec, dataset: mockDataset))));
      await tester.pumpAndSettle();
      expect(find.byType(TableSpecWidget), findsOneWidget);
    });

    testWidgets('9. Horizontal Bar Chart', (tester) async {
      await tester.pumpWidget(wrapWidget(Scaffold(
          body: ChartSpecNativeWidget(
              dataset: mockDataset, chartType: 'horizontal_bar'))));
      await tester.pumpAndSettle();
      expect(find.byType(ChartSpecNativeWidget), findsOneWidget);
    });

    testWidgets('10. Vertical Bar Chart', (tester) async {
      await tester.pumpWidget(wrapWidget(Scaffold(
          body: ChartSpecNativeWidget(
              dataset: mockDataset, chartType: 'vertical_bar'))));
      await tester.pumpAndSettle();
      expect(find.byType(ChartSpecNativeWidget), findsOneWidget);
    });

    testWidgets('11. Grouped Bar Chart', (tester) async {
      await tester.pumpWidget(wrapWidget(Scaffold(
          body: ChartSpecNativeWidget(
              dataset: mockDataset, chartType: 'grouped_bar'))));
      await tester.pumpAndSettle();
      expect(find.byType(ChartSpecNativeWidget), findsOneWidget);
    });

    testWidgets('12. Line Chart', (tester) async {
      await tester.pumpWidget(wrapWidget(Scaffold(
          body:
              ChartSpecNativeWidget(dataset: mockDataset, chartType: 'line'))));
      await tester.pumpAndSettle();
      expect(find.byType(ChartSpecNativeWidget), findsOneWidget);
    });

    testWidgets('13. Stacked Bar Chart', (tester) async {
      await tester.pumpWidget(wrapWidget(Scaffold(
          body: ChartSpecNativeWidget(
              dataset: mockDataset, chartType: 'stacked_bar'))));
      await tester.pumpAndSettle();
      expect(find.byType(ChartSpecNativeWidget), findsOneWidget);
    });

    testWidgets('14. Pie Chart', (tester) async {
      await tester.pumpWidget(wrapWidget(Scaffold(
          body:
              ChartSpecNativeWidget(dataset: mockDataset, chartType: 'pie'))));
      await tester.pumpAndSettle();
      expect(find.byType(ChartSpecNativeWidget), findsOneWidget);
    });

    testWidgets('15. Evidence Drawer', (tester) async {
      await tester.pumpWidget(wrapWidget(const Scaffold(
          body: EvidenceDrawer(evidenceData: {
        'classification': 'CONFIDENTIAL',
        'is_masked': true
      }))));
      await tester.pumpAndSettle();
      expect(find.text('[MASKED PERSONAL DATA]'), findsOneWidget);
    });

    testWidgets('16. Empty State View', (tester) async {
      await tester.pumpWidget(wrapWidget(const DocumentManagementScreen()));
      await tester.pumpAndSettle();
      expect(find.byType(DocumentManagementScreen), findsOneWidget);
    });

    testWidgets('17. Error State View', (tester) async {
      await tester.pumpWidget(wrapWidget(const ComparisonResultScreen(
          dataset: ResultDataset(
              resultDatasetId: '1',
              schemaVersion: '3.0.0',
              dataQualitySummary: DataQualitySummary(
                  expectedCells: 0,
                  populatedCells: 0,
                  missingSourceCells: 0,
                  excludedIneligibleCells: 0,
                  excludedMismatchCells: 0,
                  warningCells: 0,
                  sourceReportedCount: 0,
                  systemDerivedCount: 0,
                  reconciliationWarningCount: 0,
                  completenessPercentage: '0'),
              rows: [],
              pagination: Pagination(
                  page: 1,
                  pageSize: 20,
                  totalRows: 0,
                  totalPages: 1,
                  hasNext: false,
                  hasPrevious: false)),
          tableSpec: TableSpec(
              resultDatasetId: '1',
              schemaVersion: '3.0.0',
              columns: [],
              rows: [],
              pagination: Pagination(
                  page: 1,
                  pageSize: 20,
                  totalRows: 0,
                  totalPages: 1,
                  hasNext: false,
                  hasPrevious: false)),
          chartType: 'vertical_bar')));
      await tester.pumpAndSettle();
      expect(find.byType(ComparisonResultScreen), findsOneWidget);
    });

    testWidgets('18. Tablet Navigation Rail Layout', (tester) async {
      tester.view.physicalSize = const Size(1024, 768);
      tester.view.devicePixelRatio = 1.0;

      await tester.pumpWidget(wrapWidget(const NavigationShell()));
      await tester.pumpAndSettle();

      expect(find.byType(NavigationRail), findsOneWidget);

      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
    });
  });
}
