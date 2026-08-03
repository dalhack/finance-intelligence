import 'package:flutter/widgets.dart';

class AppLifecycleObserver extends WidgetsBindingObserver {
  final VoidCallback onAppPaused;
  final VoidCallback onAppResumed;

  AppLifecycleObserver({
    required this.onAppPaused,
    required this.onAppResumed,
  });

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.inactive) {
      onAppPaused();
    } else if (state == AppLifecycleState.resumed) {
      onAppResumed();
    }
  }
}
