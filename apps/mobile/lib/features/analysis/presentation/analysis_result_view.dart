import 'package:flutter/material.dart';

import '../../../app/theme/semantic_tokens.dart';
import '../../../core/models/wire_models.dart';
import '../../comparisons/presentation/widgets/chart_spec_native_widget.dart';
import '../../comparisons/presentation/widgets/table_spec_widget.dart';

/// The answer to an analysis, drawn from what the server verified.
///
/// The narrative is the model's wording, but the table and chart come from the
/// result dataset the deterministic engine produced. Nothing here re-derives a
/// figure from prose: if the server sent no dataset, the summary is shown and
/// the data tabs say so instead of inventing content.
class AnalysisResultView extends StatelessWidget {
  final Map<String, dynamic> result;

  const AnalysisResultView({super.key, required this.result});

  String get _summary =>
      result['executive_summary']?.toString() ?? 'Özet üretilmedi.';

  TableSpec? get _tableSpec {
    final raw = result['table_spec'];
    if (raw is! Map<String, dynamic>) return null;
    try {
      return TableSpec.fromJson(raw);
    } on Exception {
      return null;
    }
  }

  ResultDataset? get _dataset {
    final datasetId = result['result_dataset_id']?.toString();
    final rows = result['rows'];
    final quality = result['data_quality_summary'];
    if (datasetId == null ||
        rows is! List ||
        quality is! Map<String, dynamic>) {
      return null;
    }
    try {
      return ResultDataset.fromJson({
        'result_dataset_id': datasetId,
        'schema_version': result['schema_version']?.toString() ?? '3.0.0',
        'data_quality_summary': quality,
        'rows': rows,
        'pagination': const <String, dynamic>{},
      });
    } on Exception {
      return null;
    }
  }

  List<String> get _chartTypes {
    final specs = result['chart_specs'];
    if (specs is! List) return const [];
    return specs
        .whereType<Map<String, dynamic>>()
        .map((spec) => spec['chart_type']?.toString() ?? 'vertical_bar')
        .toList();
  }

  List<dynamic> get _warnings {
    final raw = result['warnings'];
    return raw is List ? raw : const [];
  }

  @override
  Widget build(BuildContext context) {
    final tableSpec = _tableSpec;
    final dataset = _dataset;
    final chartTypes = _chartTypes;

    return DefaultTabController(
      length: 4,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const TabBar(
            isScrollable: true,
            tabAlignment: TabAlignment.start,
            tabs: [
              Tab(text: 'Özet'),
              Tab(text: 'Tablo'),
              Tab(text: 'Grafik'),
              Tab(text: 'Kaynak'),
            ],
          ),
          SizedBox(
            height: 420,
            child: TabBarView(
              children: [
                _SummaryTab(summary: _summary, warnings: _warnings),
                _DataTab(
                  hasData: tableSpec != null && dataset != null,
                  emptyMessage:
                      'Bu analiz doğrulanmış bir veri kümesi üretmedi, '
                      'bu yüzden tablo gösterilemiyor.',
                  child: tableSpec != null && dataset != null
                      ? SingleChildScrollView(
                          child: TableSpecWidget(
                              tableSpec: tableSpec, dataset: dataset),
                        )
                      : null,
                ),
                _DataTab(
                  hasData: dataset != null && chartTypes.isNotEmpty,
                  emptyMessage: 'Bu analiz için grafik üretilmedi.',
                  child: dataset != null && chartTypes.isNotEmpty
                      ? SingleChildScrollView(
                          child: Column(
                            children: [
                              for (final type in chartTypes)
                                Padding(
                                  padding: const EdgeInsets.only(bottom: 12),
                                  child: ChartSpecNativeWidget(
                                      dataset: dataset, chartType: type),
                                ),
                            ],
                          ),
                        )
                      : null,
                ),
                _SourceTab(
                  datasetId: result['result_dataset_id']?.toString(),
                  quality: result['data_quality_summary'],
                  prompt: result['request_prompt']?.toString(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _SummaryTab extends StatelessWidget {
  final String summary;
  final List<dynamic> warnings;

  const _SummaryTab({required this.summary, required this.warnings});

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(SemanticTokens.spacingMd),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(summary, style: const TextStyle(fontSize: 15, height: 1.5)),
          if (warnings.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Veri kalitesi uyarıları',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
            const SizedBox(height: 6),
            for (final warning in warnings)
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: Text('• ${warning.toString()}',
                    style: const TextStyle(fontSize: 12.5, color: Colors.grey)),
              ),
          ],
        ],
      ),
    );
  }
}

/// A data tab either renders server-verified content or explains its absence.
class _DataTab extends StatelessWidget {
  final bool hasData;
  final String emptyMessage;
  final Widget? child;

  const _DataTab({
    required this.hasData,
    required this.emptyMessage,
    this.child,
  });

  @override
  Widget build(BuildContext context) {
    if (hasData && child != null) return child!;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(emptyMessage,
            textAlign: TextAlign.center,
            style: const TextStyle(color: Colors.grey)),
      ),
    );
  }
}

class _SourceTab extends StatelessWidget {
  final String? datasetId;
  final Object? quality;
  final String? prompt;

  const _SourceTab({this.datasetId, this.quality, this.prompt});

  @override
  Widget build(BuildContext context) {
    final summary = quality is Map<String, dynamic>
        ? quality as Map<String, dynamic>
        : const <String, dynamic>{};

    return ListView(
      padding: const EdgeInsets.all(SemanticTokens.spacingMd),
      children: [
        if (prompt != null && prompt!.isNotEmpty) ...[
          const Text('Soru',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
          const SizedBox(height: 4),
          Text(prompt!, style: const TextStyle(fontSize: 13.5)),
          const SizedBox(height: 16),
        ],
        const Text('Veri kümesi',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
        const SizedBox(height: 4),
        Text(datasetId ?? 'Bu analiz bir veri kümesine bağlanmadı.',
            style: const TextStyle(fontSize: 12.5, color: Colors.grey)),
        if (summary.isNotEmpty) ...[
          const SizedBox(height: 16),
          const Text('Veri kalitesi',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 13)),
          const SizedBox(height: 4),
          for (final entry in summary.entries)
            Padding(
              padding: const EdgeInsets.only(bottom: 3),
              child: Text('${entry.key}: ${entry.value}',
                  style: const TextStyle(fontSize: 12.5, color: Colors.grey)),
            ),
        ],
        const SizedBox(height: 16),
        const Text(
          'Tablodaki bir hücreye dokunarak değerin alındığı belgeye ulaşabilirsiniz.',
          style: TextStyle(fontSize: 12, color: Colors.grey),
        ),
      ],
    );
  }
}
