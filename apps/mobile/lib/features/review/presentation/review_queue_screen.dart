import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../presentation/providers/providers.dart';
import '../../../presentation/state/async_value_state.dart';
import 'candidate_detail_bottom_sheet.dart';

class ReviewQueueScreen extends ConsumerStatefulWidget {
  const ReviewQueueScreen({super.key});

  @override
  ConsumerState<ReviewQueueScreen> createState() => _ReviewQueueScreenState();
}

class _ReviewQueueScreenState extends ConsumerState<ReviewQueueScreen> {
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(factReviewControllerProvider.notifier).loadCandidates();
    });
  }

  void _openCandidateDetail(Map<String, dynamic> candidate) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => CandidateDetailBottomSheet(candidate: candidate),
    );
  }

  @override
  Widget build(BuildContext context) {
    final uiState = ref.watch(factReviewControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('İnceleme Kuyruğu'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.read(factReviewControllerProvider.notifier).loadCandidates();
            },
          ),
        ],
      ),
      body: _buildContent(uiState),
    );
  }

  Widget _buildContent(UiState<List<Map<String, dynamic>>> uiState) {
    if (uiState.isLoading) {
      return const Center(child: CircularProgressIndicator());
    }

    if (uiState.exception != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(16.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.error_outline,
                  size: 48, color: SemanticTokens.errorRedLight),
              const SizedBox(height: 8),
              Text(
                  uiState.exception?.message ??
                      'Adaylar yüklenirken bir hata oluştu.',
                  textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => ref
                    .read(factReviewControllerProvider.notifier)
                    .loadCandidates(),
                child: const Text('Yeniden Dene'),
              ),
            ],
          ),
        ),
      );
    }

    final candidates = uiState.data ?? [];
    if (candidates.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_circle_outline,
                size: 64, color: SemanticTokens.verifiedGreenLight),
            SizedBox(height: 16),
            Text('İncelenecek aday bulunmuyor.',
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
          ],
        ),
      );
    }

    return ListView.builder(
      itemCount: candidates.length,
      itemBuilder: (context, index) {
        final cand = candidates[index];
        final bool isConflict =
            cand['is_conflict'] == true || cand['isConflict'] == true;

        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Padding(
            padding: const EdgeInsets.all(12.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                        cand['institution_name']?.toString() ??
                            cand['institutionName']?.toString() ??
                            'Kurum',
                        style: const TextStyle(
                            fontWeight: FontWeight.bold, fontSize: 16)),
                    if (isConflict)
                      const Chip(
                        label: Text('409 ÇAKIŞMA',
                            style: TextStyle(
                                color: Colors.white,
                                fontSize: 10,
                                fontWeight: FontWeight.bold)),
                        backgroundColor: SemanticTokens.errorRedLight,
                      ),
                  ],
                ),
                Text(
                    '${cand['metric_label'] ?? cand['metricLabel'] ?? 'Metrik'} • ${cand['period_label'] ?? cand['periodLabel'] ?? ''}'),
                const SizedBox(height: 4),
                Text(
                    'Aday Değer: ${cand['display_value'] ?? cand['displayValue'] ?? cand['raw_value'] ?? ''}',
                    style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        color: SemanticTokens.primaryNavyLight)),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                        'Güven Skoru: %${(((cand['confidence'] as num?)?.toDouble() ?? 0.9) * 100).toInt()}',
                        style:
                            const TextStyle(color: Colors.grey, fontSize: 12)),
                    ElevatedButton.icon(
                      onPressed: () => _openCandidateDetail(cand),
                      icon: const Icon(Icons.search, size: 16),
                      label: const Text('İncele'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
