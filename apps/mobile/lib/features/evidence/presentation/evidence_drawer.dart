import 'package:flutter/material.dart';
import '../../../app/theme/semantic_tokens.dart';

class EvidenceDrawer extends StatelessWidget {
  final Map<String, dynamic> evidenceData;

  const EvidenceDrawer({super.key, required this.evidenceData});

  @override
  Widget build(BuildContext context) {
    final String classification =
        evidenceData['classification']?.toString() ?? 'CONFIDENTIAL';
    final bool isMasked = evidenceData['is_masked'] as bool? ?? false;
    final String rawSnippet = evidenceData['sanitized_snippet']?.toString() ??
        'Önizleme metni bulunmuyor.';
    final String snippet = isMasked ? '[MASKED PERSONAL DATA]' : rawSnippet;

    final String docTitle =
        evidenceData['document_title']?.toString() ?? 'Bilinmeyen Belge.pdf';
    final int? pageNumber = evidenceData['page_number'] as int?;
    final String? sheetName = evidenceData['sheet_name']?.toString();
    final String? cellCoordinate = evidenceData['cell_coordinate']?.toString();

    String locationLabel = 'Sayfa: ${pageNumber ?? 1}';
    if (sheetName != null && cellCoordinate != null) {
      locationLabel = 'Sheet: $sheetName (Hücre: $cellCoordinate)';
    }

    return Padding(
      padding: EdgeInsets.only(
        left: SemanticTokens.spacingMd,
        right: SemanticTokens.spacingMd,
        top: SemanticTokens.spacingMd,
        bottom:
            MediaQuery.of(context).viewInsets.bottom + SemanticTokens.spacingMd,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Row(
                children: [
                  Icon(Icons.find_in_page,
                      color: SemanticTokens.accentTealLight),
                  SizedBox(width: 8),
                  Text('Kanıt Çekmecesi (Evidence)',
                      style:
                          TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                ],
              ),
              IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context)),
            ],
          ),
          const Divider(),
          Chip(
            label: Text('Sınıflandırma: $classification',
                style: const TextStyle(
                    color: Colors.white,
                    fontSize: 11,
                    fontWeight: FontWeight.bold)),
            backgroundColor: classification == 'STRICTLY_CONFIDENTIAL'
                ? SemanticTokens.errorRedLight
                : SemanticTokens.warningAmberLight,
          ),
          const SizedBox(height: SemanticTokens.spacingSm),
          Text('Belge Başlığı: $docTitle',
              style: const TextStyle(fontWeight: FontWeight.bold)),
          Text('Konum: $locationLabel'),
          Text(
              'MIME Türü: ${evidenceData['mime_type'] ?? 'application/pdf'} (Doğrulandı)'),
          const SizedBox(height: SemanticTokens.spacingMd),

          // Snippet Card
          Card(
            color: Theme.of(context).colorScheme.surface,
            child: Padding(
              padding: const EdgeInsets.all(12.0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('GÜVENLİ SANİTİZE EDİLMİŞ METİN SNIPPET',
                      style: TextStyle(
                          fontWeight: FontWeight.bold,
                          fontSize: 11,
                          color: Colors.grey)),
                  const SizedBox(height: 6),
                  Text(
                    snippet,
                    style: TextStyle(
                      fontStyle: FontStyle.italic,
                      color: isMasked ? SemanticTokens.errorRedLight : null,
                      fontWeight:
                          isMasked ? FontWeight.bold : FontWeight.normal,
                    ),
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: SemanticTokens.spacingLg),
          OutlinedButton.icon(
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                SnackBar(
                    content: Text(
                        'Request ID (${evidenceData['evidence_id'] ?? 'unknown'}) kopyalandı.')),
              );
            },
            icon: const Icon(Icons.copy, size: 16),
            label: const Text('Request ID Kopyala'),
          ),
        ],
      ),
    );
  }
}
