import 'package:decimal/decimal.dart';

class FinancialValue {
  final String rawString;
  final Decimal decimalValue;
  final String? currency;
  final String unit;
  final String scale;
  final String displayText;

  FinancialValue._({
    required this.rawString,
    required this.decimalValue,
    this.currency,
    required this.unit,
    required this.scale,
    required this.displayText,
  });

  factory FinancialValue.parse({
    required String rawValue,
    String? currency,
    required String unit,
    required String scale,
    required String displayText,
  }) {
    final trimmed = rawValue.trim();
    if (trimmed.contains('e') || trimmed.contains('E')) {
      throw FormatException(
          'INVALID_DECIMAL_FORMAT: Scientific notation is prohibited for financial values ($rawValue).');
    }

    try {
      final dec = Decimal.parse(trimmed);
      return FinancialValue._(
        rawString: trimmed,
        decimalValue: dec,
        currency: currency,
        unit: unit,
        scale: scale,
        displayText: displayText,
      );
    } catch (e) {
      throw FormatException(
          'INVALID_DECIMAL_FORMAT: Cannot parse "$rawValue" as Decimal.');
    }
  }

  bool get isNegative => decimalValue < Decimal.zero;

  @override
  String toString() => displayText;
}
