import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/features/comparisons/presentation/widgets/chart_spec_native_widget.dart';

void main() {
  group('ChartCoordinateAdapter & Table/Chart Equality', () {
    test('Converts canonical decimal string safely without NaN or Infinity',
        () {
      expect(ChartCoordinateAdapter.safeToDouble('1500000.50'),
          equals(1500000.50));
      expect(ChartCoordinateAdapter.safeToDouble('-9500.25'), equals(-9500.25));
      expect(ChartCoordinateAdapter.safeToDouble('0.0000'), equals(0.0));
    });

    test('Fails safely on invalid or infinite values by returning 0.0', () {
      expect(ChartCoordinateAdapter.safeToDouble('invalid_text'), equals(0.0));
      expect(ChartCoordinateAdapter.safeToDouble(''), equals(0.0));
    });
  });
}
