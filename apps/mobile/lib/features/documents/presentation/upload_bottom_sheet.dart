import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../presentation/providers/providers.dart';

class UploadBottomSheet extends ConsumerStatefulWidget {
  const UploadBottomSheet({super.key});

  @override
  ConsumerState<UploadBottomSheet> createState() => _UploadBottomSheetState();
}

class _UploadBottomSheetState extends ConsumerState<UploadBottomSheet> {
  File? _selectedFile;
  String _selectedClassification = 'CONFIDENTIAL';
  bool _isUploading = false;
  double _uploadProgress = 0.0;
  String? _errorMessage;

  static const List<String> classifications = [
    'PUBLIC',
    'INTERNAL',
    'CONFIDENTIAL',
    'STRICTLY_CONFIDENTIAL',
    'PERSONAL_DATA',
  ];

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'xlsx', 'csv'],
    );

    if (result != null && result.files.single.path != null) {
      final file = File(result.files.single.path!);
      final len = await file.length();

      if (len > 50 * 1024 * 1024) {
        setState(() {
          _errorMessage = 'Dosya boyutu 50MB sınırını aşamaz.';
        });
        return;
      }

      setState(() {
        _selectedFile = file;
        _errorMessage = null;
      });
    }
  }

  void _startUpload() async {
    if (_selectedFile == null) return;

    setState(() {
      _isUploading = true;
      _uploadProgress = 0.1;
      _errorMessage = null;
    });

    try {
      await ref
          .read(uploadLifecycleControllerProvider.notifier)
          .startUploadAndFinalize(_selectedFile!);

      if (mounted) {
        Navigator.pop(context);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
                'Belge başarıyla yüklendi ve ayrıştırma kuyruğuna alındı.'),
            backgroundColor: SemanticTokens.verifiedGreenLight,
          ),
        );
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _isUploading = false;
          _errorMessage = e.toString();
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
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
              const Text('Belge Yükle',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              IconButton(
                  icon: const Icon(Icons.close),
                  onPressed: () => Navigator.pop(context)),
            ],
          ),
          const Divider(),
          if (_errorMessage != null)
            Container(
              padding: const EdgeInsets.all(8.0),
              margin: const EdgeInsets.only(bottom: 8.0),
              color: SemanticTokens.errorRedLight.withValues(alpha: 0.1),
              child: Text(_errorMessage!,
                  style: const TextStyle(color: SemanticTokens.errorRedLight)),
            ),
          ElevatedButton.icon(
            onPressed: _isUploading ? null : _pickFile,
            icon: const Icon(Icons.folder_open),
            label: Text(_selectedFile == null
                ? 'PDF / XLSX / CSV Seç'
                : _selectedFile!.path.split('/').last),
          ),
          const SizedBox(height: SemanticTokens.spacingMd),
          DropdownButtonFormField<String>(
            initialValue: _selectedClassification,
            decoration:
                const InputDecoration(labelText: 'Güvenlik Sınıflandırması'),
            items: classifications
                .map((c) => DropdownMenuItem(value: c, child: Text(c)))
                .toList(),
            onChanged: (val) {
              if (val != null) setState(() => _selectedClassification = val);
            },
          ),
          const SizedBox(height: SemanticTokens.spacingLg),
          if (_isUploading) ...[
            LinearProgressIndicator(value: _uploadProgress),
            const SizedBox(height: 8),
            Text('Yükleniyor... %${(_uploadProgress * 100).toInt()}',
                textAlign: TextAlign.center),
            const SizedBox(height: SemanticTokens.spacingMd),
          ],
          ElevatedButton(
            onPressed:
                (_selectedFile != null && !_isUploading) ? _startUpload : null,
            child: const Text('Yüklemeyi Başlat & Sonlandır'),
          ),
        ],
      ),
    );
  }
}
