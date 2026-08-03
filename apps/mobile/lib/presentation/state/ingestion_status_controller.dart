import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/models/wire_models.dart';
import '../../data/repositories/ingestion_repository.dart';
import 'async_value_state.dart';

class IngestionStatusPollingController
    extends StateNotifier<UiState<IngestionJob>> {
  final IngestionRepository _repository;
  StreamSubscription<IngestionJob>? _subscription;
  int _currentToken = 0;
  bool _isDisposed = false;

  IngestionStatusPollingController(this._repository) : super(UiState.initial());

  @override
  void dispose() {
    _isDisposed = true;
    _subscription?.cancel();
    super.dispose();
  }

  void startPolling({required String jobId}) {
    _subscription?.cancel();
    final token = ++_currentToken;

    state = UiState.loading(requestToken: token);

    _subscription = _repository.pollIngestionJob(jobId: jobId).listen(
      (job) {
        if (_isDisposed || token != _currentToken) return;
        state = UiState.success(data: job, requestToken: token);
      },
      onError: (err) {
        if (_isDisposed || token != _currentToken) return;
        state = UiState.failure(
          exception: err,
          requestToken: token,
          currentData: state.data,
        );
      },
    );
  }

  void stopPolling() {
    _subscription?.cancel();
    _subscription = null;
  }
}
