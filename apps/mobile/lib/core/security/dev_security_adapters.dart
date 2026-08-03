import '../config/app_config.dart';
import 'app_attestation_token_provider.dart';
import 'identity_token_provider.dart';

class DevelopmentIdentityTokenProvider implements IdentityTokenProvider {
  final AppConfig config;
  String _syntheticToken = 'dev_synthetic_bearer_token_99182';

  DevelopmentIdentityTokenProvider({required this.config}) {
    if (!config.enableDevAuth || config.environment == 'production') {
      throw StateError(
        'CRITICAL SECURITY ERROR: DevelopmentIdentityTokenProvider is strictly prohibited in production.',
      );
    }
  }

  @override
  bool get isDevelopmentProvider => true;

  @override
  Future<String> getIdToken({bool forceRefresh = false}) async {
    if (!config.enableDevAuth || config.environment == 'production') {
      throw StateError(
        'CRITICAL SECURITY ERROR: DevelopmentIdentityTokenProvider is strictly prohibited in production.',
      );
    }
    if (forceRefresh) {
      _syntheticToken =
          'dev_synthetic_bearer_token_refreshed_${DateTime.now().millisecondsSinceEpoch}';
    }
    return _syntheticToken;
  }
}

class DevelopmentAttestationTokenProvider
    implements AppAttestationTokenProvider {
  final AppConfig config;

  DevelopmentAttestationTokenProvider({required this.config}) {
    if (!config.enableDevAuth || config.environment == 'production') {
      throw StateError(
        'CRITICAL SECURITY ERROR: DevelopmentAttestationTokenProvider is strictly prohibited in production.',
      );
    }
  }

  @override
  bool get isDevelopmentProvider => true;

  @override
  Future<String?> getAttestationToken() async {
    if (!config.enableDevAuth || config.environment == 'production') {
      throw StateError(
        'CRITICAL SECURITY ERROR: DevelopmentAttestationTokenProvider is strictly prohibited in production.',
      );
    }
    return 'dev_synthetic_app_check_token_12345';
  }
}

class ProductionFirebasePlaceholderTokenProvider
    implements IdentityTokenProvider {
  final AppConfig config;

  ProductionFirebasePlaceholderTokenProvider({required this.config});

  @override
  bool get isDevelopmentProvider => false;

  @override
  Future<String> getIdToken({bool forceRefresh = false}) async {
    throw StateError(
      'FIREBASE_REAL_CONNECTION_BLOCKED: External Firebase configuration missing. Production Firebase auth SDK not connected.',
    );
  }
}

class ProductionFirebasePlaceholderAttestationProvider
    implements AppAttestationTokenProvider {
  final AppConfig config;

  ProductionFirebasePlaceholderAttestationProvider({required this.config});

  @override
  bool get isDevelopmentProvider => false;

  @override
  Future<String?> getAttestationToken() async {
    throw StateError(
      'FIREBASE_REAL_CONNECTION_BLOCKED: External Firebase configuration missing. Production Firebase App Check SDK not connected.',
    );
  }
}
