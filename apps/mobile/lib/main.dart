import 'package:firebase_core/firebase_core.dart';
import 'package:flutter/material.dart';
import 'app/app.dart';
import 'core/config/app_config.dart';
import 'core/network/org_context.dart';
import 'firebase_options.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // The active environment comes from --dart-define=APP_ENV and is validated
  // fail-closed; it is never inferred from the build mode, so a Debug build on
  // a physical device targets staging over HTTPS with real Firebase identity.
  final config = AppConfig.resolve();
  config.validateConfig();
  if (config.enableDevAuth) {
    // Backend dev adapter accepts any org UUID; a fixed synthetic id keeps
    // the X-Organization-ID header present in development.
    OrgContext.organizationId = '00000000-0000-0000-0000-000000000001';
  } else {
    await Firebase.initializeApp(
      options: DefaultFirebaseOptions.currentPlatform,
    );
  }
  runApp(FinanceIntelligenceApp(config: config));
}
