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

        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: Padding(
            padding: const EdgeInsets.all(12.0),
            child: CandidateCardContent(
              candidate: cand,
              onInspect: () => _openCandidateDetail(cand),
            ),
          ),
        );
      },
    );
  }
}

/// The readable content of one review candidate. Extracted so its wording can
/// be tested directly: a reviewer must never be shown a bare number.
class CandidateCardContent extends StatelessWidget {
  final Map<String, dynamic> candidate;
  final VoidCallback? onInspect;

  const CandidateCardContent(
      {super.key, required this.candidate, this.onInspect});

  @override
  Widget build(BuildContext context) {
    final cand = candidate;
    final bool isConflict =
        cand['is_conflict'] == true || cand['isConflict'] == true;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(
                cand['institution_name']?.toString() ??
                    cand['institutionName']?.toString() ??
                    'Kurum belirlenmedi',
                style:
                    const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
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
        Text(_candidateSubtitle(cand),
            style: const TextStyle(fontSize: 13, color: Colors.grey)),
        const SizedBox(height: 6),
        Row(
          crossAxisAlignment: CrossAxisAlignment.baseline,
          textBaseline: TextBaseline.alphabetic,
          children: [
            Flexible(
              child: Text(
                _candidateValue(cand),
                style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    fontSize: 20,
                    color: SemanticTokens.primaryNavyLight),
              ),
            ),
            const SizedBox(width: 6),
            Text(_candidateUnit(cand),
                style: const TextStyle(fontSize: 11, color: Colors.grey)),
          ],
        ),
        const SizedBox(height: 8),
        if (_extractionLabel(cand) != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Wrap(
              spacing: 6,
              runSpacing: 4,
              children: [
                _MiniChip(text: _extractionLabel(cand)!, highlight: true),
                _MiniChip(
                    text:
                        'Güven %${(((cand['confidence_score'] as num?)?.toDouble() ?? (cand['confidence'] as num?)?.toDouble() ?? 0.9) * 100).toInt()}'),
              ],
            ),
          ),
        if (_evidenceLine(cand) != null)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
            decoration: BoxDecoration(
              color: Colors.grey.withValues(alpha: 0.10),
              border: const Border(
                  left: BorderSide(
                      color: SemanticTokens.verifiedGreenLight, width: 3)),
              borderRadius:
                  const BorderRadius.horizontal(right: Radius.circular(8)),
            ),
            child: Text(_evidenceLine(cand)!,
                style: const TextStyle(fontSize: 11.5, color: Colors.grey)),
          ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(_candidateStatusLabel(cand),
                style: const TextStyle(color: Colors.grey, fontSize: 12)),
            ElevatedButton.icon(
              onPressed: onInspect,
              icon: const Icon(Icons.search, size: 16),
              label: const Text('İncele'),
            ),
          ],
        ),
      ],
    );
  }
}

/// Reviewer-facing wording for a candidate row. The API now sends the resolved
/// institution, metric and period; the raw label is the fallback so a value is
/// never presented without saying what it is.
String _candidateSubtitle(Map<String, dynamic> cand) {
  final metric = cand['metric_label']?.toString() ??
      cand['suggested_metric_code']?.toString() ??
      cand['raw_label']?.toString() ??
      'Tanımsız kalem';
  final period = cand['period_label']?.toString() ?? '';
  final basis = cand['detected_reporting_basis']?.toString() ?? '';
  return [metric, period, if (basis.isNotEmpty && basis != 'UNKNOWN') basis]
      .where((part) => part.isNotEmpty)
      .join(' · ');
}

String _candidateValue(Map<String, dynamic> cand) =>
    cand['raw_value']?.toString() ??
    cand['display_value']?.toString() ??
    cand['normalized_value']?.toString() ??
    '—';

String _candidateUnit(Map<String, dynamic> cand) {
  final currency = cand['raw_currency']?.toString() ?? '';
  final scale = cand['raw_scale']?.toString() ?? '';
  const scaleLabels = {
    'THOUSAND': 'Bin',
    'MILLION': 'Milyon',
    'BILLION': 'Milyar',
  };
  return [scaleLabels[scale] ?? '', currency]
      .where((part) => part.isNotEmpty)
      .join(' ');
}

String? _extractionLabel(Map<String, dynamic> cand) {
  switch (cand['extraction_method']?.toString()) {
    case 'LLM_ASSISTED':
      return 'Model okuması';
    case 'PARSER_TABLE':
      return 'Tablo okuması';
    case null:
      return null;
    default:
      return cand['extraction_method']?.toString();
  }
}

/// Where in the document the number was read from, so the reviewer can check it.
String? _evidenceLine(Map<String, dynamic> cand) {
  final snippet = cand['evidence_snippet']?.toString();
  final page = cand['source_page'];
  if (snippet == null || snippet.isEmpty) return null;
  return page == null ? snippet : 's.$page · $snippet';
}

String _candidateStatusLabel(Map<String, dynamic> cand) {
  final status = cand['review_status']?.toString();
  return status == 'PENDING' ? 'Onay bekliyor' : (status ?? '');
}

class _MiniChip extends StatelessWidget {
  final String text;
  final bool highlight;

  const _MiniChip({required this.text, this.highlight = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
      decoration: BoxDecoration(
        color: highlight
            ? SemanticTokens.verifiedGreenLight.withValues(alpha: 0.15)
            : Colors.grey.withValues(alpha: 0.14),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(text,
          style: TextStyle(
              fontSize: 11,
              color: highlight
                  ? SemanticTokens.verifiedGreenLight
                  : Colors.grey.shade700)),
    );
  }
}
