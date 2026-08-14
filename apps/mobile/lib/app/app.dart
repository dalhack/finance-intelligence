import 'package:dio/dio.dart';
import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/config/app_config.dart';
import '../core/network/org_context.dart';
import '../core/security/firebase_security_adapters.dart';
import '../features/authentication/views/sign_in_screen.dart';
import 'router.dart';
import 'theme/app_theme.dart';

class FinanceIntelligenceApp extends StatelessWidget {
  const FinanceIntelligenceApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ProviderScope(
      child: MaterialApp(
        title: 'Finance Intelligence',
        theme: AppTheme.lightTheme,
        darkTheme: AppTheme.darkTheme,
        themeMode: ThemeMode.system,
        debugShowCheckedModeBanner: false,
        onGenerateRoute: AppRouter.generateRoute,
        home: kReleaseMode ? const _AuthGate() : null,
        initialRoute: kReleaseMode ? null : '/',
      ),
    );
  }
}

/// Release builds require a signed-in Firebase user and a provisioned
/// organization before the app shell is shown; development builds keep the
/// synthetic dev-session flow.
class _AuthGate extends StatelessWidget {
  const _AuthGate();

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<User?>(
      stream: FirebaseAuth.instance.authStateChanges(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const _SplashScaffold();
        }
        if (snapshot.data == null) {
          OrgContext.organizationId = null;
          return const SignInScreen();
        }
        return _OrganizationGate(user: snapshot.data!);
      },
    );
  }
}

/// Ensures the signed-in user has an organization (idempotent bootstrap),
/// stores it in OrgContext, then shows the app shell.
class _OrganizationGate extends StatefulWidget {
  final User user;
  const _OrganizationGate({required this.user});

  @override
  State<_OrganizationGate> createState() => _OrganizationGateState();
}

class _OrganizationGateState extends State<_OrganizationGate> {
  late Future<void> _bootstrapFuture;

  @override
  void initState() {
    super.initState();
    _bootstrapFuture = _ensureOrganization();
  }

  Future<void> _ensureOrganization() async {
    if (OrgContext.organizationId != null) return;
    final config = AppConfig.production;
    final token =
        await FirebaseIdentityTokenProvider().getIdToken(forceRefresh: false);
    final dio = Dio(BaseOptions(
      baseUrl: config.apiBaseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 20),
    ));
    final res = await dio.post(
      '/organizations/bootstrap',
      options: Options(headers: {'Authorization': 'Bearer $token'}),
    );
    OrgContext.organizationId = res.data['organization_id']?.toString();
    if (OrgContext.organizationId == null) {
      throw StateError('Bootstrap response missing organization_id');
    }
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<void>(
      future: _bootstrapFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const _SplashScaffold();
        }
        if (snapshot.hasError) {
          return Scaffold(
            body: Center(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    const Icon(Icons.cloud_off, size: 48),
                    const SizedBox(height: 16),
                    const Text('Hesap hazırlanamadı. Bağlantınızı kontrol edin.'),
                    const SizedBox(height: 16),
                    FilledButton(
                      onPressed: () => setState(() {
                        _bootstrapFuture = _ensureOrganization();
                      }),
                      child: const Text('Yeniden Dene'),
                    ),
                    TextButton(
                      onPressed: () => FirebaseAuth.instance.signOut(),
                      child: const Text('Çıkış Yap'),
                    ),
                  ],
                ),
              ),
            ),
          );
        }
        return AppRouter.buildShell();
      },
    );
  }
}

class _SplashScaffold extends StatelessWidget {
  const _SplashScaffold();

  @override
  Widget build(BuildContext context) {
    return const Scaffold(
      body: Center(child: CircularProgressIndicator()),
    );
  }
}
