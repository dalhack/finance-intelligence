import 'package:flutter_test/flutter_test.dart';
import 'package:finance_intelligence/core/models/app_exception.dart';
import 'package:finance_intelligence/features/review/presentation/review_error_messages.dart';

AppException _error(String code, {String message = ''}) => ValidationException(
      code: code,
      message: message.isEmpty ? code : message,
      requestId: 'req-1',
    );

void main() {
  test('a code a reviewer cannot act on becomes a sentence they can', () {
    final message = reviewDecisionErrorMessage(_error('CANDIDATE_ALREADY_REVIEWED'));
    expect(message, contains('zaten incelenmiş'));
    expect(message, isNot(contains('CANDIDATE_ALREADY_REVIEWED')));
  });

  test('a conflict says what to do next', () {
    expect(reviewDecisionErrorMessage(_error('FACT_VALUE_CONFLICT')), contains('Düzeltme'));
  });

  test('an untranslated code is still shown rather than hidden', () {
    // Quoting an unknown code beats an apology that tells the reviewer nothing.
    expect(reviewDecisionErrorMessage(_error('SOME_NEW_SERVER_CODE')),
        contains('SOME_NEW_SERVER_CODE'));
  });

  test('a non-exception failure still produces text', () {
    expect(reviewDecisionErrorMessage(StateError('boom')), isNotEmpty);
  });
}
