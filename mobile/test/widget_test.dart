import 'package:flutter_test/flutter_test.dart';
import 'package:notetask_mobile/api.dart';

void main() {
  test('api builds login uri', () {
    final api = NoteTaskApi(baseUrl: 'https://todo.baski.pro');
    expect(api.baseUrl, contains('todo.baski.pro'));
  });
}
