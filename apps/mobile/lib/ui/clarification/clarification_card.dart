import 'package:flutter/material.dart';
import '../../data/models/clarification_models.dart';

class ClarificationCard extends StatelessWidget {
  final ClarificationModel clarification;
  final Function(Map<String, dynamic> payload) onSubmit;
  final VoidCallback onCancel;
  final bool isSubmitting;

  const ClarificationCard({
    super.key,
    required this.clarification,
    required this.onSubmit,
    required this.onCancel,
    this.isSubmitting = false,
  });

  String _getLocalizedTitle(String promptKey) {
    switch (promptKey) {
      case 'clarification.select_institution':
        return 'Lütfen Kurumu Seçiniz';
      case 'clarification.select_period':
        return 'Lütfen Raporlama Dönemini Seçiniz';
      case 'clarification.select_basis':
        return 'Lütfen Raporlama Esasını Seçiniz';
      case 'clarification.select_measure':
        return 'Lütfen Analiz Metriğini Seçiniz';
      default:
        return 'Ek Bilgi Gereklidir';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.all(16.0),
      elevation: 4.0,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12.0)),
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              children: [
                const Icon(Icons.help_outline, color: Colors.blue, size: 28),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _getLocalizedTitle(clarification.promptKey),
                    style: Theme.of(context).textTheme.titleMedium?.copyWith(
                          fontWeight: FontWeight.bold,
                        ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Text(
              clarification.question,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
            const SizedBox(height: 16),
            if (clarification.options.isNotEmpty)
              ...clarification.options.map((opt) => Padding(
                    padding: const EdgeInsets.only(bottom: 8.0),
                    child: SizedBox(
                      width: double.infinity,
                      height: 48, // 44+ touch target
                      child: ElevatedButton(
                        key: Key('clarification_option_${opt.id}'),
                        onPressed: isSubmitting
                            ? null
                            : () {
                                onSubmit({
                                  'option_id': opt.id,
                                  if (opt.value != null) 'value': opt.value,
                                });
                              },
                        child: Text(opt.label),
                      ),
                    ),
                  ))
            else
              SizedBox(
                width: double.infinity,
                height: 48,
                child: ElevatedButton(
                  key: const Key('clarification_confirm_button'),
                  onPressed:
                      isSubmitting ? null : () => onSubmit({'confirmed': true}),
                  child: isSubmitting
                      ? const SizedBox(
                          width: 24,
                          height: 24,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Text('Devam Et'),
                ),
              ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(
                key: const Key('clarification_cancel_button'),
                onPressed: isSubmitting ? null : onCancel,
                child: const Text('Analizi İptal Et',
                    style: TextStyle(color: Colors.red)),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
