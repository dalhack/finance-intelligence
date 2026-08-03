import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../core/models/wire_models.dart';
import '../../../presentation/providers/providers.dart';
import '../../../presentation/state/async_value_state.dart';
import 'comparison_result_screen.dart';

class ComparisonBuilderScreen extends ConsumerStatefulWidget {
  const ComparisonBuilderScreen({super.key});

  @override
  ConsumerState<ComparisonBuilderScreen> createState() =>
      _ComparisonBuilderScreenState();
}

class _ComparisonBuilderScreenState
    extends ConsumerState<ComparisonBuilderScreen> {
  final List<String> _selectedInstitutions = ['inst-garan', 'inst-akbnk'];
  final List<String> _selectedPeriods = ['period-2025-q4'];
  final List<String> _selectedMeasures = ['TOTAL_ASSETS', 'NPL_RATIO'];
  String _sourcePolicy = 'BOTH_SEPARATE_SERIES';
  String _reportingBasis = 'SOLO';
  String _chartType = 'vertical_bar';
  bool _isExecuting = false;

  void _executeComparison() async {
    if (_selectedInstitutions.length < 2) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Form Hatası: En az 2 kurum seçilmelidir.')),
      );
      return;
    }
    if (_selectedPeriods.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Form Hatası: En az 1 dönem seçilmelidir.')),
      );
      return;
    }
    if (_selectedMeasures.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
            content: Text('Form Hatası: En az 1 semantik ölçü seçilmelidir.')),
      );
      return;
    }

    setState(() => _isExecuting = true);

    final req = ComparisonRequest(
      institutionIds: _selectedInstitutions,
      reportingPeriodIds: _selectedPeriods,
      semanticMeasures: _selectedMeasures
          .map((m) => SemanticMeasureSelector(semanticMeasureCode: m))
          .toList(),
      valueSourcePolicy: _sourcePolicy,
      reportingBasis: _reportingBasis,
    );

    try {
      await ref
          .read(comparisonControllerProvider.notifier)
          .executeComparison(req);
      final state = ref.read(comparisonControllerProvider);

      if (!mounted) return;
      setState(() => _isExecuting = false);

      if (state.status == AsyncStatus.success && state.data != null) {
        final dataset = state.data!;
        final tableSpec = TableSpec(
          resultDatasetId: dataset.resultDatasetId,
          schemaVersion: dataset.schemaVersion,
          columns: const [
            TableColumn(
                key: 'institution_name',
                title: 'Institution',
                dataType: 'string',
                unitLabel: 'Text'),
            TableColumn(
                key: 'period_label',
                title: 'Period',
                dataType: 'string',
                unitLabel: 'Text'),
            TableColumn(
                key: 'TOTAL_ASSETS',
                title: 'Total Assets',
                dataType: 'decimal',
                unitLabel: 'TRY (MILLION)'),
          ],
          rows: const [],
          pagination: dataset.pagination,
        );

        Navigator.push(
          context,
          MaterialPageRoute(
            builder: (_) => ComparisonResultScreen(
              dataset: dataset,
              tableSpec: tableSpec,
              chartType: _chartType,
            ),
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(state.exception?.message ??
                  'Karşılaştırma yürütülürken hata oluştu.')),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() => _isExecuting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('İstek Hatası: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Karşılaştırma Oluşturucu'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(SemanticTokens.spacingMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Institution Selection Section
            const Text('KURUM SEÇİMİ (En az 2)',
                style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: SemanticTokens.spacingSm),
            Wrap(
              spacing: 8,
              children: [
                FilterChip(
                  label: const Text('Garanti BBVA'),
                  selected: _selectedInstitutions.contains('inst-garan'),
                  onSelected: (val) {
                    setState(() {
                      val
                          ? _selectedInstitutions.add('inst-garan')
                          : _selectedInstitutions.remove('inst-garan');
                    });
                  },
                ),
                FilterChip(
                  label: const Text('Akbank A.Ş.'),
                  selected: _selectedInstitutions.contains('inst-akbnk'),
                  onSelected: (val) {
                    setState(() {
                      val
                          ? _selectedInstitutions.add('inst-akbnk')
                          : _selectedInstitutions.remove('inst-akbnk');
                    });
                  },
                ),
                FilterChip(
                  label: const Text('Yapı Kredi'),
                  selected: _selectedInstitutions.contains('inst-ykb'),
                  onSelected: (val) {
                    setState(() {
                      val
                          ? _selectedInstitutions.add('inst-ykb')
                          : _selectedInstitutions.remove('inst-ykb');
                    });
                  },
                ),
              ],
            ),
            const SizedBox(height: SemanticTokens.spacingLg),

            // Period Selection Section
            const Text('DÖNEM SEÇİMİ (En az 1)',
                style: TextStyle(fontWeight: FontWeight.bold)),
            const SizedBox(height: SemanticTokens.spacingSm),
            Wrap(
              spacing: 8,
              children: [
                FilterChip(
                  label: const Text('2025/Q4'),
                  selected: _selectedPeriods.contains('period-2025-q4'),
                  onSelected: (val) {
                    setState(() {
                      val
                          ? _selectedPeriods.add('period-2025-q4')
                          : _selectedPeriods.remove('period-2025-q4');
                    });
                  },
                ),
                FilterChip(
                  label: const Text('2024/Q4'),
                  selected: _selectedPeriods.contains('period-2024-q4'),
                  onSelected: (val) {
                    setState(() {
                      val
                          ? _selectedPeriods.add('period-2024-q4')
                          : _selectedPeriods.remove('period-2024-q4');
                    });
                  },
                ),
              ],
            ),
            const SizedBox(height: SemanticTokens.spacingLg),

            // Options Form
            DropdownButtonFormField<String>(
              initialValue: _sourcePolicy,
              decoration: const InputDecoration(
                  labelText: 'Kaynak Politikası (Source Policy)'),
              items: const [
                DropdownMenuItem(
                    value: 'BOTH_SEPARATE_SERIES',
                    child: Text('BOTH_SEPARATE_SERIES (Tüm Seriler)')),
                DropdownMenuItem(
                    value: 'PREFER_SOURCE_REPORTED',
                    child:
                        Text('PREFER_SOURCE_REPORTED (Öncelikli Bildirilen)')),
                DropdownMenuItem(
                    value: 'PREFER_SYSTEM_DERIVED',
                    child:
                        Text('PREFER_SYSTEM_DERIVED (Öncelikli Hesaplanan)')),
              ],
              onChanged: (v) => setState(() => _sourcePolicy = v!),
            ),
            const SizedBox(height: SemanticTokens.spacingMd),
            DropdownButtonFormField<String>(
              initialValue: _reportingBasis,
              decoration: const InputDecoration(
                  labelText: 'Raporlama Esası (Reporting Basis)'),
              items: const [
                DropdownMenuItem(value: 'SOLO', child: Text('SOLO (Bireysel)')),
                DropdownMenuItem(
                    value: 'CONSOLIDATED',
                    child: Text('CONSOLIDATED (Konsolide)')),
              ],
              onChanged: (v) => setState(() => _reportingBasis = v!),
            ),
            const SizedBox(height: SemanticTokens.spacingMd),
            DropdownButtonFormField<String>(
              initialValue: _chartType,
              decoration: const InputDecoration(labelText: 'Grafik Türü'),
              items: const [
                DropdownMenuItem(
                    value: 'vertical_bar',
                    child: Text('Vertical Bar (Dikey Çubuk)')),
                DropdownMenuItem(
                    value: 'horizontal_bar',
                    child: Text('Horizontal Bar (Yatay Çubuk)')),
                DropdownMenuItem(
                    value: 'grouped_bar',
                    child: Text('Grouped Bar (Grup Çubuk)')),
                DropdownMenuItem(
                    value: 'line', child: Text('Line (Çizgi Grafik)')),
                DropdownMenuItem(
                    value: 'stacked_bar',
                    child: Text('Stacked Bar (Yığılmış Çubuk)')),
                DropdownMenuItem(
                    value: 'pie', child: Text('Pie (Pasta Grafik)')),
              ],
              onChanged: (v) => setState(() => _chartType = v!),
            ),
            const SizedBox(height: SemanticTokens.spacingXl),

            ElevatedButton.icon(
              onPressed: _isExecuting ? null : _executeComparison,
              icon: const Icon(Icons.analytics),
              label: Text(_isExecuting
                  ? 'Karşılaştırılıyor...'
                  : 'Karşılaştır ve Analizi Getir'),
            ),
          ],
        ),
      ),
    );
  }
}
