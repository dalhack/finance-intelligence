import '../../core/models/app_exception.dart';

enum AsyncStatus {
  initial,
  loading,
  refreshing,
  success,
  empty,
  partialSuccessWithWarnings,
  validationFailure,
  authFailure,
  permissionFailure,
  networkFailure,
  serverFailure,
  terminalFailure,
}

class UiState<T> {
  final AsyncStatus status;
  final T? data;
  final AppException? exception;
  final String? warningMessage;
  final int requestToken;

  const UiState._({
    required this.status,
    this.data,
    this.exception,
    this.warningMessage,
    required this.requestToken,
  });

  factory UiState.initial() => const UiState._(
        status: AsyncStatus.initial,
        requestToken: 0,
      );

  factory UiState.loading({required int requestToken, T? currentData}) =>
      UiState._(
        status: AsyncStatus.loading,
        data: currentData,
        requestToken: requestToken,
      );

  factory UiState.refreshing(
          {required int requestToken, required T currentData}) =>
      UiState._(
        status: AsyncStatus.refreshing,
        data: currentData,
        requestToken: requestToken,
      );

  factory UiState.success({required T data, required int requestToken}) =>
      UiState._(
        status: AsyncStatus.success,
        data: data,
        requestToken: requestToken,
      );

  factory UiState.empty({required int requestToken}) => UiState._(
        status: AsyncStatus.empty,
        requestToken: requestToken,
      );

  factory UiState.partialSuccessWithWarnings({
    required T data,
    required String warningMessage,
    required int requestToken,
  }) =>
      UiState._(
        status: AsyncStatus.partialSuccessWithWarnings,
        data: data,
        warningMessage: warningMessage,
        requestToken: requestToken,
      );

  factory UiState.failure({
    required AppException exception,
    required int requestToken,
    T? currentData,
  }) {
    AsyncStatus status;
    if (exception is ValidationException) {
      status = AsyncStatus.validationFailure;
    } else if (exception is AuthenticationException) {
      status = AsyncStatus.authFailure;
    } else if (exception is AuthorizationException) {
      status = AsyncStatus.permissionFailure;
    } else if (exception is NetworkException || exception is TimeoutException) {
      status = AsyncStatus.networkFailure;
    } else if (exception is ServerException) {
      status = AsyncStatus.serverFailure;
    } else {
      status = AsyncStatus.terminalFailure;
    }

    return UiState._(
      status: status,
      data: currentData,
      exception: exception,
      requestToken: requestToken,
    );
  }

  bool get isLoading => status == AsyncStatus.loading;
  bool get isSuccess =>
      status == AsyncStatus.success ||
      status == AsyncStatus.partialSuccessWithWarnings;
}
