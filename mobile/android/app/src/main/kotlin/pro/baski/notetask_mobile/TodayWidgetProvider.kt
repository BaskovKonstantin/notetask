package pro.baski.notetask_mobile

import android.appwidget.AppWidgetManager
import android.content.Context
import android.content.SharedPreferences
import android.widget.RemoteViews
import es.antonborri.home_widget.HomeWidgetProvider

class TodayWidgetProvider : HomeWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
        widgetData: SharedPreferences,
    ) {
        appWidgetIds.forEach { widgetId ->
            val views = RemoteViews(context.packageName, R.layout.today_widget).apply {
                val lines = widgetData.getString("today_lines", "Открой NoteTask") ?: "Открой NoteTask"
                val count = widgetData.getInt("today_count", 0)
                setTextViewText(R.id.widget_title, "Сегодня · $count")
                setTextViewText(R.id.widget_lines, lines)
            }
            appWidgetManager.updateAppWidget(widgetId, views)
        }
    }
}
