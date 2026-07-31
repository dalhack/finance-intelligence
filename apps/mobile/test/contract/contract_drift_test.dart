import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('Backend Contract Drift Gate', () {
    test('OpenAPI contract snapshot matches expected Flutter wire model schema',
        () {
      List<String> candidatePaths = [
        '../contracts/openapi_spec.json',
        '../../contracts/openapi_spec.json',
        'contracts/openapi_spec.json',
      ];

      File? specFile;
      for (final p in candidatePaths) {
        final f = File(p);
        if (f.existsSync()) {
          specFile = f;
          break;
        }
      }

      expect(specFile != null && specFile.existsSync(), isTrue,
          reason: 'contracts/openapi_spec.json must exist');

      final content = specFile!.readAsStringSync();
      final Map<String, dynamic> spec = jsonDecode(content);

      final paths = spec['paths'] as Map<String, dynamic>;
      expect(paths.containsKey('/api/v1/comparisons'), isTrue);
      expect(paths.containsKey('/api/v1/comparisons/{comparison_id}'), isTrue);
      expect(paths.containsKey('/api/v1/documents/uploads'), isTrue);
      expect(paths.containsKey('/api/v1/evidence/{evidence_id}'), isTrue);

      final components = spec['components'] as Map<String, dynamic>? ?? {};
      final schemas = components['schemas'] as Map<String, dynamic>? ?? {};

      // Verify ResultDatasetDTO
      expect(schemas.containsKey('ResultDatasetDTO'), isTrue);
      final dsSchema = schemas['ResultDatasetDTO'] as Map<String, dynamic>;
      final dsProps = dsSchema['properties'] as Map<String, dynamic>;
      expect(dsProps.containsKey('schema_version'), isTrue);
      expect(dsProps.containsKey('data_quality_summary'), isTrue);

      // Verify ComparisonRequestDTO
      expect(schemas.containsKey('ComparisonRequestDTO'), isTrue);
      final reqSchema = schemas['ComparisonRequestDTO'] as Map<String, dynamic>;
      final reqProps = reqSchema['properties'] as Map<String, dynamic>;
      expect(reqProps.containsKey('semantic_measures'), isTrue);
      expect(reqProps.containsKey('reporting_basis'), isTrue);
    });
  });
}
