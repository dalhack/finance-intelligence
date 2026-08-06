import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/models/wire_models.dart';
import '../../../data/api/analysis_sse_client.dart';
import '../../../data/api/api_client.dart';

enum AnalysisStatusState {
  idle,
  submitting,
  accepted,
  understanding,
  planning,
  executingTools,
  validatingResults,
  needsClarification,
  clarificationExpired,
  clarificationCancelled,
  completed,
  cancelled,
  failedRetryable,
  failedTerminal,
  reconnecting,
}

class AnalysisState {
  final AnalysisStatusState statusState;
  final String? activeAnalysisId;
  final int lastAppliedSequence;
  final String? lastEventId;
  final String? userPrompt;
  final String? errorMessage;
  final String? warningMessage;
  final Map<String, dynamic>? resultSnapshot;
  final Map<String, dynamic>? clarificationData;
  final bool isSubmitting;

  const AnalysisState({
    this.statusState = AnalysisStatusState.idle,
    this.activeAnalysisId,
    this.lastAppliedSequence = 0,
    this.lastEventId,
    this.userPrompt,
    this.errorMessage,
    this.warningMessage,
    this.resultSnapshot,
    this.clarificationData,
    this.isSubmitting = false,
  });

  AnalysisState copyWith({
    AnalysisStatusState? statusState,
    String? activeAnalysisId,
    int? lastAppliedSequence,
    String? lastEventId,
    String? userPrompt,
    String? errorMessage,
    String? warningMessage,
    Map<String, dynamic>? resultSnapshot,
    Map<String, dynamic>? clarificationData,
    bool? isSubmitting,
  }) {
    return AnalysisState(
      statusState: statusState ?? this.statusState,
      activeAnalysisId: activeAnalysisId ?? this.activeAnalysisId,
      lastAppliedSequence: lastAppliedSequence ?? this.lastAppliedSequence,
      lastEventId: lastEventId ?? this.lastEventId,
      userPrompt: userPrompt ?? this.userPrompt,
      errorMessage: errorMessage ?? this.errorMessage,
      warningMessage: warningMessage ?? this.warningMessage,
      resultSnapshot: resultSnapshot ?? this.resultSnapshot,
      clarificationData: clarificationData ?? this.clarificationData,
      isSubmitting: isSubmitting ?? this.isSubmitting,
    );
  }
}

class AnalysisController extends StateNotifier<AnalysisState> {
  final FinanceIntelligenceApiClient _apiClient;
  final AnalysisSseClient _sseClient;
  final dynamic _resumeStore;
  final String? _sessionBindingFingerprint;
  StreamSubscription<AnalysisDomainEventModel>? _sseSubscription;

  AnalysisController({
    required FinanceIntelligenceApiClient apiClient,
    required AnalysisSseClient sseClient,
    dynamic resumeStore,
    String? sessionBindingFingerprint,
  })  : _apiClient = apiClient,
        _sseClient = sseClient,
        _resumeStore = resumeStore,
        _sessionBindingFingerprint = sessionBindingFingerprint,
        super(const AnalysisState());

  Future<void> restorePendingAnalysis() async {
    if (_resumeStore == null) return;
    try {
      if (_sessionBindingFingerprint != null) {
        await _resumeStore.clearIfSessionMismatch(_sessionBindingFingerprint);
      }
      final record = await _resumeStore.read();
      if (record == null) return;

      final serverJob =
          await _apiClient.getAnalysis(analysisId: record.analysisId);
      if (serverJob.status == 'COMPLETED') {
        state = state.copyWith(
          statusState: AnalysisStatusState.completed,
          activeAnalysisId: record.analysisId,
          lastAppliedSequence: record.lastAppliedSequence,
          lastEventId: record.lastEventId,
        );
        await _resumeStore.markTerminal();
        await _fetchFinalResult(record.analysisId);
        return;
      } else if (serverJob.status == 'NEEDS_CLARIFICATION') {
        state = state.copyWith(
          statusState: AnalysisStatusState.needsClarification,
          activeAnalysisId: record.analysisId,
          lastAppliedSequence: record.lastAppliedSequence,
          lastEventId: record.lastEventId,
        );
        await fetchClarificationDetails(record.analysisId);
        _subscribeToEvents(record.analysisId, lastEventId: record.lastEventId);
        return;
      } else if (serverJob.status == 'FAILED' ||
          serverJob.status == 'CANCELLED' ||
          serverJob.status == 'EXPIRED') {
        await _resumeStore.markTerminal();
        state = state.copyWith(
          statusState: serverJob.status == 'CANCELLED'
              ? AnalysisStatusState.cancelled
              : (serverJob.status == 'EXPIRED'
                  ? AnalysisStatusState.clarificationExpired
                  : AnalysisStatusState.failedTerminal),
          activeAnalysisId: record.analysisId,
        );
        return;
      }

      state = state.copyWith(
        statusState: AnalysisStatusState.understanding,
        activeAnalysisId: record.analysisId,
        lastAppliedSequence: record.lastAppliedSequence,
        lastEventId: record.lastEventId,
      );
      _subscribeToEvents(record.analysisId, lastEventId: record.lastEventId);
    } catch (_) {
      if (_resumeStore != null) await _resumeStore.clear();
    }
  }

