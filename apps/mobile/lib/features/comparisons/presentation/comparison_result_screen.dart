import 'package:flutter/material.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../core/models/wire_models.dart';
import 'widgets/chart_spec_native_widget.dart';
import 'widgets/table_spec_widget.dart';

class ComparisonResultScreen extends StatelessWidget {
  final ResultDataset dataset;
  final TableSpec tableSpec;
  final String chartType;

  const ComparisonResultScreen({
    super.key,
    required this.dataset,
    required this.tableSpec,
    required this.chartType,
  });

  @override
  Widget build(BuildContext context) {
    final dq = dataset.dataQualitySummary;

    return DefaultTabController(
      length: 4,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Karşılaştırma Sonucu'),
          bottom: const TabBar(
            tabs: [
              Tab(icon: Icon(Icons.table_chart), text: 'Tablo'),
              Tab(icon: Icon(Icons.bar_chart), text: 'Grafik'),
              Tab(icon: Icon(Icons.verified), text: 'Kalite'),
              Tab(icon: Icon(Icons.source), text: 'Kaynaklar'),
            ],
          ),
        ),
        body: Column(
          children: [
            // Metadata Header Card
            Container(
              color: SemanticTokens.primaryNavyLight.withOpacity(0.05),
              padding: const EdgeInsets.all(12.0),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Schema Version: ${dataset.schemaVersion}',
                          style: const TextStyle(
                              fontWeight: FontWeight.bold, fontSize: 12)),
                      Text('Doluluk Oranı: %${dq.completenessPercentage}',
                          style: const TextStyle(
                              color: SemanticTokens.verifiedGreenLight,
                              fontSize: 12,
                              fontWeight: FontWeight.bold)),
                    ],
                  ),
                  Chip(
                    label: Text('${dq.warningCells} Uyarı',
                        style: const TextStyle(
                            color: Colors.white,
                            fontSize: 11,
                            fontWeight: FontWeight.bold)),
                    backgroundColor: dq.warningCells > 0
                        ? SemanticTokens.warningAmberLight
                        : SemanticTokens.verifiedGreenLight,
                  ),
                ],
              ),
            ),

            // Tab Views
            Expanded(
              child: TabBarView(
                children: [
                  // Tab 1: Financial TableSpec
                  Padding(
                    padding: const EdgeInsets.all(8.0),
                    child:
                        TableSpecWidget(tableSpec: tableSpec, dataset: dataset),
                  ),

                  // Tab 2: Native ChartSpec
                  Padding(
                    padding: const EdgeInsets.all(16.0),
                    child: ChartSpecNativeWidget(
                        dataset: dataset, chartType: chartType),
                  ),

                  // Tab 3: Data Quality Summary Card
                  SingleChildScrollView(
                    padding: const EdgeInsets.all(16.0),
                    child: Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16.0),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                                'Veri Kalitesi Özeti (Data Quality Summary)',
                                style: TextStyle(
                                    fontWeight: FontWeight.bold, fontSize: 16)),
                            const Divider(),
                            ListTile(
                              leading: const Icon(Icons.grid_on,
                                  color: SemanticTokens.primaryBlueLight),
                              title: const Text('Beklenen Hücre Sayısı'),
                              trailing: Text('${dq.expectedCells}',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                            ),
                            ListTile(
                              leading: const Icon(Icons.check_circle,
                                  color: SemanticTokens.verifiedGreenLight),
                              title: const Text('Dolu Hücreler (Populated)'),
                              trailing: Text('${dq.populatedCells}',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                            ),
                            ListTile(
                              leading: const Icon(Icons.remove_circle_outline,
                                  color: Colors.grey),
                              title: const Text(
                                  'Eksik Kaynak Hücreleri (Missing)'),
                              trailing: Text('${dq.missingSourceCells}',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                            ),
                            ListTile(
                              leading: const Icon(Icons.warning,
                                  color: SemanticTokens.warningAmberLight),
                              title: const Text(
                                  'Uyarı İçeren Hücreler (Warnings)'),
                              trailing: Text('${dq.warningCells}',
                                  style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),

                  // Tab 4: Sources
                  const Center(
                    child: Text(
                        'Tüm finansal veriler doğrulanmış PDF/XLSX dipnotlarından çıkarılmıştır.'),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
