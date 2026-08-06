import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../presentation/providers/providers.dart';
import '../controllers/analysis_controller.dart';
import 'widgets/executive_summary_widget.dart';
import 'widgets/progress_timeline_widget.dart';

class AnalysisComposerScreen extends ConsumerStatefulWidget {
  const AnalysisComposerScreen({super.key});

  @override
  ConsumerState<AnalysisComposerScreen> createState() =>
      _AnalysisComposerScreenState();
}

class _AnalysisComposerScreenState
    extends ConsumerState<AnalysisComposerScreen> {
  final TextEditingController _promptController = TextEditingController();
  bool _internalOnly = false;
  String? _validationError;

  @override
  void dispose() {
    _promptController.dispose();
    super.dispose();
  }

  void _submitQuery() {
    final text = _promptController.text.trim();
    if (text.isEmpty) {
      setState(() {
        _validationError = 'Lütfen geçerli bir analiz sorusu giriniz.';
      });
      return;
    }

    setState(() {
      _validationError = null;
    });

    final idempotencyKey = 'idem-${DateTime.now().millisecondsSinceEpoch}';
    ref.read(analysisControllerProvider.notifier).submitAnalysis(
          prompt: text,
          idempotencyKey: idempotencyKey,
        );
  }

  void _showCancelConfirmation() {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Analizi İptal Et'),
        content: const Text(
          'Devam eden analiz işlemini iptal etmek istediğinize emin misiniz?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Vazgeç'),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            onPressed: () {
              Navigator.pop(ctx);
              ref
                  .read(analysisControllerProvider.notifier)
                  .cancelCurrentAnalysis();
            },
            child: const Text('İptal Et'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(analysisControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Finansal Akıllı Analiz (AI)'),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Soru ve Analiz Kompozisyonu',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _promptController,
              maxLines: 3,
              decoration: InputDecoration(
                hintText:
                    'Örn: Garanti Bankası 2025 Q4 Toplam Aktif ve Özkaynak karşılaştırması yapınız.',
                border: const OutlineInputBorder(),
                errorText: _validationError,
              ),
            ),
            const SizedBox(height: 12),
            CheckboxListTile(
              title:
                  const Text('Sadece Şirket İçi Doğrulanmış Belgeleri Kullan'),
              value: _internalOnly,
              onChanged: (val) {
                setState(() {
                  _internalOnly = val ?? false;
                });
              },
            ),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton.icon(
                    onPressed: state.isSubmitting ? null : _submitQuery,
                    icon: const Icon(Icons.send),
                    label: const Text('Analizi Başlat'),
                  ),
                ),
                if (state.statusState != AnalysisStatusState.idle &&
                    state.statusState != AnalysisStatusState.completed &&
                    state.statusState != AnalysisStatusState.cancelled &&
                    state.statusState !=
                        AnalysisStatusState.failedTerminal) ...[
                  const SizedBox(width: 12),
                  OutlinedButton.icon(
                    onPressed: _showCancelConfirmation,
                    icon: const Icon(Icons.cancel, color: Colors.red),
                    label: const Text('İptal Et',
                        style: TextStyle(color: Colors.red)),
                  ),
                ],
              ],
            ),
            const SizedBox(height: 24),
            if (state.statusState != AnalysisStatusState.idle) ...[
              ProgressTimelineWidget(
                statusState: state.statusState,
                warningMessage: state.warningMessage,
              ),
            ],
            if (state.resultSnapshot != null) ...[
              const SizedBox(height: 16),
              ExecutiveSummaryWidget(
                summaryText:
                    state.resultSnapshot!['result']?['summary']?.toString() ??
                        'Analiz başarıyla tamamlandı.',
              ),
            ],
            if (state.errorMessage != null) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                color: Colors.red.shade100,
                child: Text(
                  'Hata: ${state.errorMessage}',
                  style: const TextStyle(color: Colors.red),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
