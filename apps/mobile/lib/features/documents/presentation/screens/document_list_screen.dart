import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../../presentation/providers/providers.dart';
import '../../data/models/document_model.dart';

class DocumentListScreen extends ConsumerStatefulWidget {
  const DocumentListScreen({super.key});

  @override
  ConsumerState<DocumentListScreen> createState() => _DocumentListScreenState();
}

class _DocumentListScreenState extends ConsumerState<DocumentListScreen> {
  final List<DocumentModel> _documents = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _fetchDocuments();
    });
  }

  Future<void> _fetchDocuments() async {
    setState(() {
      _isLoading = true;
    });

    try {
      await ref.read(documentListControllerProvider.notifier).loadDocuments();
    } catch (_) {}

    if (mounted) {
      setState(() {
        _isLoading = false;
      });
    }
  }

  Color _getStatusColor(String? status) {
    switch (status) {
      case 'COMPLETED':
      case 'EXTRACTED':
        return Colors.green;
      case 'COMPLETED_WITH_WARNINGS':
        return Colors.orange;
      case 'AWAITING_REVIEW':
        return Colors.purple;
      case 'PARSING':
      case 'VALIDATING':
      case 'QUEUED':
        return Colors.blue;
      case 'FAILED':
      case 'REJECTED':
        return Colors.red;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Document Management'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _fetchDocuments,
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _documents.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.folder_open,
                          size: 64, color: Colors.grey),
                      const SizedBox(height: 16),
                      const Text(
                        'No tenant documents found',
                        style: TextStyle(fontSize: 16, color: Colors.grey),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton.icon(
                        icon: const Icon(Icons.upload_file),
                        label: const Text('Upload Financial Document'),
                        onPressed: () {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Document Upload selection dialog opened.',
                              ),
                            ),
                          );
                        },
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: _documents.length,
                  itemBuilder: (context, index) {
                    final doc = _documents[index];
                    return Card(
                      margin: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 8,
                      ),
                      child: ListTile(
                        leading: Icon(
                          doc.displayName.endsWith('.pdf')
                              ? Icons.picture_as_pdf
                              : doc.displayName.endsWith('.xlsx')
                                  ? Icons.table_chart
                                  : Icons.insert_drive_file,
                          color: Theme.of(context).primaryColor,
                        ),
                        title: Text(
                          doc.displayName,
                          style: const TextStyle(fontWeight: FontWeight.bold),
                        ),
                        subtitle: Text(
                          'Type: ${doc.documentType} • Classification: ${doc.classification}',
                        ),
                        trailing: Chip(
                          label: Text(
                            doc.ingestionStatus ?? 'PENDING',
                            style: const TextStyle(
                              color: Colors.white,
                              fontSize: 11,
                            ),
                          ),
                          backgroundColor: _getStatusColor(doc.ingestionStatus),
                        ),
                      ),
                    );
                  },
                ),
    );
  }
}
