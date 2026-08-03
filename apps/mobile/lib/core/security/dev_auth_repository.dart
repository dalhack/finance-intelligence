import '../config/app_config.dart';
import 'auth_repository.dart';

class DevelopmentAuthRepository implements AuthRepository {
  final AppConfig config;
  String? _token;

  DevelopmentAuthRepository({required this.config}) {
    if (!config.enableDevAuth || config.environment == 'production') {
      throw StateError(
        'CRITICAL SECURITY ERROR: DevelopmentAuthRepository is strictly prohibited in production builds.',
      );
    }
  }

  @override
  bool get isDevelopmentAuthActive => config.enableDevAuth;

  @override
  Future<String> getAccessToken() async {
    if (_token == null) {
      await signInWithDevelopmentSession();
    }
    return _token!;
  }

  @override
  Future<void> signInWithDevelopmentSession() async {
    if (!config.enableDevAuth || config.environment == 'production') {
      throw StateError(
        'CRITICAL SECURITY ERROR: DevelopmentAuthRepository is strictly prohibited in production builds.',
      );
    }
    _token = 'dev_synthetic_bearer_token_99182';
  }

  @override
  Future<void> signOut() async {
    _token = null;
  }
}
