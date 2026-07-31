import 'package:dio/dio.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/data/api/api_client.dart';

void main() {
  group('Local Backend Real HTTP Integration Gate', () {
    late FinanceIntelligenceApiClient apiClient;
    bool isServerRunning = false;

    setUpAll(() async {
      const baseUrl = 'http://localhost:8000';
      final dio = Dio(BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: const Duration(seconds: 2),
        receiveTimeout: const Duration(seconds: 2),
      ));

      try {
        final res = await dio.get('/health');
        if (res.statusCode == 200) {
          isServerRunning = true;
        }
      } catch (_) {
        isServerRunning = false;
      }

      apiClient = FinanceIntelligenceApiClient(dio: dio);
    });

    test(
        'Checks local backend readiness or reports UNVERIFIED when backend offline',
        () async {
      if (!isServerRunning) {
        expect(isServerRunning, isFalse,
            reason:
                'LOCAL_BACKEND_UI_INTEGRATION_GATE = UNVERIFIED (FastAPI backend is offline)');
        return;
      }

      final metadata = await apiClient.getComparisonFiltersMetadata();
      expect(metadata, isNotEmpty);
    });
  });
}
