import '../../../core/models/app_exception.dart';

/// Turns a refused review decision into a sentence a reviewer can act on.
///
/// The server answers with a code — `CANDIDATE_ALREADY_REVIEWED`,
/// `FACT_VALUE_CONFLICT` — which is precise for a log and useless on a phone.
/// Codes without a translation are still shown, because an untranslated code
/// the reviewer can quote is better than a vague apology that hides it.
String reviewDecisionErrorMessage(Object error) {
  final code = error is AppException ? error.code : null;
  final message = error is AppException ? error.message : error.toString();

  switch (code) {
    case 'CANDIDATE_ALREADY_REVIEWED':
      return 'Bu aday zaten incelenmiş. Liste yenilendi.';
    case 'CANDIDATE_NOT_FOUND':
      return 'Bu aday artık bulunmuyor. Liste yenilendi.';
    case 'CANNOT_APPROVE_WITHOUT_METRIC_DEFINITION':
      return 'Bu kalem tanımlı bir metriğe bağlanamadı, bu haliyle onaylanamaz.';
    case 'CANNOT_APPROVE_UNPARSED_VALUE':
      return 'Bu adayın değeri okunamadığı için onaylanamaz.';
    case 'FACT_VALUE_CONFLICT':
      return 'Aynı kalem için farklı değerde doğrulanmış bir kayıt var. '
          'Düzeltme olarak onaylamanız gerekiyor.';
    case 'REPORTING_BASIS_REQUIRED':
      return 'Raporlama bazı (solo / konsolide) belirlenemedi, lütfen seçin.';
    case 'EVIDENCE_INCOMPLETE':
    case 'EVIDENCE_LINEAGE_INCOMPLETE':
      return 'Bu adayın kaynak kanıtı eksik olduğu için onaylanamaz.';
    case 'PERMISSION_DENIED':
      return 'Bu işlem için yetkiniz yok.';
    case 'NETWORK_UNAVAILABLE':
      return 'Sunucuya bağlanılamadı. Bağlantınızı kontrol edip tekrar deneyin.';
    case 'NETWORK_TIMEOUT':
      return 'Sunucu zamanında yanıt vermedi. Lütfen tekrar deneyin.';
  }

  // The server sends its code as the message for domain refusals; showing the
  // raw exception wrapper on top of it only adds noise.
  return message.isEmpty ? 'İşlem tamamlanamadı.' : message;
}