  Future<void> submitAnalysis({
    required String prompt,
    required String idempotencyKey,
  }) async {
    if (state.isSubmitting) return;

    state = state.copyWith(
      statusState: AnalysisStatusState.submitting,
      userPrompt: prompt,
      isSubmitting: true,
      errorMessage: null,
    );

    try {
      final job = await _apiClient.createAnalysis(
        prompt: prompt,
        idempotencyKey: idempotencyKey,
      );

      state = state.copyWith(
        statusState: AnalysisStatusState.accepted,
        activeAnalysisId: job.id,
        isSubmitting: false,
      );

      if (_resumeStore != null && _sessionBindingFingerprint != null) {
        await _resumeStore.write(
          dynamicRecord(
            analysisId: job.id,
            lastAppliedSequence: 0,
            lifecycleStatus: 'ACCEPTED',
            sessionBindingFingerprint: _sessionBindingFingerprint,
          ),
        );
      }

      _subscribeToEvents(job.id);
    } catch (e) {
      state = state.copyWith(
        statusState: AnalysisStatusState.failedTerminal,
        errorMessage: e.toString(),
        isSubmitting: false,
      );
    }
  }

  dynamic dynamicRecord({
    required String analysisId,
    required int lastAppliedSequence,
    String? lastEventId,
    required String lifecycleStatus,
    required String sessionBindingFingerprint,
  }) {
    // Dynamic runtime factory for test store polymorphism
    try {
      return (AnalysisResumeRecordRef.create(
        analysisId: analysisId,
        lastAppliedSequence: lastAppliedSequence,
        lastEventId: lastEventId,
        lifecycleStatus: lifecycleStatus,
        createdAt: DateTime.now().toUtc().toIso8601String(),
        lastConnectedAt: DateTime.now().toUtc().toIso8601String(),
        sessionBindingFingerprint: sessionBindingFingerprint,
      ));
    } catch (_) {
      return null;
    }
  }

  void _subscribeToEvents(String analysisId, {String? lastEventId}) {
    _sseSubscription?.cancel();

    _sseSubscription = _sseClient
        .streamEvents(
      analysisId: analysisId,
      lastEventId: lastEventId ?? state.lastEventId,
    )
        .listen(
      (event) {
        _handleDomainEvent(event);
      },
      onError: (err) {
        state = state.copyWith(
          statusState: AnalysisStatusState.reconnecting,
          errorMessage: 'Bağlantı kesildi, yeniden bağlanılıyor...',
        );
      },
    );
  }

  void _handleDomainEvent(AnalysisDomainEventModel event) {
    if (state.statusState == AnalysisStatusState.completed ||
        state.statusState == AnalysisStatusState.failedTerminal ||
        state.statusState == AnalysisStatusState.cancelled ||
        state.statusState == AnalysisStatusState.clarificationExpired) {
      return;
    }

    if (event.analysisId.isNotEmpty &&
        state.activeAnalysisId != null &&
        event.analysisId != state.activeAnalysisId) {
      return;
    }

    if (event.sequence <= state.lastAppliedSequence) {
      return;
    }

    if (event.sequence > state.lastAppliedSequence + 1 &&
        state.lastAppliedSequence > 0) {
      refreshActiveSnapshot();
      return;
    }

    if (_resumeStore != null) {
      _resumeStore.updateSequence(event.sequence, event.sequence.toString());
    }

    AnalysisStatusState newStatus = state.statusState;
    switch (event.eventType) {
      case 'analysis.accepted':
        newStatus = AnalysisStatusState.accepted;
        break;
      case 'analysis.state_changed':
        newStatus = AnalysisStatusState.understanding;
        break;
      case 'analysis.plan_ready':
        newStatus = AnalysisStatusState.planning;
        break;
      case 'analysis.tool_started':
        newStatus = AnalysisStatusState.executingTools;
        break;
      case 'analysis.tool_completed':
        newStatus = AnalysisStatusState.validatingResults;
        break;
      case 'analysis.clarification_required':
        newStatus = AnalysisStatusState.needsClarification;
        fetchClarificationDetails(event.analysisId);
        break;
      case 'analysis.clarification_received':
      case 'analysis.resumed':
        newStatus = AnalysisStatusState.understanding;
        break;
      case 'analysis.clarification_expired':
        newStatus = AnalysisStatusState.clarificationExpired;
        if (_resumeStore != null) _resumeStore.markTerminal();
        break;
      case 'analysis.warning':
        state = state.copyWith(
            warningMessage: event.payload['message']?.toString());
        break;
      case 'analysis.completed':
        newStatus = AnalysisStatusState.completed;
        if (_resumeStore != null) _resumeStore.markTerminal();
        _fetchFinalResult(event.analysisId);
        break;
      case 'analysis.failed':
        newStatus = AnalysisStatusState.failedTerminal;
        if (_resumeStore != null) _resumeStore.markTerminal();
        break;
      case 'analysis.cancelled':
        newStatus = AnalysisStatusState.cancelled;
        if (_resumeStore != null) _resumeStore.markTerminal();
        break;
    }

    state = state.copyWith(
      statusState: newStatus,
      lastAppliedSequence: event.sequence,
      lastEventId: event.sequence.toString(),
    );
  }

