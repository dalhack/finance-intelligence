abstract class AppAttestationTokenProvider {
  Future<String?> getAttestationToken();
  bool get isDevelopmentProvider;
}
