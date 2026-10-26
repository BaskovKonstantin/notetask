package pro.baski.notetask_mobile

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

class TodayWidgetProvider : AppWidgetProvider() {
    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray,
    ) {
        val prefs = Prefs.store(context)
        val lines = prefs.getString(Prefs.LINES, "Открой NoteTask") ?: "Открой NoteTask"
        val count = prefs.getInt(Prefs.COUNT, 0)
        val launch = PendingIntent.getActivity(
            context,
            0,
            Intent(context, MainActivity::class.java).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        appWidgetIds.forEach { id ->
            val views = RemoteViews(context.packageName, R.layout.today_widget).apply {
                setTextViewText(R.id.widget_title, "Сегодня · $count")
                setTextViewText(R.id.widget_lines, lines)
                setOnClickPendingIntent(R.id.widget_root, launch)
            }
            appWidgetManager.updateAppWidget(id, views)
        }
        WidgetSync.refreshAsync(context)
    }
}
