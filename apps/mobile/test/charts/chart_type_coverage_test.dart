import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/wire_models.dart';
import 'package:finance_intelligence/features/comparisons/presentation/widgets/chart_spec_native_widget.dart';

void main() {
  group('ChartSpec 6-Chart Coverage & Fallback Tests', () {
    final mockDataset = ResultDataset(
      resultDatasetId: 'ds-test',
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
          institutionName: 'Bank Alpha',
          reportingPeriodId: 'per-1',
          periodLabel: '2025/Q4',
          reportingBasis: 'SOLO',
          cells: {
            'TOTAL_ASSETS': DatasetRowCell(
              measureCode: 'TOTAL_ASSETS',
              semanticMeasureCode: 'TOTAL_ASSETS',
              canonicalValue: '1000.5000',
              displayValue: '1,000.50',
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

    const chartTypes = [
      'vertical_bar',
      'horizontal_bar',
      'grouped_bar',
      'line',
      'stacked_bar',
      'pie',
    ];

    for (final chartType in chartTypes) {
      testWidgets('Renders chart type $chartType without exception',
          (tester) async {
        await tester.pumpWidget(
          MaterialApp(
            home: Scaffold(
              body: ChartSpecNativeWidget(
                  dataset: mockDataset, chartType: chartType),
            ),
          ),
        );
        await tester.pumpAndSettle();
        expect(find.byType(ChartSpecNativeWidget), findsOneWidget);
        expect(tester.takeException(), isNull);
      });
    }

    testWidgets(
        'Triggers fail-closed fallback for pie chart on negative values',
        (tester) async {
      final negDataset = ResultDataset(
        resultDatasetId: 'ds-neg',
        schemaVersion: '3.0.0',
        dataQualitySummary: const DataQualitySummary(
          expectedCells: 1,
          populatedCells: 1,
          missingSourceCells: 0,
          excludedIneligibleCells: 0,
          excludedMismatchCells: 0,
          warningCells: 0,
          sourceReportedCount: 1,
          systemDerivedCount: 0,
          reconciliationWarningCount: 0,
          completenessPercentage: '100.00',
        ),
        rows: const [
          DatasetRow(
            rowId: 'r-neg',
            institutionId: 'inst-1',
            institutionName: 'Bank Neg',
            reportingPeriodId: 'per-1',
            periodLabel: '2025/Q4',
            reportingBasis: 'SOLO',
            cells: {
              'PROFIT': DatasetRowCell(
                measureCode: 'PROFIT',
                semanticMeasureCode: 'PROFIT',
                canonicalValue: '-500.0000',
                displayValue: '-500.00',
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

      await tester.pumpWidget(
        MaterialApp(
          home: Scaffold(
            body: ChartSpecNativeWidget(dataset: negDataset, chartType: 'pie'),
          ),
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Pasta grafik'), findsOneWidget);
    });
  });
}
