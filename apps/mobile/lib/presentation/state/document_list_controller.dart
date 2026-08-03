import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../core/models/app_exception.dart';
import '../../core/models/wire_models.dart';
import '../../data/repositories/document_repository.dart';
import 'async_value_state.dart';

class DocumentListController
    extends StateNotifier<UiState<List<DocumentItem>>> {
  final DocumentRepository _repository;
  int _currentToken = 0;
  bool _isDisposed = false;

  DocumentListController(this._repository) : super(UiState.initial());

  UiState<List<DocumentItem>> get currentUiState => state;

  @override
  void dispose() {
    _isDisposed = true;
    super.dispose();
  }

  Future<void> loadDocuments({bool isRefresh = false}) async {
    final token = ++_currentToken;

    if (isRefresh && state.data != null) {
      state = UiState.refreshing(requestToken: token, currentData: state.data!);
    } else {
      state = UiState.loading(requestToken: token);
    }

    try {
      final documents = await _repository.getDocuments();
      if (_isDisposed || token != _currentToken) return;

      if (documents.isEmpty) {
        state = UiState.empty(requestToken: token);
      } else {
        state = UiState.success(data: documents, requestToken: token);
      }
    } on AppException catch (e) {
      if (_isDisposed || token != _currentToken) return;
      state = UiState.failure(
          exception: e, requestToken: token, currentData: state.data);
    } catch (e) {
      if (_isDisposed || token != _currentToken) return;
      state = UiState.failure(
        exception: UnknownException(
          code: 'DOCUMENT_FETCH_FAILED',
          message: e.toString(),
          requestId: 'unknown',
        ),
        requestToken: token,
        currentData: state.data,
      );
    }
  }
}
