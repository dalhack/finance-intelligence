import 'package:flutter/material.dart';

import '../../controllers/analysis_controller.dart';

class ProgressTimelineWidget extends StatelessWidget {
  final AnalysisStatusState statusState;
  final String? warningMessage;

  const ProgressTimelineWidget({
    super.key,
    required this.statusState,
    this.warningMessage,
  });

  @override
  Widget build(BuildContext context) {
    final steps = [
      _ProgressStep('Talep Alındı', AnalysisStatusState.accepted),
      _ProgressStep('İstek Anlaşılıyor', AnalysisStatusState.understanding),
      _ProgressStep('Plan Hazırlanıyor', AnalysisStatusState.planning),
      _ProgressStep(
          'Finansal Veriler İşleniyor', AnalysisStatusState.executingTools),
      _ProgressStep(
          'Sonuçlar Doğrulanıyor', AnalysisStatusState.validatingResults),
      _ProgressStep('Tamamlandı', AnalysisStatusState.completed),
    ];

    final currentIndex = _getCurrentStepIndex();

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Analiz İlerleme Durumu',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 12),
            if (warningMessage != null) ...[
              Container(
                padding: const EdgeInsets.all(8),
                color: Colors.amber.shade100,
                child: Text('Uyarı: $warningMessage',
                    style: const TextStyle(color: Colors.amber)),
              ),
              const SizedBox(height: 8),
            ],
            for (int i = 0; i < steps.length; i++) ...[
              Row(
                children: [
                  Icon(
                    i < currentIndex
                        ? Icons.check_circle
                        : (i == currentIndex
                            ? Icons.hourglass_top
                            : Icons.radio_button_unchecked),
                    color: i <= currentIndex ? Colors.teal : Colors.grey,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    steps[i].label,
                    style: TextStyle(
                      fontWeight: i == currentIndex
                          ? FontWeight.bold
                          : FontWeight.normal,
                      color: i <= currentIndex ? Colors.black87 : Colors.grey,
                    ),
                  ),
                ],
              ),
              if (i < steps.length - 1)
                Padding(
                  padding: const EdgeInsets.only(left: 11),
                  child: Container(
                    height: 16,
                    width: 2,
                    color:
                        i < currentIndex ? Colors.teal : Colors.grey.shade300,
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }

  int _getCurrentStepIndex() {
    switch (statusState) {
      case AnalysisStatusState.accepted:
        return 0;
      case AnalysisStatusState.understanding:
        return 1;
      case AnalysisStatusState.planning:
        return 2;
      case AnalysisStatusState.executingTools:
        return 3;
      case AnalysisStatusState.validatingResults:
        return 4;
      case AnalysisStatusState.completed:
        return 5;
      default:
        return 0;
    }
  }
}

class _ProgressStep {
  final String label;
  final AnalysisStatusState state;

  _ProgressStep(this.label, this.state);
}
