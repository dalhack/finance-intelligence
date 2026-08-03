import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/navigation_shell.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../presentation/providers/providers.dart';
import '../../../presentation/state/async_value_state.dart';
import '../../analysis/presentation/analysis_composer_screen.dart';

class MainDashboardScreen extends ConsumerStatefulWidget {
  const MainDashboardScreen({super.key});

  @override
  ConsumerState<MainDashboardScreen> createState() =>
      _MainDashboardScreenState();
}

class _MainDashboardScreenState extends ConsumerState<MainDashboardScreen> {
  final TextEditingController _queryController = TextEditingController();
  final bool _showOrchestrationBanner = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(documentListControllerProvider.notifier).loadDocuments();
      ref.read(factReviewControllerProvider.notifier).loadCandidates();
    });
  }

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  void _handlePromptSubmit() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => const AnalysisComposerScreen(),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final docState = ref.watch(documentListControllerProvider);
    final candState = ref.watch(factReviewControllerProvider);

    final int docCount =
        docState.status == AsyncStatus.success && docState.data != null
            ? docState.data!.length
            : 0;
    final int candCount =
        candState.status == AsyncStatus.success && candState.data != null
            ? candState.data!.length
            : 0;

    return Scaffold(
      appBar: AppBar(
        title:
            const Text('Finance Intelligence', style: TextStyle(fontSize: 16)),
        actions: const [
          Padding(
            padding: EdgeInsets.only(right: 12.0),
            child: Icon(Icons.business_center, size: 20),
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(SemanticTokens.spacingMd),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            // Filter Bar
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  ActionChip(
                    avatar:
                        const Icon(Icons.account_balance_outlined, size: 16),
                    label: const Text('Kurumlar: Tümü'),
                    onPressed: () {},
                  ),
                  const SizedBox(width: SemanticTokens.spacingSm),
                  ActionChip(
                    avatar: const Icon(Icons.calendar_today_outlined, size: 16),
                    label: const Text('Dönem: Tümü'),
                    onPressed: () {},
                  ),
                ],
              ),
            ),
            const SizedBox(height: SemanticTokens.spacingMd),

            // Large Prompt Input Card
            Card(
              child: Padding(
                padding: const EdgeInsets.all(SemanticTokens.spacingMd),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    TextField(
                      controller: _queryController,
                      maxLines: 3,
                      decoration: const InputDecoration(
                        hintText:
                            'Finansal karşılaştırma veya analiz sorunuzu yazın...',
                        border: InputBorder.none,
                      ),
                    ),
                    const Divider(),
                    if (_showOrchestrationBanner)
                      Container(
                        margin: const EdgeInsets.only(bottom: 12.0),
                        padding: const EdgeInsets.all(12.0),
                        decoration: BoxDecoration(
                          color: SemanticTokens.warningAmberLight
                              .withValues(alpha: 0.1),
                          border: Border.all(
                              color: SemanticTokens.warningAmberLight),
                          borderRadius:
                              BorderRadius.circular(SemanticTokens.radiusSm),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Row(
                              children: [
                                Icon(Icons.info_outline,
                                    color: SemanticTokens.warningAmberLight,
                                    size: 20),
                                SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    'Analiz orkestrasyonu sonraki aşamada (Aşama 4) etkinleştirilecektir.',
                                    style: TextStyle(
                                        fontSize: 13,
                                        color: SemanticTokens.warningAmberLight,
                                        fontWeight: FontWeight.bold),
                                  ),
                                ),
                              ],
                            ),
                            Align(
                              alignment: Alignment.centerRight,
                              child: TextButton(
                                onPressed: () {
                                  Navigator.push(
                                    context,
                                    MaterialPageRoute(
                                      builder: (_) =>
                                          const NavigationShell(initialTab: 3),
                                    ),
                                  );
                                },
                                child: const Text('Karşılaştır'),
                              ),
                            ),
                          ],
                        ),
                      ),
                    Wrap(
                      alignment: WrapAlignment.spaceBetween,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        OutlinedButton.icon(
                          onPressed: () {
                            Navigator.push(
                              context,
                              MaterialPageRoute(
                                builder: (_) =>
                                    const NavigationShell(initialTab: 1),
                              ),
                            );
                          },
                          icon: const Icon(Icons.attach_file, size: 18),
                          label: const Text('Belgeler'),
                        ),
                        ElevatedButton.icon(
                          onPressed: _handlePromptSubmit,
                          icon: const Icon(Icons.send),
                          label: const Text('Gönder'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: SemanticTokens.spacingLg),

            // Status Overview Section
            const Text(
              'Dahili Durum Özeti',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: SemanticTokens.spacingSm),
            Wrap(
              spacing: 12,
              runSpacing: 12,
              children: [
                ConstrainedBox(
                  constraints:
                      const BoxConstraints(minWidth: 140, maxWidth: 200),
                  child: Card(
                    color: Theme.of(context).colorScheme.surface,
                    child: Padding(
                      padding: const EdgeInsets.all(12.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.description,
                                  color: SemanticTokens.accentTealLight,
                                  size: 18),
                              SizedBox(width: 4),
                              Expanded(
                                child: Text(
                                  'Yüklü Belge',
                                  style: TextStyle(
                                      fontWeight: FontWeight.w600,
                                      fontSize: 12),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Text(
                              '$docCount Belge',
                              style: Theme.of(context)
                                  .textTheme
                                  .titleMedium
                                  ?.copyWith(fontWeight: FontWeight.bold),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
                ConstrainedBox(
                  constraints:
                      const BoxConstraints(minWidth: 140, maxWidth: 200),
                  child: Card(
                    color: Theme.of(context).colorScheme.surface,
                    child: Padding(
                      padding: const EdgeInsets.all(12.0),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          const Row(
                            children: [
                              Icon(Icons.fact_check,
                                  color: SemanticTokens.warningAmberLight,
                                  size: 18),
                              SizedBox(width: 4),
                              Expanded(
                                child: Text(
                                  'İnceleme',
                                  style: TextStyle(
                                      fontWeight: FontWeight.w600,
                                      fontSize: 12),
                                  overflow: TextOverflow.ellipsis,
                                ),
                              ),
                            ],
                          ),
                          const SizedBox(height: 8),
                          FittedBox(
                            fit: BoxFit.scaleDown,
                            child: Row(
                              children: [
                                Text(
                                  '$candCount Aday',
                                  style: Theme.of(context)
                                      .textTheme
                                      .titleMedium
                                      ?.copyWith(fontWeight: FontWeight.bold),
                                ),
                                if (candCount > 0) ...[
                                  const SizedBox(width: 6),
                                  Container(
                                    width: 8,
                                    height: 8,
                                    decoration: const BoxDecoration(
                                      color: SemanticTokens.errorRedLight,
                                      shape: BoxShape.circle,
                                    ),
                                  ),
                                ],
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: SemanticTokens.spacingLg),

            // Recent Analysis Section
            const Text(
              'Son Analizler',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: SemanticTokens.spacingSm),
            Card(
              child: ListTile(
                leading: const Icon(Icons.analytics_outlined,
                    color: SemanticTokens.primaryBlueLight),
                title: const Text('Yapılandırılmış Karşılaştırma Analizi'),
                subtitle: const Text(
                    'Schema: 3.0.0 • Metrik ve Kurum Karşılaştırma Modülü'),
                trailing: const Icon(Icons.chevron_right),
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (_) => const NavigationShell(initialTab: 3),
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
