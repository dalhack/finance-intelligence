import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/models/app_exception.dart';
import '../../data/repositories/fact_review_repository.dart';
import 'async_value_state.dart';

class FactReviewController
    extends StateNotifier<UiState<List<Map<String, dynamic>>>> {
  final FactReviewRepository _repository;
  int _generationToken = 0;

  FactReviewController(this._repository) : super(UiState.initial());

  Future<void> loadCandidates() async {
    final currentToken = ++_generationToken;
    state =
        UiState.loading(requestToken: currentToken, currentData: state.data);

    try {
      final items = await _repository.getCandidateQueue();
      if (!mounted || _generationToken != currentToken) return;

      if (items.isEmpty) {
        state = UiState.empty(requestToken: currentToken);
      } else {
        state = UiState.success(data: items, requestToken: currentToken);
      }
    } catch (e) {
      if (!mounted || _generationToken != currentToken) return;
      state = UiState.failure(
        exception: e is AppException
            ? e
            : UnknownException(
                code: 'UNKNOWN', message: e.toString(), requestId: 'req-local'),
        requestToken: currentToken,
      );
    }
  }

  Future<void> approveCandidate(
      {required String candidateId,
      String? notes,
      String? targetReportingBasis}) async {
    final currentToken = ++_generationToken;
    try {
      await _repository.approveCandidate(
          candidateId: candidateId,
          notes: notes,
          targetReportingBasis: targetReportingBasis);
      if (!mounted || _generationToken != currentToken) return;
      await loadCandidates();
    } catch (e) {
      final failure = e is AppException
          ? e
          : UnknownException(
              code: 'UNKNOWN', message: e.toString(), requestId: 'req-local');
      // The queue itself is still valid, so it stays on screen: replacing it
      // with an error page hid every remaining candidate behind one refused
      // decision. Reloading also clears a card the server has already
      // reviewed, which is the usual reason a decision is refused.
      if (mounted && _generationToken == currentToken) {
        await loadCandidates();
      }
      // A review decision that did not reach the server must never read as
      // done. Swallowing this told the reviewer their approval succeeded while
      // nothing had been written.
      throw failure;
    }
  }

  Future<void> rejectCandidate(
      {required String candidateId, required String reason}) async {
    final currentToken = ++_generationToken;
    try {
      await _repository.rejectCandidate(
          candidateId: candidateId, reason: reason);
      if (!mounted || _generationToken != currentToken) return;
      await loadCandidates();
    } catch (e) {
      final failure = e is AppException
          ? e
          : UnknownException(
              code: 'UNKNOWN', message: e.toString(), requestId: 'req-local');
      // The queue itself is still valid, so it stays on screen: replacing it
      // with an error page hid every remaining candidate behind one refused
      // decision. Reloading also clears a card the server has already
      // reviewed, which is the usual reason a decision is refused.
      if (mounted && _generationToken == currentToken) {
        await loadCandidates();
      }
      // A review decision that did not reach the server must never read as
      // done. Swallowing this told the reviewer their approval succeeded while
      // nothing had been written.
      throw failure;
    }
  }

  Future<void> approveCandidateRevision({
    required String candidateId,
    required String expectedExistingFactId,
    String? notes,
    String? targetReportingBasis,
  }) async {
    final currentToken = ++_generationToken;
    try {
      await _repository.approveCandidateRevision(
        candidateId: candidateId,
        expectedExistingFactId: expectedExistingFactId,
        notes: notes,
        targetReportingBasis: targetReportingBasis,
      );
      if (!mounted || _generationToken != currentToken) return;
      await loadCandidates();
    } catch (e) {
      final failure = e is AppException
          ? e
          : UnknownException(
              code: 'UNKNOWN', message: e.toString(), requestId: 'req-local');
      // The queue itself is still valid, so it stays on screen: replacing it
      // with an error page hid every remaining candidate behind one refused
      // decision. Reloading also clears a card the server has already
      // reviewed, which is the usual reason a decision is refused.
      if (mounted && _generationToken == currentToken) {
        await loadCandidates();
      }
      // A review decision that did not reach the server must never read as
      // done. Swallowing this told the reviewer their approval succeeded while
      // nothing had been written.
      throw failure;
    }
  }
}
