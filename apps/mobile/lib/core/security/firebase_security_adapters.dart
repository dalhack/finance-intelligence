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

/// App Check attestation is not yet wired on the client; the backend runs
/// with ENFORCE_APP_CHECK=false until Firebase App Check integration lands.
/// Returning null omits the attestation header entirely.
class NoopAttestationTokenProvider implements AppAttestationTokenProvider {
  @override
  bool get isDevelopmentProvider => false;

  @override
  Future<String?> getAttestationToken() async => null;
}
