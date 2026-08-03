import '../../core/models/wire_models.dart';
import '../api/api_client.dart';

abstract class EvidenceRepository {
  Future<EvidenceDetail> getEvidenceDetail({required String evidenceId});
}

class RemoteEvidenceRepository implements EvidenceRepository {
  final FinanceIntelligenceApiClient apiClient;

  RemoteEvidenceRepository({required this.apiClient});

  @override
  Future<EvidenceDetail> getEvidenceDetail({required String evidenceId}) async {
    return await apiClient.getEvidenceDetail(evidenceId: evidenceId);
  }
}
