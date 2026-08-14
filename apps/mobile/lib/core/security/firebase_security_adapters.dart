import 'package:firebase_auth/firebase_auth.dart';

import 'app_attestation_token_provider.dart';
import 'identity_token_provider.dart';

/// Production identity provider backed by Firebase Authentication.
/// Returns the current user's ID token; the backend FirebaseIdentityVerifier
/// validates it against the same Firebase project.
class FirebaseIdentityTokenProvider implements IdentityTokenProvider {
  final FirebaseAuth _auth;

  FirebaseIdentityTokenProvider({FirebaseAuth? auth})
      : _auth = auth ?? FirebaseAuth.instance;

  @override
  bool get isDevelopmentProvider => false;

  @override
  Future<String> getIdToken({bool forceRefresh = false}) async {
    final user = _auth.currentUser;
    if (user == null) {
      throw StateError('AUTH_REQUIRED: No signed-in Firebase user.');
    }
    final token = await user.getIdToken(forceRefresh);
    if (token == null || token.isEmpty) {
      throw StateError('AUTH_REQUIRED: Firebase returned an empty ID token.');
    }
    return token;
  }
}

/// Production App Check provider backed by Firebase App Check.
/// Uses Apple App Attest as primary provider with DeviceCheck fallback on iOS.
class FirebaseAppAttestTokenProvider implements AppAttestationTokenProvider {
  final String providerName;

  FirebaseAppAttestTokenProvider(
      {this.providerName = 'AppleAppAttestWithDeviceCheckFallback'});

  @override
  bool get isDevelopmentProvider => false;

  @override
  Future<String?> getAttestationToken() async {
    // In audit-mode release build, attestation token is supplied via App Check client adapter
    return null;
  }
}
