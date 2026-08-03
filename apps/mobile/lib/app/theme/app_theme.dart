import 'package:flutter/material.dart';
import 'semantic_tokens.dart';

class AppTheme {
  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.light,
      colorScheme: const ColorScheme.light(
        primary: SemanticTokens.primaryNavyLight,
        secondary: SemanticTokens.accentTealLight,
        tertiary: SemanticTokens.primaryBlueLight,
        surface: SemanticTokens.surfaceLight,
        error: SemanticTokens.errorRedLight,
      ),
      scaffoldBackgroundColor: SemanticTokens.backgroundLight,
      cardTheme: CardThemeData(
        color: SemanticTokens.surfaceLight,
        elevation: SemanticTokens.cardElevation,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SemanticTokens.radiusMd),
          side: const BorderSide(color: SemanticTokens.borderLight),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: SemanticTokens.primaryNavyLight,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  static ThemeData get darkTheme {
    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: const ColorScheme.dark(
        primary: SemanticTokens.primaryBlueDark,
        secondary: SemanticTokens.accentTealDark,
        surface: SemanticTokens.surfaceDark,
        error: SemanticTokens.errorRedDark,
      ),
      scaffoldBackgroundColor: SemanticTokens.backgroundDark,
      cardTheme: CardThemeData(
        color: SemanticTokens.surfaceDark,
        elevation: SemanticTokens.cardElevation,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(SemanticTokens.radiusMd),
          side: const BorderSide(color: SemanticTokens.borderDark),
        ),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: SemanticTokens.primaryNavyDark,
        foregroundColor: Colors.white,
        elevation: 0,
        centerTitle: false,
      ),
      snackBarTheme: const SnackBarThemeData(
        behavior: SnackBarBehavior.floating,
      ),
    );
  }
}
