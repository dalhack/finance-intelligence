import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../presentation/providers/providers.dart';
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
  @override
  void initState() {
    super.initState();
    Future.microtask(() {
      ref.read(documentListControllerProvider.notifier).loadDocuments();
    });
  }

  void _openUploadModal() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      builder: (_) => const UploadBottomSheet(),
    );
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

    final items = uiState.data ?? [];
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
            subtitle: Text('ID: ${doc.documentId}'),
            trailing: const Chip(
              label: Text('PROCESSED',
                  style: TextStyle(
                      color: Colors.white,
                      fontSize: 10,
                      fontWeight: FontWeight.bold)),
              backgroundColor: SemanticTokens.verifiedGreenLight,
            ),
          ),
        );
      },
    );
  }
}
