import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/financial_value.dart';

void main() {
  group('Lossless Financial Decimal Handling', () {
    test('Parses very large financial decimal string without float loss', () {
      const rawVal = '123456789012345678.9012345678';
      final finVal = FinancialValue.parse(
        rawValue: rawVal,
        currency: 'TRY',
        unit: 'CURRENCY',
        scale: 'ONE',
        displayText: '123,456,789,012,345,678.90',
      );

      expect(finVal.rawString, equals(rawVal));
      expect(finVal.decimalValue.toString(), equals(rawVal));
      expect(finVal.isNegative, isFalse);
    });

    test('Parses negative decimal value', () {
      const rawVal = '-9500000.5000';
      final finVal = FinancialValue.parse(
        rawValue: rawVal,
        currency: 'TRY',
        unit: 'CURRENCY',
        scale: 'ONE',
        displayText: '-9,500,000.50',
      );

      expect(finVal.isNegative, isTrue);
      expect(finVal.rawString, equals(rawVal));
    });

    test('Prohibits scientific notation (1e10)', () {
      expect(
        () => FinancialValue.parse(
          rawValue: '1e10',
          currency: 'TRY',
          unit: 'CURRENCY',
          scale: 'ONE',
          displayText: '1e10',
        ),
        throwsFormatException,
      );
    });
  });
}
