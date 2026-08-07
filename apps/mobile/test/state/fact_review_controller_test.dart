import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/app_exception.dart';
import 'package:finance_intelligence/data/repositories/fact_review_repository.dart';
import 'package:finance_intelligence/presentation/state/async_value_state.dart';
import 'package:finance_intelligence/presentation/state/fact_review_controller.dart';

class MockFactReviewRepository implements FactReviewRepository {
  Completer<List<Map<String, dynamic>>>? queueCompleter;
  List<Map<String, dynamic>> itemsToReturn = [
    {'id': 'cand-1', 'title': 'Fact 1'}
  ];
  Object? errorToThrow;

  @override
  Future<List<Map<String, dynamic>>> getCandidateQueue() async {
    if (queueCompleter != null) {
      return queueCompleter!.future;
    }
    if (errorToThrow != null) {
      throw errorToThrow!;
    }
    return itemsToReturn;
  }

  @override
  Future<void> approveCandidate({
    required String candidateId,
    String? notes,
    String? targetReportingBasis,
  }) async {}

  @override
  Future<void> rejectCandidate({
    required String candidateId,
    required String reason,
  }) async {}

  @override
  Future<void> approveCandidateRevision({
    required String candidateId,
    required String expectedExistingFactId,
    String? notes,
    String? targetReportingBasis,
  }) async {}
}

void main() {
  group('FactReviewController Async Lifecycle & Mount Guard Tests', () {
    late MockFactReviewRepository repository;

    setUp(() {
      repository = MockFactReviewRepository();
    });

    test(
        'T1 — Disposing controller while loadCandidates is pending prevents StateError on completion',
        () async {
      final completer = Completer<List<Map<String, dynamic>>>();
      repository.queueCompleter = completer;

      final controller = FactReviewController(repository);
      expect(controller.state.status, equals(AsyncStatus.initial));

      // Trigger async load
      final loadFuture = controller.loadCandidates();
      expect(controller.state.status, equals(AsyncStatus.loading));

      // Dispose controller while future is pending
      controller.dispose();
      expect(controller.mounted, isFalse);

      // Complete future after disposal
      completer.complete([
        {'id': 'cand-late', 'title': 'Late Fact'}
      ]);
      await loadFuture;

      // Controller remains disposed and no StateError is thrown
      expect(controller.mounted, isFalse);
    });

    test('T2 — Mounted success path updates state with candidate items',
        () async {
      final controller = FactReviewController(repository);

      await controller.loadCandidates();
      expect(controller.state.status, equals(AsyncStatus.success));
      expect(controller.state.data, hasLength(1));
      expect(controller.state.data!.first['id'], equals('cand-1'));
    });

    test(
        'T3 — Mounted error path transitions state to failure with AppException',
        () async {
      repository.errorToThrow = const UnknownException(
        code: 'TEST_ERROR',
        message: 'Repository failure',
        requestId: 'req-test',
      );
      final controller = FactReviewController(repository);

      await controller.loadCandidates();
      expect(controller.state.status, equals(AsyncStatus.terminalFailure));
      expect(controller.state.exception, isNotNull);
      expect(controller.state.exception!.code, equals('TEST_ERROR'));
    });

    test(
        'T4 — Stale completion race does not overwrite state of subsequent load',
        () async {
      final controller = FactReviewController(repository);

      final c1 = Completer<List<Map<String, dynamic>>>();
      repository.queueCompleter = c1;

      final f1 = controller.loadCandidates();
      final token1 = controller.state.requestToken;

      final c2 = Completer<List<Map<String, dynamic>>>();
      repository.queueCompleter = c2;

      final f2 = controller.loadCandidates();
      final token2 = controller.state.requestToken;

      expect(token2, greaterThan(token1));

      // Complete second request first
      c2.complete([
        {'id': 'cand-2', 'title': 'Second Load'}
      ]);
      await f2;

      expect(controller.state.status, equals(AsyncStatus.success));
      expect(controller.state.data!.first['id'], equals('cand-2'));

      // Complete first stale request later
      c1.complete([
        {'id': 'cand-1', 'title': 'Stale First Load'}
      ]);
      await f1;

      // State remains from second request
      expect(controller.state.data!.first['id'], equals('cand-2'));
    });
  });
}
