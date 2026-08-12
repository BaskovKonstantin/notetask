import 'package:flutter/material.dart';
import 'package:home_widget/home_widget.dart';
import 'package:notetask_mobile/api.dart';
import 'package:notetask_mobile/widget_sync.dart';

class TodayPage extends StatefulWidget {
  const TodayPage({super.key, required this.api, required this.onLogout});

  final NoteTaskApi api;
  final Future<void> Function() onLogout;

  @override
  State<TodayPage> createState() => _TodayPageState();
}

class _TodayPageState extends State<TodayPage> {
  List<Map<String, dynamic>> _tasks = [];
  bool _loading = true;
  String? _error;
  final _add = TextEditingController();

  @override
  void initState() {
    super.initState();
    _reload();
    HomeWidget.widgetClicked.listen((_) {
      _reload();
    });
  }

  @override
  void dispose() {
    _add.dispose();
    super.dispose();
  }

  Future<void> _reload() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final tasks = await widget.api.todayTasks();
      final open = tasks
          .where((t) => (t['status'] as String? ?? 'open') == 'open')
          .toList();
      setState(() {
        _tasks = open;
        _loading = false;
      });
      await syncTodayWidget(open);
    } catch (e) {
      setState(() {
        _error = 'Не удалось загрузить задачи';
        _loading = false;
      });
    }
  }

  Future<void> _complete(Map<String, dynamic> task) async {
    final id = task['id'] as int;
    try {
      await widget.api.complete(id);
      await _reload();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Ошибка выполнения')),
      );
    }
  }

  Future<void> _create() async {
    final title = _add.text.trim();
    if (title.isEmpty) return;
    _add.clear();
    try {
      await widget.api.createTask(title);
      await _reload();
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Не удалось добавить')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Сегодня'),
        actions: [
          IconButton(onPressed: _reload, icon: const Icon(Icons.refresh)),
          IconButton(
            onPressed: widget.onLogout,
            icon: const Icon(Icons.logout),
            tooltip: 'Выйти',
          ),
        ],
      ),
      body: Column(
        children: [
          if (_loading) const LinearProgressIndicator(minHeight: 2),
          if (_error != null)
            Padding(
              padding: const EdgeInsets.all(16),
              child: Text(_error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
            ),
          Expanded(
            child: RefreshIndicator(
              onRefresh: _reload,
              child: ListView.builder(
                itemCount: _tasks.length,
                itemBuilder: (context, i) {
                  final t = _tasks[i];
                  return ListTile(
                    leading: IconButton(
                      icon: const Icon(Icons.circle_outlined),
                      onPressed: () => _complete(t),
                    ),
                    title: Text(t['title'] as String? ?? ''),
                    subtitle: t['due_at'] != null ? Text('${t['due_at']}') : null,
                  );
                },
              ),
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _add,
                      decoration: const InputDecoration(
                        hintText: 'Новая задача…',
                        border: OutlineInputBorder(),
                        isDense: true,
                      ),
                      onSubmitted: (_) => _create(),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(onPressed: _create, child: const Text('+')),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