  Future<void> fetchClarificationDetails(String analysisId) async {
    try {
      final res =
          await _apiClient.getAnalysisClarification(analysisId: analysisId);
      state = state.copyWith(clarificationData: res);
    } catch (_) {}
  }

  Future<void> submitClarification({
    required String clarificationId,
    required String idempotencyKey,
    required Map<String, dynamic> responsePayload,
  }) async {
    final job = state.activeAnalysisId;
    if (job == null || state.isSubmitting) return;

    state = state.copyWith(isSubmitting: true, errorMessage: null);

    try {
      await _apiClient.respondToClarification(
        analysisId: job,
        requestData: {
          'clarification_id': clarificationId,
          'idempotency_key': idempotencyKey,
          'response_payload': responsePayload,
        },
      );
      state = state.copyWith(
        statusState: AnalysisStatusState.understanding,
        isSubmitting: false,
        clarificationData: null,
      );
    } catch (e) {
      state = state.copyWith(
        isSubmitting: false,
        errorMessage: e.toString(),
      );
    }
  }

  Future<void> cancelClarification({
    required String clarificationId,
    required String idempotencyKey,
  }) async {
    final job = state.activeAnalysisId;
    if (job == null) return;

    try {
      await _apiClient.cancelClarification(
        analysisId: job,
        requestData: {
          'clarification_id': clarificationId,
          'idempotency_key': idempotencyKey,
          'reason_code': 'USER_CANCELLED',
        },
      );
      state = state.copyWith(
        statusState: AnalysisStatusState.cancelled,
        clarificationData: null,
      );
      if (_resumeStore != null) await _resumeStore.markTerminal();
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> refreshActiveSnapshot() async {
    final job = state.activeAnalysisId;
    if (job == null) return;
    try {
      final updatedJob = await _apiClient.getAnalysis(analysisId: job);
      if (updatedJob.status == 'COMPLETED') {
        state = state.copyWith(statusState: AnalysisStatusState.completed);
        if (_resumeStore != null) await _resumeStore.markTerminal();
        await _fetchFinalResult(job);
      }
    } catch (_) {}
  }

  Future<void> _fetchFinalResult(String analysisId) async {
    try {
      final res = await _apiClient.getCompletedResult(analysisId: analysisId);
      state = state.copyWith(resultSnapshot: res);
    } catch (e) {
      state = state.copyWith(
        statusState: AnalysisStatusState.failedTerminal,
        errorMessage: 'Sonuç yüklenemedi: $e',
      );
    }
  }

  Future<void> cancelCurrentAnalysis() async {
    final job = state.activeAnalysisId;
    if (job == null) return;
    state = state.copyWith(statusState: AnalysisStatusState.cancelled);
    if (_resumeStore != null) await _resumeStore.markTerminal();
    try {
      await _apiClient.cancelAnalysis(analysisId: job);
    } catch (_) {}
  }

  @override
  void dispose() {
    _sseSubscription?.cancel();
    super.dispose();
  }
}

class AnalysisResumeRecordRef {
  static dynamic create({
    required String analysisId,
    required int lastAppliedSequence,
    String? lastEventId,
    required String lifecycleStatus,
    required String createdAt,
    required String lastConnectedAt,
    required String sessionBindingFingerprint,
  }) {
    // Helper to dynamically import or construct store records
    return {
      'resumeSchemaVersion': 1,
      'analysisId': analysisId,
      'lastAppliedSequence': lastAppliedSequence,
      'lastEventId': lastEventId,
      'lifecycleStatus': lifecycleStatus,
      'createdAt': createdAt,
      'lastConnectedAt': lastConnectedAt,
      'contractVersion': '3.0.0',
      'sessionBindingFingerprint': sessionBindingFingerprint,
    };
  }
}
