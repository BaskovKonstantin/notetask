import 'dart:convert';

import 'package:http/http.dart' as http;

class NoteTaskApi {
  NoteTaskApi({required this.baseUrl, this.token});

  final String baseUrl;
  String? token;

  Map<String, String> get _headers => {
        'Content-Type': 'application/json',
        if (token != null && token!.isNotEmpty) 'Authorization': 'Bearer $token',
      };

  Uri _u(String path, [Map<String, String>? q]) =>
      Uri.parse('$baseUrl$path').replace(queryParameters: q);

  Future<String> login(String password) async {
    final res = await http.post(
      _u('/api/login'),
      headers: _headers,
      body: jsonEncode({'password': password}),
    );
    if (res.statusCode != 200) {
      throw Exception('login ${res.statusCode}');
    }
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return data['token'] as String;
  }

  Future<List<dynamic>> projects() async {
    final res = await http.get(_u('/api/projects'), headers: _headers);
    if (res.statusCode != 200) throw Exception('projects ${res.statusCode}');
    return jsonDecode(res.body) as List<dynamic>;
  }

  Future<List<Map<String, dynamic>>> todayTasks() async {
    final res = await http.get(
      _u('/api/tasks', {'view': 'today'}),
      headers: _headers,
    );
    if (res.statusCode != 200) throw Exception('tasks ${res.statusCode}');
    final list = jsonDecode(res.body) as List<dynamic>;
    return list.cast<Map<String, dynamic>>();
  }

  Future<Map<String, dynamic>> complete(int id) async {
    final res = await http.post(_u('/api/tasks/$id/complete'), headers: _headers);
    if (res.statusCode != 200) throw Exception('complete ${res.statusCode}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<Map<String, dynamic>> createTask(String title) async {
    final res = await http.post(
      _u('/api/tasks'),
      headers: _headers,
      body: jsonEncode({
        'title': title,
        'kind': 'task',
        'priority': 4,
        'due_at': DateTime.now().toIso8601String().substring(0, 10),
      }),
    );
    if (res.statusCode != 200) throw Exception('create ${res.statusCode}');
    return jsonDecode(res.body) as Map<String, dynamic>;
  }
}
