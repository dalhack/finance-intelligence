abstract class AuthRepository {
  Future<String> getAccessToken();
  Future<void> signInWithDevelopmentSession();
  Future<void> signOut();
  bool get isDevelopmentAuthActive;
}
