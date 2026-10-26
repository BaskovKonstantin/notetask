package pro.baski.notetask_mobile

import android.content.Context

object Prefs {
    const val FILE = "notetask"
    const val TOKEN = "notetask_token"
    const val BASE = "api_base"
    const val LINES = "today_lines"
    const val COUNT = "today_count"

    const val PUBLIC_BASE = "https://todo.baski.pro"
    const val LAN_BASE = "http://192.168.0.6"

    fun store(context: Context) = context.getSharedPreferences(FILE, Context.MODE_PRIVATE)
}
