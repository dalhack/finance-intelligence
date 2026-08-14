import 'package:flutter/material.dart';
import 'navigation_shell.dart';

class AppRouter {
  static Widget buildShell() => const NavigationShell();

  static Route<dynamic> generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case '/':
        return MaterialPageRoute(builder: (_) => const NavigationShell());
      case '/documents':
        return MaterialPageRoute(
            builder: (_) => const NavigationShell(initialTab: 1));
      case '/review':
        return MaterialPageRoute(
            builder: (_) => const NavigationShell(initialTab: 2));
      case '/comparisons':
        return MaterialPageRoute(
            builder: (_) => const NavigationShell(initialTab: 3));
      default:
        return MaterialPageRoute(
          builder: (_) => const NavigationShell(),
        );
    }
  }
}

final appRouter = RouterConfig<Object>(routerDelegate: _SimpleRouterDelegate());

class _SimpleRouterDelegate extends RouterDelegate<Object>
    with ChangeNotifier, PopNavigatorRouterDelegateMixin<Object> {
  @override
  final GlobalKey<NavigatorState> navigatorKey = GlobalKey<NavigatorState>();

  @override
  Widget build(BuildContext context) {
    return Navigator(
      key: navigatorKey,
      pages: const [MaterialPage(child: NavigationShell())],
      onDidRemovePage: (page) {},
    );
  }

  @override
  Future<void> setNewRoutePath(Object configuration) async {}
}
