import 'package:firebase_core/firebase_core.dart' show FirebaseOptions;
import 'package:flutter/foundation.dart'
    show defaultTargetPlatform, TargetPlatform;

/// Firebase configuration for finance-intel-staging-8f2a.
/// Values sourced from the registered Firebase iOS app
/// (1:523958262212:ios:bd7b9a3d73ee327cba6c91). These are public client
/// identifiers, not secrets.
class DefaultFirebaseOptions {
  static FirebaseOptions get currentPlatform {
    switch (defaultTargetPlatform) {
      case TargetPlatform.iOS:
        return ios;
      default:
        throw UnsupportedError(
          'DefaultFirebaseOptions are only configured for iOS in this phase.',
        );
    }
  }

  static const FirebaseOptions ios = FirebaseOptions(
    apiKey: 'AIzaSyCqffEpZ19hpSjzDxTqeiMOZschzlBxB90',
    appId: '1:523958262212:ios:bd7b9a3d73ee327cba6c91',
    messagingSenderId: '523958262212',
    projectId: 'finance-intel-staging-8f2a',
    storageBucket: 'finance-intel-staging-8f2a.firebasestorage.app',
    iosBundleId: 'com.korhanturgut.financeintelligence',
  );
}
