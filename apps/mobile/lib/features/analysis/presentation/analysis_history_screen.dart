import 'package:flutter/material.dart';

import '../../../core/models/wire_models.dart';
import '../../../data/api/api_client.dart';

class AnalysisHistoryScreen extends StatefulWidget {
  final FinanceIntelligenceApiClient apiClient;
  final Function(String analysisId)? onSelectAnalysis;

  const AnalysisHistoryScreen({
    super.key,
    required this.apiClient,
    this.onSelectAnalysis,
  });

  @override
  State<AnalysisHistoryScreen> createState() => _AnalysisHistoryScreenState();
}

class _AnalysisHistoryScreenState extends State<AnalysisHistoryScreen> {
  bool _isLoading = true;
  String? _errorMessage;
  List<AnalysisJobModel> _jobs = [];
  int _offset = 0;
  final int _limit = 20;

  @override
  void initState() {
    super.initState();
    _loadHistory();
  }

  Future<void> _loadHistory({bool refresh = false}) async {
    if (refresh) {
      setState(() {
        _offset = 0;
        _isLoading = true;
        _errorMessage = null;
      });
    }

    try {
      final results = await widget.apiClient.listAnalyses(
        limit: _limit,
        offset: _offset,
      );
      setState(() {
        _jobs = refresh ? results : [..._jobs, ...results];
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = 'Analiz geçmişi yüklenemedi: $e';
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Analiz Geçmişi'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => _loadHistory(refresh: true),
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading && _jobs.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }

    if (_errorMessage != null && _jobs.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(_errorMessage!, style: const TextStyle(color: Colors.red)),
            const SizedBox(height: 12),
            ElevatedButton(
              onPressed: () => _loadHistory(refresh: true),
              child: const Text('Tekrar Deneyin'),
            ),
          ],
        ),
      );
    }

    if (_jobs.isEmpty) {
      return const Center(
        child: Text('Henüz kaydedilmiş analiz bulunmuyor.'),
      );
    }

    return RefreshIndicator(
      onRefresh: () => _loadHistory(refresh: true),
      child: ListView.builder(
        itemCount: _jobs.length,
        itemBuilder: (context, index) {
          final job = _jobs[index];
          return ListTile(
            title: Text(
              job.requestPrompt.length > 50
                  ? '${job.requestPrompt.substring(0, 50)}...'
                  : job.requestPrompt,
              style: const TextStyle(fontWeight: FontWeight.w600),
            ),
            subtitle: Text('Tarih: ${job.createdAt}'),
            trailing: _buildStatusBadge(job.status),
            onTap: () {
              if (widget.onSelectAnalysis != null) {
                widget.onSelectAnalysis!(job.id);
              }
            },
          );
        },
      ),
    );
  }

  Widget _buildStatusBadge(String status) {
    Color color = Colors.grey;
    if (status == 'COMPLETED') color = Colors.teal;
    if (status == 'FAILED') color = Colors.red;
    if (status == 'CANCELLED') color = Colors.orange;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color),
      ),
      child: Text(
        status,
        style:
            TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.bold),
      ),
    );
  }
}
