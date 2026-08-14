import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter/material.dart';
import 'app/app.dart';
import 'core/network/org_context.dart';
import 'firebase_options.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // Development builds use the synthetic dev-session flow against localhost;
  // Firebase is only required for the production identity provider.
  if (kReleaseMode) {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
  } else {
    // Backend dev adapter accepts any org UUID; a fixed synthetic id keeps
    // the X-Organization-ID header present in development.
    OrgContext.organizationId = '00000000-0000-0000-0000-000000000001';
  }
  runApp(const FinanceIntelligenceApp());
}
