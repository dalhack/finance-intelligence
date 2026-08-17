import 'dart:io';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../app/theme/semantic_tokens.dart';
import '../../../presentation/providers/providers.dart';
import '../../../presentation/state/upload_controller.dart';

class UploadBottomSheet extends ConsumerStatefulWidget {
  const UploadBottomSheet({super.key});

  @override
  ConsumerState<UploadBottomSheet> createState() => _UploadBottomSheetState();
}

class _UploadBottomSheetState extends ConsumerState<UploadBottomSheet> {
  File? _selectedFile;
  String _selectedClassification = 'CONFIDENTIAL';
  String? _errorMessage;
  bool _isNonRetryable = false;

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
          _isNonRetryable = true;
        });
        return;
      }

      setState(() {
        _selectedFile = file;
        _errorMessage = null;
        _isNonRetryable = false;
      });
    }
  }

  void _startUpload() async {
    if (_selectedFile == null) return;

    setState(() {
      _errorMessage = null;
      _isNonRetryable = false;
    });

    try {
      await ref
          .read(uploadLifecycleControllerProvider.notifier)
          .startUploadAndFinalize(_selectedFile!);

      final uploadState = ref.read(uploadLifecycleControllerProvider);
      if (uploadState.status == UploadStatus.failed) {
        final exc = uploadState.exception;
        final isNonRetryable =
            exc != null && exc.code == 'INVALID_FILE_EXTENSION' ||
                exc?.code == 'FILE_SIZE_EXCEEDED' ||
                exc?.code == 'UNSUPPORTED_FILE_TYPE';
        setState(() {
          _errorMessage = exc?.message ?? 'Yükleme sırasında bir hata oluştu.';
          _isNonRetryable = isNonRetryable;
        });
        return;
      }

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
          _errorMessage =
              'Belge yüklenirken bir sorun oluştu. Lütfen tekrar deneyin.';
          _isNonRetryable = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final uploadState = ref.watch(uploadLifecycleControllerProvider);
    final isUploading = uploadState.status == UploadStatus.uploading ||
        uploadState.status == UploadStatus.selecting;
    final progress = uploadState.progressFraction;

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
              padding: const EdgeInsets.all(12.0),
              margin: const EdgeInsets.only(bottom: 12.0),
              decoration: BoxDecoration(
                color: SemanticTokens.errorRedLight.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(8.0),
                border: Border.all(color: SemanticTokens.errorRedLight),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(_errorMessage!,
                      style: const TextStyle(
                          color: SemanticTokens.errorRedLight,
                          fontWeight: FontWeight.w600)),
                  if (_isNonRetryable) ...[
                    const SizedBox(height: 6),
                    const Text(
                      'Bu dosya yüklenemez. Lütfen uygun format ve boyutta başka bir dosya seçin.',
                      style: TextStyle(fontSize: 12, color: Colors.black87),
                    ),
                  ],
                ],
              ),
            ),
          ElevatedButton.icon(
            onPressed: isUploading ? null : _pickFile,
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
            onChanged: isUploading
                ? null
                : (val) {
                    if (val != null)
                      setState(() => _selectedClassification = val);
                  },
          ),
          const SizedBox(height: SemanticTokens.spacingLg),
          if (isUploading) ...[
            LinearProgressIndicator(value: progress > 0 ? progress : null),
            const SizedBox(height: 8),
            Text('Yükleniyor... %${(progress * 100).toInt()}',
                textAlign: TextAlign.center),
            const SizedBox(height: SemanticTokens.spacingMd),
          ],
          Row(
            children: [
              if (_errorMessage != null &&
                  !_isNonRetryable &&
                  !isUploading) ...[
                Expanded(
                  child: OutlinedButton(
                    onPressed: _startUpload,
                    child: const Text('Yeniden Dene'),
                  ),
                ),
                const SizedBox(width: 8),
              ],
              Expanded(
                child: ElevatedButton(
                  onPressed: (_selectedFile != null && !isUploading)
                      ? _startUpload
                      : null,
                  child: const Text('Yüklemeyi Başlat'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
