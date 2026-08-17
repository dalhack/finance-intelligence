import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/network/org_context.dart';
import '../features/comparisons/presentation/comparison_builder_screen.dart';
import '../features/documents/presentation/document_management_screen.dart';
import '../features/home/presentation/main_dashboard_screen.dart';
import '../features/review/presentation/review_queue_screen.dart';
import '../presentation/providers/providers.dart';

class NavigationShell extends StatefulWidget {
  final int initialTab;

  const NavigationShell({super.key, this.initialTab = 0});

  @override
  State<NavigationShell> createState() => _NavigationShellState();
}

class _NavigationShellState extends State<NavigationShell> {
  late int _currentIndex;

  final List<Widget> _screens = const [
    MainDashboardScreen(),
    DocumentManagementScreen(),
    ReviewQueueScreen(),
    ComparisonBuilderScreen(),
    ProfileScreen(),
  ];

  @override
  void initState() {
    super.initState();
    _currentIndex = widget.initialTab;
  }

  void _onTabSelected(int index) {
    setState(() {
      _currentIndex = index;
    });
  }

  @override
  Widget build(BuildContext context) {
    final mediaQuery = MediaQuery.of(context);
    final isTablet = mediaQuery.size.width >= 600;

    if (isTablet) {
      return Scaffold(
        body: Row(
          children: [
            NavigationRail(
              selectedIndex: _currentIndex,
              onDestinationSelected: _onTabSelected,
              labelType: NavigationRailLabelType.all,
              destinations: const [
                NavigationRailDestination(
                  icon: Icon(Icons.dashboard_outlined),
                  selectedIcon: Icon(Icons.dashboard),
                  label: Text('Ana Sayfa'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.folder_outlined),
                  selectedIcon: Icon(Icons.folder),
                  label: Text('Belgeler'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.fact_check_outlined),
                  selectedIcon: Icon(Icons.fact_check),
                  label: Text('İnceleme'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.analytics_outlined),
                  selectedIcon: Icon(Icons.analytics),
                  label: Text('Analiz'),
                ),
                NavigationRailDestination(
                  icon: Icon(Icons.person_outline),
                  selectedIcon: Icon(Icons.person),
                  label: Text('Profil'),
                ),
              ],
            ),
            const VerticalDivider(thickness: 1, width: 1),
            Expanded(
                child: IndexedStack(index: _currentIndex, children: _screens)),
          ],
        ),
      );
    }

    return Scaffold(
      body: IndexedStack(index: _currentIndex, children: _screens),
      bottomNavigationBar: BottomNavigationBar(
        currentIndex: _currentIndex,
        onTap: _onTabSelected,
        type: BottomNavigationBarType.fixed,
        selectedFontSize: 11,
        unselectedFontSize: 11,
        selectedItemColor: Theme.of(context).colorScheme.primary,
        unselectedItemColor: Colors.grey,
        items: const [
          BottomNavigationBarItem(
            icon: Icon(Icons.dashboard_outlined),
            activeIcon: Icon(Icons.dashboard),
            label: 'Ana Sayfa',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.folder_outlined),
            activeIcon: Icon(Icons.folder),
            label: 'Belgeler',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.fact_check_outlined),
            activeIcon: Icon(Icons.fact_check),
            label: 'İnceleme',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.analytics_outlined),
            activeIcon: Icon(Icons.analytics),
            label: 'Analiz',
          ),
          BottomNavigationBarItem(
            icon: Icon(Icons.person_outline),
            activeIcon: Icon(Icons.person),
            label: 'Profil',
          ),
        ],
      ),
    );
  }
}

/// Account tab: shows the active session, the organization bound to it and the
/// environment the app is talking to, and offers a real Firebase sign-out.
class ProfileScreen extends ConsumerStatefulWidget {
  const ProfileScreen({super.key});

  @override
  ConsumerState<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends ConsumerState<ProfileScreen> {
  bool _signingOut = false;

  /// Firebase is only initialised for environments with real identity; in
  /// development builds and widget tests the plugin is absent, so reading the
  /// current user must never throw.
  String? _currentEmail(bool devSession) {
    if (devSession) return null;
    try {
      return FirebaseAuth.instance.currentUser?.email;
    } catch (_) {
      return null;
    }
  }

  Future<void> _confirmAndSignOut() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Çıkış yap'),
        content: const Text(
            'Oturumunuz kapatılacak ve giriş ekranına döneceksiniz.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Vazgeç'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Çıkış yap'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;

    setState(() => _signingOut = true);
    try {
      await FirebaseAuth.instance.signOut();
      OrgContext.organizationId = null;
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Çıkış yapılamadı. Lütfen tekrar deneyin.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _signingOut = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final config = ref.watch(appConfigProvider);
    final devSession = config.enableDevAuth;
    final email = _currentEmail(devSession);
    final orgId = OrgContext.organizationId;

    return Scaffold(
      appBar: AppBar(title: const Text('Profil')),
      body: ListView(
        children: [
          ListTile(
            leading: const Icon(Icons.account_circle_outlined),
            title: const Text('Hesap'),
            subtitle: Text(
              devSession ? 'Geliştirme oturumu' : (email ?? 'Bilinmiyor'),
            ),
          ),
          ListTile(
            leading: const Icon(Icons.business_outlined),
            title: const Text('Organizasyon'),
            subtitle: Text(orgId == null
                ? 'Atanmadı'
                : '${orgId.substring(0, orgId.length < 8 ? orgId.length : 8)}…'),
          ),
          ListTile(
            leading: const Icon(Icons.cloud_outlined),
            title: const Text('Ortam'),
            subtitle: Text(
              '${config.environment} · ${Uri.parse(config.apiBaseUrl).host}',
            ),
          ),
          const Divider(),
          Padding(
            padding: const EdgeInsets.all(16),
            child: devSession
                ? const Text(
                    'Geliştirme oturumunda çıkış yapılamaz. Gerçek oturum için '
                    'uygulamayı staging veya production ortamıyla çalıştırın.',
                  )
                : FilledButton.icon(
                    onPressed: _signingOut ? null : _confirmAndSignOut,
                    icon: _signingOut
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.logout),
                    label: const Text('Çıkış yap'),
                  ),
          ),
        ],
      ),
    );
  }
}
