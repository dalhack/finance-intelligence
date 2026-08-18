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

    test('every endpoint the api client calls exists in the OpenAPI contract',
        () {
      // Guards the failure class where the app calls a path the backend never
      // exposed (e.g. /facts/candidates vs /fact-candidates): the request 404s
      // and the feature is silently dead.
      final specFile = [
        '../contracts/openapi_spec.json',
        '../../contracts/openapi_spec.json',
        'contracts/openapi_spec.json',
      ].map(File.new).firstWhere((f) => f.existsSync());
      final spec =
          jsonDecode(specFile.readAsStringSync()) as Map<String, dynamic>;
      final specPaths = (spec['paths'] as Map<String, dynamic>).keys.toSet();

      final clientFile = [
        'lib/data/api/api_client.dart',
        'apps/mobile/lib/data/api/api_client.dart',
      ].map(File.new).firstWhere((f) => f.existsSync());
      final source = clientFile.readAsStringSync();

      // Collect the literal request paths passed to _dio.<verb>('...').
      final callPattern =
          RegExp(r"""_dio\.(?:get|post|put|patch|delete)\(\s*'([^']+)'""");
      final calls = callPattern
          .allMatches(source)
          .map((m) => m.group(1)!)
          .where((p) => p.startsWith('/'))
          .toSet();

      expect(calls, isNotEmpty,
          reason: 'api client request paths must be discoverable');

      // Normalise Dart interpolation ($id) into OpenAPI template segments.
      String normalise(String path) {
        final segments = path.split('/').map((segment) {
          if (segment.startsWith(r'$')) return '{param}';
          return segment;
        }).join('/');
        return '/api/v1$segments';
      }

      String canonical(String path) => path
          .split('/')
          .map((segment) => segment.startsWith('{') && segment.endsWith('}')
              ? '{param}'
              : segment)
          .join('/');

      // Documented, deliberately-uncontracted paths. This list must never
      // grow: each entry is a known debt with a planned resolution.
      const knownUncontracted = {
        // Development-only synthetic session route, absent from the published
        // contract on purpose.
        '/api/v1/dev-session',
        // Legacy three-step upload protocol, superseded by the single
        // multipart upload; the client methods are scheduled for removal.
        '/api/v1/documents/uploads/{param}/stream',
        // Ingestion polling still addresses jobs by id; the backend exposes
        // status under /documents/{id}/versions/{id}/status. The polling flow
        // is currently not reachable from the UI and is tracked for rework.
        '/api/v1/documents/ingestion-jobs/{param}',
      };

      final knownPaths = specPaths.map(canonical).toSet();
      final missing = calls
          .map(normalise)
          .where((path) => !knownPaths.contains(path))
          .where((path) => !knownUncontracted.contains(path))
          .toList()
        ..sort();

      expect(missing, isEmpty,
          reason:
              'these client paths are absent from the OpenAPI contract: $missing');
    });
  });
}
