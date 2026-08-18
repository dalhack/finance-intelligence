import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../presentation/providers/providers.dart';
import 'review_error_messages.dart';

class CandidateDetailBottomSheet extends ConsumerStatefulWidget {
  final Map<String, dynamic> candidate;

  const CandidateDetailBottomSheet({
    super.key,
    required this.candidate,
  });

  @override
  ConsumerState<CandidateDetailBottomSheet> createState() =>
      _CandidateDetailBottomSheetState();
}

class _CandidateDetailBottomSheetState
    extends ConsumerState<CandidateDetailBottomSheet> {
  final TextEditingController _rejectReasonController = TextEditingController();
  bool _isSubmitting = false;

  @override
  void dispose() {
    _rejectReasonController.dispose();
    super.dispose();
  }

  void _handleApprove() async {
    final candidateId = widget.candidate['id']?.toString() ??
        widget.candidate['candidate_id']?.toString() ??
        '';
    setState(() => _isSubmitting = true);

    try {
      await ref
          .read(factReviewControllerProvider.notifier)
          .approveCandidate(candidateId: candidateId);
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Aday başarıyla onaylandı.'),
          backgroundColor: SemanticTokens.verifiedGreenLight,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(reviewDecisionErrorMessage(e)),
            backgroundColor: SemanticTokens.errorRedLight),
      );
    }
  }

  void _handleReject() async {
    final reason = await showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Adayı Reddet'),
        content: TextField(
          controller: _rejectReasonController,
          decoration:
              const InputDecoration(labelText: 'Reddedilme Nedeni (Zorunlu)'),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx), child: const Text('İptal')),
          ElevatedButton(
            onPressed: () =>
                Navigator.pop(ctx, _rejectReasonController.text.trim()),
            child: const Text('Reddet'),
          ),
        ],
      ),
    );

    if (reason == null || reason.isEmpty) return;

    final candidateId = widget.candidate['id']?.toString() ??
        widget.candidate['candidate_id']?.toString() ??
        '';
    setState(() => _isSubmitting = true);

    try {
      await ref
          .read(factReviewControllerProvider.notifier)
          .rejectCandidate(candidateId: candidateId, reason: reason);
      if (!mounted) return;
      Navigator.pop(context);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Aday reddedildi.'),
          backgroundColor: SemanticTokens.warningAmberLight,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() => _isSubmitting = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(reviewDecisionErrorMessage(e)),
            backgroundColor: SemanticTokens.errorRedLight),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final cand = widget.candidate;
    final bool isConflict =
        cand['is_conflict'] == true || cand['isConflict'] == true;
    final String metricLabel = cand['metric_label']?.toString() ??
        cand['metricLabel']?.toString() ??
        'Metrik Detayı';

    return Padding(
      padding: EdgeInsets.only(
        left: SemanticTokens.spacingMd,
        right: SemanticTokens.spacingMd,
        top: SemanticTokens.spacingMd,
        bottom:
            MediaQuery.of(context).viewInsets.bottom + SemanticTokens.spacingMd,
      ),
      child: SingleChildScrollView(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(metricLabel,
                    style: const TextStyle(
                        fontSize: 18, fontWeight: FontWeight.bold)),
                IconButton(
                    icon: const Icon(Icons.close),
                    onPressed: () => Navigator.pop(context)),
              ],
            ),
            const Divider(),
            if (isConflict)
              Container(
                padding: const EdgeInsets.all(12.0),
                margin: const EdgeInsets.only(bottom: 12.0),
                decoration: BoxDecoration(
                  color: SemanticTokens.errorRedLight.withValues(alpha: 0.1),
                  border: Border.all(color: SemanticTokens.errorRedLight),
                  borderRadius: BorderRadius.circular(SemanticTokens.radiusSm),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('🔴 ÇAKIŞMA UYARISI (409 CONFLICT)',
                        style: TextStyle(
                            fontWeight: FontWeight.bold,
                            color: SemanticTokens.errorRedLight)),
                    const SizedBox(height: 4),
                    Text(
                        'Mevcut Değer: ${cand['existing_value'] ?? cand['existingValue'] ?? '12,100,000 TRY'}'),
                    Text(
                        'Aday Değer: ${cand['display_value'] ?? cand['displayValue'] ?? ''}'),
                  ],
                ),
              ),

            // Details
            Text(
                'Kurum: ${cand['institution_name'] ?? cand['institutionName'] ?? ''}'),
            Text(
                'Dönem: ${cand['period_label'] ?? cand['periodLabel'] ?? ''} (${cand['reporting_basis'] ?? cand['reportingBasis'] ?? 'SOLO'})'),
            Text('Ham Değer: ${cand['raw_value'] ?? cand['rawValue'] ?? ''}'),
            Text(
                'Kanonik Değer: ${cand['canonical_value'] ?? cand['canonicalValue'] ?? ''}'),
            const SizedBox(height: SemanticTokens.spacingMd),

            // Coordinate Preview
            Card(
              color: Theme.of(context).colorScheme.surface,
              child: Padding(
                padding: const EdgeInsets.all(12.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('KOORDİNAT VE KANIT ÖNİZLEME',
                        style: TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 12,
                            color: Colors.grey)),
                    const SizedBox(height: 4),
                    Text(
                        'Belge: ${cand['document_title'] ?? cand['documentTitle'] ?? 'Belge.pdf'}'),
                    Text('Snippet: "${cand['snippet'] ?? 'Metin kanıtı'}"',
                        style: const TextStyle(fontStyle: FontStyle.italic)),
                  ],
                ),
              ),
            ),
            const SizedBox(height: SemanticTokens.spacingLg),

            if (_isSubmitting)
              const Center(child: CircularProgressIndicator())
            else
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: _handleReject,
                      style: OutlinedButton.styleFrom(
                          foregroundColor: SemanticTokens.errorRedLight),
                      child: const Text('Reddet'),
                    ),
                  ),
                  const SizedBox(width: SemanticTokens.spacingSm),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: _handleApprove,
                      style: ElevatedButton.styleFrom(
                          backgroundColor: SemanticTokens.verifiedGreenLight,
                          foregroundColor: Colors.white),
                      child: const Text('Onayla'),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
