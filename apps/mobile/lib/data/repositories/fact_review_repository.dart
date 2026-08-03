import '../api/api_client.dart';

abstract class FactReviewRepository {
  Future<List<Map<String, dynamic>>> getCandidateQueue();
  Future<void> approveCandidate(
      {required String candidateId,
      String? notes,
      String? targetReportingBasis});
  Future<void> rejectCandidate(
      {required String candidateId, required String reason});
  Future<void> approveCandidateRevision({
    required String candidateId,
    required String expectedExistingFactId,
    String? notes,
    String? targetReportingBasis,
  });
}

class RemoteFactReviewRepository implements FactReviewRepository {
  final FinanceIntelligenceApiClient apiClient;

  RemoteFactReviewRepository({required this.apiClient});

  @override
  Future<List<Map<String, dynamic>>> getCandidateQueue() async {
    return apiClient.getCandidateFacts();
  }

  @override
  Future<void> approveCandidate({
    required String candidateId,
    String? notes,
    String? targetReportingBasis,
  }) async {
    await apiClient.approveCandidate(
      candidateId: candidateId,
      notes: notes,
      targetReportingBasis: targetReportingBasis,
    );
  }

  @override
  Future<void> rejectCandidate({
    required String candidateId,
    required String reason,
  }) async {
    await apiClient.rejectCandidate(candidateId: candidateId, reason: reason);
  }

  @override
  Future<void> approveCandidateRevision({
    required String candidateId,
    required String expectedExistingFactId,
    String? notes,
    String? targetReportingBasis,
  }) async {
    await apiClient.approveCandidateRevision(
      candidateId: candidateId,
      expectedExistingFactId: expectedExistingFactId,
      notes: notes,
      targetReportingBasis: targetReportingBasis,
    );
  }
}
