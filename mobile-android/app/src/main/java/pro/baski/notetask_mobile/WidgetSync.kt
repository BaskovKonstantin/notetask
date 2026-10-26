package pro.baski.notetask_mobile

import android.appwidget.AppWidgetManager
import android.content.ComponentName
import android.content.Context
import android.widget.RemoteViews
import org.json.JSONArray
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

object WidgetSync {
    fun refreshAsync(context: Context) {
        val app = context.applicationContext
        thread(name = "notetask-widget") {
            refresh(app)
        }
    }

    fun refresh(context: Context) {
        val prefs = Prefs.store(context)
        val token = prefs.getString(Prefs.TOKEN, null).orEmpty()
        val base = prefs.getString(Prefs.BASE, Prefs.PUBLIC_BASE) ?: Prefs.PUBLIC_BASE
        val lines: String
        val count: Int
        if (token.isBlank()) {
            lines = "Войди в NoteTask"
            count = 0
        } else {
            val fetched = fetchOpenTitles(base, token) ?: fetchOpenTitles(
                if (base == Prefs.PUBLIC_BASE) Prefs.LAN_BASE else Prefs.PUBLIC_BASE,
                token,
            )
            if (fetched == null) {
                lines = "Нет связи"
                count = prefs.getInt(Prefs.COUNT, 0)
            } else {
                count = fetched.size
                lines = if (fetched.isEmpty()) "Нет открытых задач" else fetched.take(8).joinToString("\n")
                prefs.edit()
                    .putString(Prefs.LINES, lines)
                    .putInt(Prefs.COUNT, count)
                    .apply()
            }
        }
        push(context, lines, count)
    }

    private fun fetchOpenTitles(base: String, token: String): List<String>? {
        return try {
            val conn = URL("$base/api/tasks?view=today").openConnection() as HttpURLConnection
            conn.connectTimeout = 4000
            conn.readTimeout = 6000
            conn.setRequestProperty("Authorization", "Bearer $token")
            conn.setRequestProperty("Accept", "application/json")
            conn.instanceFollowRedirects = true
            val code = conn.responseCode
            val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader()
                ?.use { it.readText() }
                .orEmpty()
            conn.disconnect()
            if (code != 200) return null
            val arr = JSONArray(body)
            val out = ArrayList<String>()
            for (i in 0 until arr.length()) {
                val obj = arr.optJSONObject(i) ?: continue
                val status = obj.optString("status", "open")
                if (status != "open") continue
                val title = obj.optString("title").trim()
                if (title.isNotEmpty()) out.add(title)
            }
            out
        } catch (_: Exception) {
            null
        }
    }

    fun push(context: Context, lines: String, count: Int) {
        val views = RemoteViews(context.packageName, R.layout.today_widget).apply {
            setTextViewText(R.id.widget_title, "Сегодня · $count")
            setTextViewText(R.id.widget_lines, lines)
        }
        val ids = AppWidgetManager.getInstance(context)
            .getAppWidgetIds(ComponentName(context, TodayWidgetProvider::class.java))
        if (ids.isEmpty()) return
        AppWidgetManager.getInstance(context).updateAppWidget(ids, views)
    }
}
