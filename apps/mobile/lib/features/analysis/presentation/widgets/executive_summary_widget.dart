import 'package:flutter/material.dart';

class ExecutiveSummaryWidget extends StatelessWidget {
  final String summaryText;

  const ExecutiveSummaryWidget({
    super.key,
    required this.summaryText,
  });

  @override
  Widget build(BuildContext context) {
    // Plain text safe rendering without HTML or script execution risks
    final sanitizedText = _sanitizeSummaryText(summaryText);

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.analytics, color: Colors.teal),
                SizedBox(width: 8),
                Text(
                  'Yönetici Özeti (Doğrulanmış)',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                ),
              ],
            ),
            const Divider(),
            SelectableText(
              sanitizedText,
              style: const TextStyle(
                  fontSize: 14, height: 1.4, color: Colors.black87),
            ),
          ],
        ),
      ),
    );
  }

  String _sanitizeSummaryText(String raw) {
    // Strip potential script tags or javascript: URIs for safety
    return raw
        .replaceAll(
            RegExp(r'<script.*?>.*?</script>', caseSensitive: false), '')
        .replaceAll(RegExp(r'javascript:', caseSensitive: false), '');
  }
}
