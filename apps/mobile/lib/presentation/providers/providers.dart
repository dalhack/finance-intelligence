import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/config/app_config.dart';
import '../../core/models/wire_models.dart';
import '../../core/network/dio_client_factory.dart';
import '../../core/security/dev_security_adapters.dart';
import '../../core/security/firebase_security_adapters.dart';
import '../../data/api/api_client.dart';
import '../../data/repositories/comparison_repository.dart';
import '../../data/repositories/document_repository.dart';
import '../../data/repositories/evidence_repository.dart';
import '../../data/repositories/fact_review_repository.dart';
import '../../data/repositories/ingestion_repository.dart';
import '../../data/storage/analysis_resume_store.dart';
import '../../data/api/analysis_sse_client.dart';
import '../../features/analysis/controllers/analysis_controller.dart';
import '../state/async_value_state.dart';
import '../state/comparison_controller.dart';
import '../state/document_list_controller.dart';
import '../state/evidence_detail_controller.dart';
import '../state/fact_review_controller.dart';
import '../state/ingestion_status_controller.dart';
import '../state/upload_controller.dart';

final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError(
      'sharedPreferencesProvider must be overridden in ProviderScope');
});

final analysisResumeStoreProvider = Provider<AnalysisResumeStore>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return SharedPreferencesAnalysisResumeStore(prefs);
});

/// Active configuration, selected by the `APP_ENV` dart-define and validated
/// fail-closed at read time (see [AppConfig.resolve]).
final appConfigProvider = Provider<AppConfig>((ref) {
  final config = AppConfig.resolve();
  config.validateConfig();
  return config;
});

final identityTokenProvider = Provider((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.enableDevAuth) {
    return DevelopmentIdentityTokenProvider(config: config);
  }
  return FirebaseIdentityTokenProvider();
});

final appAttestationTokenProvider = Provider((ref) {
  final config = ref.watch(appConfigProvider);
  if (config.enableDevAuth) {
    return DevelopmentAttestationTokenProvider(config: config);
  }
  return FirebaseAppAttestTokenProvider();
});

final dioClientProvider = Provider((ref) {
  final config = ref.watch(appConfigProvider);
  final identityProv = ref.watch(identityTokenProvider);
  final attestationProv = ref.watch(appAttestationTokenProvider);
  return DioClientFactory.createDio(
    config: config,
    identityTokenProvider: identityProv,
    appAttestationTokenProvider: attestationProv,
  );
});

final apiClientProvider = Provider<FinanceIntelligenceApiClient>((ref) {
  final dio = ref.watch(dioClientProvider);
  return FinanceIntelligenceApiClient(dio: dio);
});

final documentRepositoryProvider = Provider<DocumentRepository>((ref) {
  final api = ref.watch(apiClientProvider);
  return RemoteDocumentRepository(apiClient: api);
});

final ingestionRepositoryProvider = Provider<IngestionRepository>((ref) {
  final api = ref.watch(apiClientProvider);
  return RemoteIngestionRepository(apiClient: api);
});

final comparisonRepositoryProvider = Provider<ComparisonRepository>((ref) {
  final api = ref.watch(apiClientProvider);
  return RemoteComparisonRepository(apiClient: api);
});

final evidenceRepositoryProvider = Provider<EvidenceRepository>((ref) {
  final api = ref.watch(apiClientProvider);
  return RemoteEvidenceRepository(apiClient: api);
});

final factReviewRepositoryProvider = Provider<FactReviewRepository>((ref) {
  final api = ref.watch(apiClientProvider);
  return RemoteFactReviewRepository(apiClient: api);
});

// Presentation Controllers
final documentListControllerProvider =
    StateNotifierProvider<DocumentListController, UiState<List<DocumentItem>>>(
        (ref) {
  final repo = ref.watch(documentRepositoryProvider);
  return DocumentListController(repo);
});

final uploadLifecycleControllerProvider =
    StateNotifierProvider<UploadLifecycleController, UploadState>((ref) {
  final repo = ref.watch(documentRepositoryProvider);
  return UploadLifecycleController(repo);
});

final ingestionStatusPollingControllerProvider = StateNotifierProvider.family<
    IngestionStatusPollingController,
    UiState<IngestionJob>,
    String>((ref, jobId) {
  final repo = ref.watch(ingestionRepositoryProvider);
  return IngestionStatusPollingController(repo);
});

final comparisonControllerProvider =
    StateNotifierProvider<ComparisonController, UiState<ResultDataset>>((ref) {
  final repo = ref.watch(comparisonRepositoryProvider);
  return ComparisonController(repo);
});

final evidenceDetailControllerProvider =
    StateNotifierProvider<EvidenceDetailController, UiState<EvidenceDetail>>(
        (ref) {
  final repo = ref.watch(evidenceRepositoryProvider);
  return EvidenceDetailController(repo);
});

final factReviewControllerProvider = StateNotifierProvider<FactReviewController,
    UiState<List<Map<String, dynamic>>>>((ref) {
  final repo = ref.watch(factReviewRepositoryProvider);
  return FactReviewController(repo);
});

final analysisSseClientProvider = Provider<AnalysisSseClient>((ref) {
  final dio = ref.watch(dioClientProvider);
  return AnalysisSseClient(dio: dio);
});

final analysisControllerProvider =
    StateNotifierProvider<AnalysisController, AnalysisState>((ref) {
  final apiClient = ref.watch(apiClientProvider);
  final sseClient = ref.watch(analysisSseClientProvider);
  return AnalysisController(apiClient: apiClient, sseClient: sseClient);
});
