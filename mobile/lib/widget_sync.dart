import 'package:home_widget/home_widget.dart';

const androidWidgetName = 'TodayWidgetProvider';
const qualifiedAndroidName = 'pro.baski.notetask_mobile.TodayWidgetProvider';

Future<void> syncTodayWidget(List<Map<String, dynamic>> openTasks) async {
  final titles = openTasks
      .take(8)
      .map((t) => (t['title'] as String? ?? '').trim())
      .where((t) => t.isNotEmpty)
      .toList();
  final text = titles.isEmpty ? 'Нет открытых задач' : titles.join('\n');
  await HomeWidget.saveWidgetData<String>('today_lines', text);
  await HomeWidget.saveWidgetData<int>('today_count', openTasks.length);
  await HomeWidget.updateWidget(
    name: androidWidgetName,
    androidName: androidWidgetName,
    qualifiedAndroidName: qualifiedAndroidName,
  );
}
