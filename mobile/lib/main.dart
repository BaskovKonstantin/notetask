import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:notetask_mobile/api.dart';
import 'package:notetask_mobile/today_page.dart';

const _tokenKey = 'notetask_token';
const _preferredBase = String.fromEnvironment(
  'API_BASE',
  defaultValue: kPublicBase,
);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const NoteTaskApp());
}

class NoteTaskApp extends StatelessWidget {
  const NoteTaskApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'NoteTask',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1F6B4E),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      home: const _BootGate(),
    );
  }
}

class _BootGate extends StatefulWidget {
  const _BootGate();

  @override
  State<_BootGate> createState() => _BootGateState();
}

class _BootGateState extends State<_BootGate> {
  final _storage = const FlutterSecureStorage();
  NoteTaskApi? _api;
  String _baseUrl = _preferredBase;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    final base = await resolveApiBase(preferred: _preferredBase);
    final token = await _storage.read(key: _tokenKey);
    if (token != null && token.isNotEmpty) {
      final api = NoteTaskApi(baseUrl: base, token: token);
      try {
        await api.projects();
        if (!mounted) return;
        setState(() {
          _baseUrl = base;
          _api = api;
          _loading = false;
        });
        return;
      } catch (_) {
        await _storage.delete(key: _tokenKey);
      }
    }
    if (!mounted) return;
    setState(() {
      _baseUrl = base;
      _loading = false;
    });
  }

  Future<void> _onLoggedIn(NoteTaskApi api, String token) async {
    await _storage.write(key: _tokenKey, value: token);
    setState(() {
      _baseUrl = api.baseUrl;
      _api = api;
    });
  }

  Future<void> _logout() async {
    await _storage.delete(key: _tokenKey);
    setState(() => _api = null);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    final api = _api;
    if (api == null) {
      return LoginPage(baseUrl: _baseUrl, onLoggedIn: _onLoggedIn);
    }
    return TodayPage(api: api, onLogout: _logout);
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.baseUrl, required this.onLoggedIn});

  final String baseUrl;
  final Future<void> Function(NoteTaskApi api, String token) onLoggedIn;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _password = TextEditingController();
  String? _error;
  bool _busy = false;

  Future<void> _submit() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      final base = await resolveApiBase(preferred: widget.baseUrl);
      final api = NoteTaskApi(baseUrl: base);
      final token = await api.login(_password.text);
      api.token = token;
      await widget.onLoggedIn(api, token);
    } catch (e) {
      setState(() => _error = 'Неверный пароль или нет сети');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  void dispose() {
    _password.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 360),
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Text(
                  'NoteTask',
                  style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                ),
                const SizedBox(height: 8),
                Text(
                  'Задачи на сегодня · виджет на рабочем столе',
                  style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
                const SizedBox(height: 24),
                TextField(
                  controller: _password,
                  obscureText: true,
                  decoration: const InputDecoration(
                    labelText: 'Пароль',
                    border: OutlineInputBorder(),
                  ),
                  onSubmitted: (_) => _submit(),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
                ],
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _busy ? null : _submit,
                  child: Text(_busy ? 'Вход…' : 'Войти'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
