import '../../core/models/wire_models.dart';
import '../api/api_client.dart';

abstract class ComparisonRepository {
  Future<Map<String, dynamic>> executeComparison(
      {required ComparisonRequest request});
  Future<Map<String, dynamic>> getPersistedComparison({
    required String comparisonId,
    int page = 1,
    int pageSize = 20,
  });
  Future<Map<String, dynamic>> getComparisonFiltersMetadata();
}

class RemoteComparisonRepository implements ComparisonRepository {
  final FinanceIntelligenceApiClient apiClient;

  RemoteComparisonRepository({required this.apiClient});

  @override
  Future<Map<String, dynamic>> executeComparison({
    required ComparisonRequest request,
  }) async {
    return await apiClient.executeComparison(request: request);
  }

  @override
  Future<Map<String, dynamic>> getPersistedComparison({
    required String comparisonId,
    int page = 1,
    int pageSize = 20,
  }) async {
    return await apiClient.getPersistedComparison(
      comparisonId: comparisonId,
      page: page,
      pageSize: pageSize,
    );
  }

  @override
  Future<Map<String, dynamic>> getComparisonFiltersMetadata() async {
    return await apiClient.getComparisonFiltersMetadata();
  }
}
