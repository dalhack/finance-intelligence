import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/models/app_exception.dart';
import '../../core/models/wire_models.dart';
import '../../data/repositories/evidence_repository.dart';
import 'async_value_state.dart';

class EvidenceDetailController extends StateNotifier<UiState<EvidenceDetail>> {
  final EvidenceRepository _repository;
  int _currentToken = 0;
  bool _isDisposed = false;

  EvidenceDetailController(this._repository) : super(UiState.initial());

  @override
  void dispose() {
    _isDisposed = true;
    super.dispose();
  }

  Future<void> fetchEvidenceDetail({required String evidenceId}) async {
    final token = ++_currentToken;
    state = UiState.loading(requestToken: token);

    try {
      final detail =
          await _repository.getEvidenceDetail(evidenceId: evidenceId);
      if (_isDisposed || token != _currentToken) return;

      state = UiState.success(data: detail, requestToken: token);
    } on AppException catch (e) {
      if (_isDisposed || token != _currentToken) return;
      state = UiState.failure(exception: e, requestToken: token);
    } catch (e) {
      if (_isDisposed || token != _currentToken) return;
      state = UiState.failure(
        exception: UnknownException(
          code: 'EVIDENCE_FETCH_FAILED',
          message: e.toString(),
          requestId: 'unknown',
        ),
        requestToken: token,
      );
    }
  }
}
