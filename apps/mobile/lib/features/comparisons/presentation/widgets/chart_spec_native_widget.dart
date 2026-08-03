import 'package:decimal/decimal.dart';
import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import '../../../../app/theme/semantic_tokens.dart';
import '../../../../core/models/wire_models.dart';

class ChartCoordinateAdapter {
  static double safeToDouble(String canonicalValue) {
    try {
      final dec = Decimal.parse(canonicalValue);
      final val = dec.toDouble();
      if (!val.isFinite || val.isNaN) return 0.0;
      return val;
    } catch (_) {
      return 0.0;
    }
  }
}

class ChartSpecNativeWidget extends StatelessWidget {
  final ResultDataset dataset;
  final String chartType;

  const ChartSpecNativeWidget({
    super.key,
    required this.dataset,
    this.chartType = 'vertical_bar',
  });

  @override
  Widget build(BuildContext context) {
    if (dataset.rows.isEmpty) {
      return const Center(
          child: Text('Grafik çizimi için yeterli veri bulunmuyor.'));
    }

    // Fail-Closed Fallback for Pie Chart on negative / non-part-to-whole datasets
    if (chartType == 'pie') {
      final hasNegative = dataset.rows.any((r) => r.cells.values.any(
          (c) => ChartCoordinateAdapter.safeToDouble(c.canonicalValue) < 0));
      if (hasNegative) {
        return Container(
          padding: const EdgeInsets.all(16.0),
          decoration: BoxDecoration(
            color: SemanticTokens.warningAmberLight.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(SemanticTokens.radiusMd),
            border: Border.all(color: SemanticTokens.warningAmberLight),
          ),
          child: const Column(
            children: [
              Icon(Icons.warning,
                  color: SemanticTokens.warningAmberLight, size: 32),
              SizedBox(height: 8),
              Text(
                'Pasta grafik (Pie Chart) negatif veya parça-bütün ilişkisi içermeyen veriler için uygun değildir. Tablo görünümü kullanılmaktadır.',
                textAlign: TextAlign.center,
                style: TextStyle(fontWeight: FontWeight.bold),
              ),
            ],
          ),
        );
      }
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        // Textual Summary for Screen Readers / Accessibility (WCAG 2.1 AA)
        Semantics(
          label:
              'Grafik Erişilebilir Özeti: ${dataset.rows.length} satır, Tür: $chartType. '
              'Seriler: SOURCE_REPORTED (Lacivert), SYSTEM_DERIVED (Turkuaz).',
          child: Container(
            padding: const EdgeInsets.all(8.0),
            color: SemanticTokens.primaryNavyLight.withValues(alpha: 0.05),
            child: Text(
              '📊 Native Grafik ($chartType): ${dataset.rows.length} Karşılaştırma Noktası',
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 13),
            ),
          ),
        ),
        const SizedBox(height: SemanticTokens.spacingMd),

        SizedBox(
          height: 260,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16.0),
            child: _buildNativeChartWidget(),
          ),
        ),
        const SizedBox(height: SemanticTokens.spacingMd),

        // Legend
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Container(
                width: 12, height: 12, color: SemanticTokens.primaryNavyLight),
            const SizedBox(width: 4),
            const Text('SOURCE_REPORTED',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
            const SizedBox(width: 16),
            Container(
                width: 12, height: 12, color: SemanticTokens.accentTealLight),
            const SizedBox(width: 4),
            const Text('SYSTEM_DERIVED',
                style: TextStyle(fontSize: 11, fontWeight: FontWeight.bold)),
          ],
        ),
      ],
    );
  }

  Widget _buildNativeChartWidget() {
    switch (chartType) {
      case 'horizontal_bar':
        return _buildBarChart(isHorizontal: true);
      case 'line':
        return _buildLineChart();
      case 'pie':
        return _buildPieChart();
      case 'grouped_bar':
      case 'stacked_bar':
      case 'vertical_bar':
      default:
        return _buildBarChart(isHorizontal: false);
    }
  }

  Widget _buildBarChart({required bool isHorizontal}) {
    final row = dataset.rows.first;
    final keys = row.cells.keys.toList();

    return BarChart(
      BarChartData(
        alignment: BarChartAlignment.spaceAround,
        maxY: _calculateMaxY(),
        barTouchData: BarTouchData(
          touchTooltipData: BarTouchTooltipData(
            getTooltipItem: (group, groupIndex, rod, rodIndex) {
              final r = dataset.rows[groupIndex];
              final cellKey = keys.isNotEmpty ? keys[0] : '';
              final cell = r.cells[cellKey];
              return BarTooltipItem(
                '${r.institutionName}\n${cell?.displayValue ?? rod.toY.toString()}',
                const TextStyle(
                    color: Colors.white, fontWeight: FontWeight.bold),
              );
            },
          ),
        ),
        titlesData: FlTitlesData(
          show: true,
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (val, meta) {
                final idx = val.toInt();
                if (idx >= 0 && idx < dataset.rows.length) {
                  return Text(
                    dataset.rows[idx].institutionName.split(' ').first,
                    style: const TextStyle(
                        fontSize: 10, fontWeight: FontWeight.bold),
                  );
                }
                return const Text('');
              },
            ),
          ),
          leftTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        borderData: FlBorderData(show: false),
        barGroups: dataset.rows.asMap().entries.map((e) {
          final idx = e.key;
          final r = e.value;
          final firstCell = r.cells.values.firstOrNull;
          final double val = firstCell != null
              ? ChartCoordinateAdapter.safeToDouble(firstCell.canonicalValue)
              : 0.0;
          final bool isDerived = firstCell?.valueOrigin == 'SYSTEM_DERIVED';

          return BarChartGroupData(
            x: idx,
            barRods: [
              BarChartRodData(
                toY: val,
                color: isDerived
                    ? SemanticTokens.accentTealLight
                    : SemanticTokens.primaryNavyLight,
                width: 22,
                borderRadius: BorderRadius.circular(4),
              ),
            ],
          );
        }).toList(),
      ),
    );
  }

  Widget _buildLineChart() {
    return LineChart(
      LineChartData(
        gridData: const FlGridData(show: false),
        titlesData: FlTitlesData(
          bottomTitles: AxisTitles(
            sideTitles: SideTitles(
              showTitles: true,
              getTitlesWidget: (val, meta) {
                final idx = val.toInt();
                if (idx >= 0 && idx < dataset.rows.length) {
                  return Text(dataset.rows[idx].periodLabel,
                      style: const TextStyle(fontSize: 10));
                }
                return const Text('');
              },
            ),
          ),
          leftTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          topTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
          rightTitles:
              const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        ),
        lineBarsData: [
          LineChartBarData(
            isCurved: true,
            color: SemanticTokens.primaryNavyLight,
            barWidth: 3,
            spots: dataset.rows.asMap().entries.map((e) {
              final idx = e.key.toDouble();
              final firstCell = e.value.cells.values.firstOrNull;
              final val = firstCell != null
                  ? ChartCoordinateAdapter.safeToDouble(
                      firstCell.canonicalValue)
                  : 0.0;
              return FlSpot(idx, val);
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildPieChart() {
    return PieChart(
      PieChartData(
        sectionsSpace: 2,
        centerSpaceRadius: 30,
        sections: dataset.rows.asMap().entries.map((e) {
          final idx = e.key;
          final r = e.value;
          final firstCell = r.cells.values.firstOrNull;
          final val = firstCell != null
              ? ChartCoordinateAdapter.safeToDouble(firstCell.canonicalValue)
              : 1.0;
          return PieChartSectionData(
            value: val,
            title: r.institutionName.split(' ').first,
            color: idx % 2 == 0
                ? SemanticTokens.primaryNavyLight
                : SemanticTokens.accentTealLight,
            radius: 50,
            titleStyle: const TextStyle(
                fontSize: 10, color: Colors.white, fontWeight: FontWeight.bold),
          );
        }).toList(),
      ),
    );
  }

  double _calculateMaxY() {
    double maxVal = 0.0;
    for (final r in dataset.rows) {
      for (final cell in r.cells.values) {
        final val = ChartCoordinateAdapter.safeToDouble(cell.canonicalValue);
        if (val > maxVal) maxVal = val;
      }
    }
    return maxVal > 0 ? maxVal * 1.2 : 100.0;
  }
}
