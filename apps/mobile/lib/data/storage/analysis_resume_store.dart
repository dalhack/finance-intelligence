import 'dart:convert';
import 'package:crypto/crypto.dart';
import 'package:shared_preferences/shared_preferences.dart';

class AnalysisResumeRecord {
  final int resumeSchemaVersion;
  final String analysisId;
  final int lastAppliedSequence;
  final String? lastEventId;
  final String lifecycleStatus;
  final String createdAt;
  final String lastConnectedAt;
  final String contractVersion;
  final String sessionBindingFingerprint;

  AnalysisResumeRecord({
    this.resumeSchemaVersion = 1,
    required this.analysisId,
    required this.lastAppliedSequence,
    this.lastEventId,
    required this.lifecycleStatus,
    required this.createdAt,
    required this.lastConnectedAt,
    this.contractVersion = "3.0.0",
    required this.sessionBindingFingerprint,
  });

  String get calculateChecksum {
    final raw =
        "resume_v1:$analysisId:$lastAppliedSequence:$lifecycleStatus:$sessionBindingFingerprint";
    return sha256.convert(utf8.encode(raw)).toString();
  }

  Map<String, dynamic> toJson() {
    return {
      'resumeSchemaVersion': resumeSchemaVersion,
      'analysisId': analysisId,
      'lastAppliedSequence': lastAppliedSequence,
      'lastEventId': lastEventId,
      'lifecycleStatus': lifecycleStatus,
      'createdAt': createdAt,
      'lastConnectedAt': lastConnectedAt,
      'contractVersion': contractVersion,
      'sessionBindingFingerprint': sessionBindingFingerprint,
      'checksum': calculateChecksum,
    };
  }

  factory AnalysisResumeRecord.fromJson(Map<String, dynamic> json) {
    if (json['resumeSchemaVersion'] != 1) {
      throw FormatException(
          "Unsupported resume schema version: ${json['resumeSchemaVersion']}");
    }
    if (json['contractVersion'] != "3.0.0") {
      throw FormatException(
          "Unsupported contract version: ${json['contractVersion']}");
    }
    if (json['analysisId'] == null || (json['analysisId'] as String).isEmpty) {
      throw FormatException("Invalid analysisId in resume record");
    }
    if (json['lastAppliedSequence'] == null ||
        (json['lastAppliedSequence'] as int) < 0) {
      throw FormatException("Invalid lastAppliedSequence in resume record");
    }
    if (json['sessionBindingFingerprint'] == null ||
        (json['sessionBindingFingerprint'] as String).isEmpty) {
      throw FormatException(
          "Invalid sessionBindingFingerprint in resume record");
    }

    final record = AnalysisResumeRecord(
      resumeSchemaVersion: json['resumeSchemaVersion'] as int? ?? 1,
      analysisId: json['analysisId'] as String,
      lastAppliedSequence: json['lastAppliedSequence'] as int,
      lastEventId: json['lastEventId'] as String?,
      lifecycleStatus: json['lifecycleStatus'] as String? ?? 'ACTIVE',
      createdAt: json['createdAt'] as String,
      lastConnectedAt: json['lastConnectedAt'] as String,
      contractVersion: json['contractVersion'] as String? ?? '3.0.0',
      sessionBindingFingerprint: json['sessionBindingFingerprint'] as String,
    );

    if (json.containsKey('checksum') &&
        json['checksum'] != record.calculateChecksum) {
      throw FormatException(
          "Resume record checksum mismatch - possible partial write or corruption");
    }

    return record;
  }
}

String computeSessionBindingHash(String opaqueSubject) {
  if (opaqueSubject.isEmpty) {
    throw ArgumentError("opaqueSubject cannot be empty");
  }
  final bytes = utf8.encode("session_binding:$opaqueSubject");
  return sha256.convert(bytes).toString();
}

abstract class AnalysisResumeStore {
  Future<AnalysisResumeRecord?> read();
  Future<void> write(AnalysisResumeRecord record);
  Future<void> updateSequence(int sequence, String? eventId);
  Future<void> markTerminal();
  Future<void> clear();
  Future<void> clearIfSessionMismatch(String currentSessionBindingFingerprint);
}

class SharedPreferencesAnalysisResumeStore implements AnalysisResumeStore {
  static const String _storageKey = "finance_intelligence_resume_record_v1";
  final SharedPreferences _prefs;

  SharedPreferencesAnalysisResumeStore(this._prefs);

  @override
  Future<AnalysisResumeRecord?> read() async {
    final raw = _prefs.getString(_storageKey);
    if (raw == null || raw.isEmpty) return null;
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      return AnalysisResumeRecord.fromJson(json);
    } catch (_) {
      await clear();
      return null;
    }
  }

  @override
  Future<void> write(AnalysisResumeRecord record) async {
    final raw = jsonEncode(record.toJson());
    await _prefs.setString(_storageKey, raw);
  }

  @override
  Future<void> updateSequence(int sequence, String? eventId) async {
    final current = await read();
    if (current == null) return;
    if (sequence < current.lastAppliedSequence) return; // Sequence monotonicity

    final updated = AnalysisResumeRecord(
      resumeSchemaVersion: current.resumeSchemaVersion,
      analysisId: current.analysisId,
      lastAppliedSequence: sequence,
      lastEventId: eventId ?? current.lastEventId,
      lifecycleStatus: current.lifecycleStatus,
      createdAt: current.createdAt,
      lastConnectedAt: DateTime.now().toUtc().toIso8601String(),
      contractVersion: current.contractVersion,
      sessionBindingFingerprint: current.sessionBindingFingerprint,
    );
    await write(updated);
  }

  @override
  Future<void> markTerminal() async {
    await clear();
  }

  @override
  Future<void> clear() async {
    await _prefs.remove(_storageKey);
  }

  @override
  Future<void> clearIfSessionMismatch(
      String currentSessionBindingFingerprint) async {
    final current = await read();
    if (current != null &&
        current.sessionBindingFingerprint != currentSessionBindingFingerprint) {
      await clear();
    }
  }
}

class InMemoryAnalysisResumeStore implements AnalysisResumeStore {
  AnalysisResumeRecord? _record;

  @override
  Future<AnalysisResumeRecord?> read() async => _record;

  @override
  Future<void> write(AnalysisResumeRecord record) async {
    _record = record;
  }

  @override
  Future<void> updateSequence(int sequence, String? eventId) async {
    if (_record == null) return;
    if (sequence < _record!.lastAppliedSequence) return;
    _record = AnalysisResumeRecord(
      resumeSchemaVersion: _record!.resumeSchemaVersion,
      analysisId: _record!.analysisId,
      lastAppliedSequence: sequence,
      lastEventId: eventId ?? _record!.lastEventId,
      lifecycleStatus: _record!.lifecycleStatus,
      createdAt: _record!.createdAt,
      lastConnectedAt: DateTime.now().toUtc().toIso8601String(),
      contractVersion: _record!.contractVersion,
      sessionBindingFingerprint: _record!.sessionBindingFingerprint,
    );
  }

  @override
  Future<void> markTerminal() async {
    _record = null;
  }

  @override
  Future<void> clear() async {
    _record = null;
  }

  @override
  Future<void> clearIfSessionMismatch(
      String currentSessionBindingFingerprint) async {
    if (_record != null &&
        _record!.sessionBindingFingerprint !=
            currentSessionBindingFingerprint) {
      _record = null;
    }
  }
}
