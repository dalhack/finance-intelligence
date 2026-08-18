import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../presentation/providers/providers.dart';
import '../../../core/models/wire_models.dart';
import '../../../presentation/state/async_value_state.dart';
import 'upload_bottom_sheet.dart';

class DocumentManagementScreen extends ConsumerStatefulWidget {
  const DocumentManagementScreen({super.key});

  @override
  ConsumerState<DocumentManagementScreen> createState() =>
      _DocumentManagementScreenState();
}

class _DocumentManagementScreenState
    extends ConsumerState<DocumentManagementScreen> {
  /// Ingestion runs in the background, so the screen keeps polling while a
  /// document is still being processed. Without this the user is left guessing
  /// whether anything is happening.
  static const _pollInterval = Duration(seconds: 5);
  static const _maxPolls = 36; // ~3 minutes

  Timer? _poller;
  int _pollsRemaining = 0;
  bool _wasProcessing = false;

  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(documentListControllerProvider.notifier).loadDocuments();
    });
  }

  @override
  void dispose() {
    _poller?.cancel();
    super.dispose();
  }

  void _startWatching() {
    _pollsRemaining = _maxPolls;
    _poller?.cancel();
    _poller = Timer.periodic(_pollInterval, (timer) {
      if (!mounted || _pollsRemaining <= 0) {
        timer.cancel();
        return;
      }
      _pollsRemaining -= 1;
      ref
          .read(documentListControllerProvider.notifier)
          .loadDocuments(isRefresh: true);
    });
  }

  /// Watches the list for the moment ingestion finishes and tells the user,
  /// pointing them at the review queue where the extracted values land.
  void _syncWatchState(List<DocumentItem> documents) {
    final processing = documents.any((doc) => doc.isProcessing);

    if (processing && _poller == null) {
      _startWatching();
    } else if (!processing) {
      _poller?.cancel();
      _poller = null;
      if (_wasProcessing && mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
                'Ayrıştırma tamamlandı. Çıkarılan veriler İnceleme sekmesinde.'),
          ),
        );
      }
    }
    _wasProcessing = processing;
  }

  void _openUploadModal() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => const UploadBottomSheet(),
    ).whenComplete(() {
      // Refresh so a freshly finalized document appears with its real
      // ingestion state, then keep watching until parsing finishes.
      if (!mounted) return;
      ref.read(documentListControllerProvider.notifier).loadDocuments();
      _startWatching();
    });
  }

  @override
  Widget build(BuildContext context) {
    final uiState = ref.watch(documentListControllerProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Belge Yönetimi'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () {
              ref.read(documentListControllerProvider.notifier).loadDocuments();
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // Filter Row
          Padding(
            padding: const EdgeInsets.all(SemanticTokens.spacingSm),
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  FilterChip(
                      label: const Text('Format: Tümü'),
                      selected: false,
                      onSelected: (_) {}),
                  const SizedBox(width: 8),
                  FilterChip(
                      label: const Text('Sınıflandırma: Tümü'),
                      selected: false,
                      onSelected: (_) {}),
                  const SizedBox(width: 8),
                  FilterChip(
                      label: const Text('Durum: Tümü'),
                      selected: false,
                      onSelected: (_) {}),
                ],
              ),
            ),
          ),
          Expanded(
            child: _buildContent(uiState),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openUploadModal,
        icon: const Icon(Icons.upload_file),
        label: const Text('Belge Yükle'),
      ),
    );
  }

  Widget _buildContent(UiState<dynamic> uiState) {
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
                      'Belgeler yüklenirken bir hata oluştu.',
                  textAlign: TextAlign.center),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => ref
                    .read(documentListControllerProvider.notifier)
                    .loadDocuments(),
                child: const Text('Yeniden Dene'),
              ),
            ],
          ),
        ),
      );
    }

    final items = (uiState.data ?? const <DocumentItem>[]).cast<DocumentItem>();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _syncWatchState(items);
    });
    if (items.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.folder_open, size: 64, color: Colors.grey),
            SizedBox(height: 16),
            Text('Henüz yüklü belge bulunmuyor.',
                style: TextStyle(fontSize: 16, color: Colors.grey)),
          ],
        ),
      );
    }

    return ListView.builder(
      itemCount: items.length,
      itemBuilder: (context, index) {
        final doc = items[index];
        return Card(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
          child: ListTile(
            leading: Icon(
              doc.displayName.endsWith('.pdf')
                  ? Icons.picture_as_pdf
                  : Icons.table_chart,
              color: Theme.of(context).colorScheme.primary,
            ),
            title: Text(doc.displayName,
                style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: Text(_statusDescription(doc)),
            trailing: _StatusChip(status: doc.ingestionStatus),
          ),
        );
      },
    );
  }
}

/// Human wording for where a document currently is in ingestion.
String _statusDescription(DocumentItem doc) {
  switch (doc.ingestionStatus) {
    case '':
    case 'QUEUED':
    case 'PENDING':
    case 'CLAIMED':
      return 'Sırada bekliyor';
    case 'PARSING':
    case 'EXTRACTING':
      return 'İşleniyor…';
    case 'COMPLETED':
      return 'Ayrıştırma tamamlandı';
    case 'COMPLETED_WITH_WARNINGS':
      return 'Tamamlandı (uyarılarla)';
    case 'AWAITING_REVIEW':
      return 'İnceleme gerekiyor';
    case 'REJECTED':
      return 'Reddedildi';
    case 'FAILED':
      return 'Ayrıştırma başarısız';
    default:
      return doc.ingestionStatus;
  }
}

class _StatusChip extends StatelessWidget {
  final String status;

  const _StatusChip({required this.status});

  @override
  Widget build(BuildContext context) {
    final processing = status.isEmpty ||
        const ['QUEUED', 'PENDING', 'CLAIMED', 'PARSING', 'EXTRACTING']
            .contains(status);
    if (processing) {
      return const SizedBox(
        width: 18,
        height: 18,
        child: CircularProgressIndicator(strokeWidth: 2),
      );
    }
    final failed = status == 'FAILED' || status == 'REJECTED';
    final needsReview = status == 'AWAITING_REVIEW';
    return Icon(
      failed
          ? Icons.error_outline
          : needsReview
              ? Icons.rate_review_outlined
              : Icons.check_circle,
      color: failed
          ? Theme.of(context).colorScheme.error
          : needsReview
              ? Colors.orange
              : SemanticTokens.verifiedGreenLight,
    );
  }
}
