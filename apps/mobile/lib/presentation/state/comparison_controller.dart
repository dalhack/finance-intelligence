import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/models/app_exception.dart';
import '../../core/models/wire_models.dart';
import '../../data/repositories/comparison_repository.dart';
import 'async_value_state.dart';

class ComparisonController extends StateNotifier<UiState<ResultDataset>> {
  final ComparisonRepository _repository;
  int _currentToken = 0;
  bool _isDisposed = false;

  ComparisonController(this._repository) : super(UiState.initial());

  @override
  void dispose() {
    _isDisposed = true;
    super.dispose();
  }

  Future<void> executeComparison(ComparisonRequest request) async {
    if (state.isLoading) return; // Prevent duplicate submit

    final token = ++_currentToken;
    state = UiState.loading(requestToken: token, currentData: state.data);

    try {
      final resJson = await _repository.executeComparison(request: request);
      if (_isDisposed || token != _currentToken) return;

      final dsJson = resJson['result_dataset'] as Map<String, dynamic>;
      final dataset = ResultDataset.fromJson(dsJson);

      state = UiState.success(data: dataset, requestToken: token);
    } on AppException catch (e) {
      if (_isDisposed || token != _currentToken) return;
      state = UiState.failure(
          exception: e, requestToken: token, currentData: state.data);
    } catch (e) {
      if (_isDisposed || token != _currentToken) return;
      state = UiState.failure(
        exception: UnknownException(
          code: 'COMPARISON_EXECUTION_FAILED',
          message: e.toString(),
          requestId: 'unknown',
        ),
        requestToken: token,
        currentData: state.data,
      );
    }
  }
}
