abstract class IdentityTokenProvider {
  Future<String> getIdToken({bool forceRefresh = false});
  bool get isDevelopmentProvider;
}
