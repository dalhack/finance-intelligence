import 'dart:async';
import 'dart:math';
import '../../core/models/app_exception.dart';
import '../../core/models/wire_models.dart';
import '../api/api_client.dart';

abstract class IngestionRepository {
  Future<IngestionJob> getJobStatus({required String jobId});
  Stream<IngestionJob> pollIngestionJob({
    required String jobId,
    Duration initialInterval = const Duration(seconds: 1),
    Duration maxInterval = const Duration(seconds: 10),
  });
}

class RemoteIngestionRepository implements IngestionRepository {
  final FinanceIntelligenceApiClient apiClient;
  final Map<String, StreamController<IngestionJob>> _activePollers = {};

  RemoteIngestionRepository({required this.apiClient});

  @override
  Future<IngestionJob> getJobStatus({required String jobId}) async {
    return await apiClient.getIngestionJobStatus(jobId: jobId);
  }

  @override
  Stream<IngestionJob> pollIngestionJob({
    required String jobId,
    Duration initialInterval = const Duration(seconds: 1),
    Duration maxInterval = const Duration(seconds: 10),
  }) {
    // Singleton per job
    _activePollers[jobId]?.close();

    final controller = StreamController<IngestionJob>.broadcast();
    _activePollers[jobId] = controller;

    Timer? timer;
    int attempt = 0;

    void scheduleNextPoll() {
      if (controller.isClosed) return;

      attempt++;
      final factor = pow(1.5, attempt).toDouble();
      final jitterMs = Random().nextInt(300);
      final rawMs =
          (initialInterval.inMilliseconds * factor).toInt() + jitterMs;
      final delayMs = min(rawMs, maxInterval.inMilliseconds);

      timer = Timer(Duration(milliseconds: delayMs), () async {
        if (controller.isClosed) return;
        try {
          final job = await apiClient.getIngestionJobStatus(jobId: jobId);
          if (!controller.isClosed) {
            controller.add(job);
            if (job.isTerminal) {
              await controller.close();
              _activePollers.remove(jobId);
              return;
            }
          }
          scheduleNextPoll();
        } on AuthenticationException catch (e) {
          if (!controller.isClosed) controller.addError(e);
          await controller.close();
          _activePollers.remove(jobId);
        } on AuthorizationException catch (e) {
          if (!controller.isClosed) controller.addError(e);
          await controller.close();
          _activePollers.remove(jobId);
        } catch (e) {
          if (!controller.isClosed) controller.addError(e);
          scheduleNextPoll();
        }
      });
    }

    controller.onCancel = () {
      timer?.cancel();
      _activePollers.remove(jobId);
    };

    // Immediate first fetch
    Future.microtask(() async {
      try {
        final job = await apiClient.getIngestionJobStatus(jobId: jobId);
        if (!controller.isClosed) {
          controller.add(job);
          if (job.isTerminal) {
            await controller.close();
            _activePollers.remove(jobId);
            return;
          }
        }
        scheduleNextPoll();
      } catch (e) {
        if (!controller.isClosed) controller.addError(e);
        scheduleNextPoll();
      }
    });

    return controller.stream;
  }
}
