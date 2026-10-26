package pro.baski.notetask_mobile

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import android.widget.Toast
import androidx.core.content.FileProvider
import org.json.JSONObject
import java.io.File
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

data class RemoteApp(val versionCode: Int, val versionName: String, val apkUrl: String, val size: Long)

object AppUpdate {
    const val SKIP_CODE = "skip_update_code"
    const val PENDING_APK = "pending_apk"

    fun installedCode(activity: Activity): Int {
        val info = activity.packageManager.getPackageInfo(activity.packageName, 0)
        return if (Build.VERSION.SDK_INT >= 28) info.longVersionCode.toInt() else @Suppress("DEPRECATION") info.versionCode
    }

    fun check(activity: Activity, onAvailable: (RemoteApp) -> Unit) {
        val skip = Prefs.store(activity).getInt(SKIP_CODE, 0)
        val local = installedCode(activity)
        val bases = listOf(
            Prefs.store(activity).getString(Prefs.BASE, Prefs.PUBLIC_BASE) ?: Prefs.PUBLIC_BASE,
            Prefs.PUBLIC_BASE,
            Prefs.LAN_BASE,
        ).distinct()
        thread(name = "notetask-update-check") {
            val remote = bases.firstNotNullOfOrNull { fetchMeta(it) } ?: return@thread
            if (remote.versionCode <= local || remote.versionCode == skip) return@thread
            activity.runOnUiThread { onAvailable(remote) }
        }
    }

    fun skip(activity: Activity, code: Int) {
        Prefs.store(activity).edit().putInt(SKIP_CODE, code).apply()
    }

    fun downloadAndInstall(activity: Activity, remote: RemoteApp, onProgress: (String) -> Unit) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && !activity.packageManager.canRequestPackageInstalls()) {
            Toast.makeText(activity, "Разреши установку из этого приложения", Toast.LENGTH_LONG).show()
            activity.startActivity(
                Intent(
                    Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                    Uri.parse("package:${activity.packageName}"),
                ),
            )
            return
        }
        onProgress("Загрузка…")
        thread(name = "notetask-update-dl") {
            try {
                val dir = File(activity.cacheDir, "updates").apply { mkdirs() }
                val out = File(dir, "NoteTask.apk")
                val conn = URL(remote.apkUrl).openConnection() as HttpURLConnection
                conn.connectTimeout = 8000
                conn.readTimeout = 60000
                conn.instanceFollowRedirects = true
                if (conn.responseCode !in 200..299) throw IllegalStateException("http ${conn.responseCode}")
                conn.inputStream.use { input ->
                    out.outputStream().use { input.copyTo(it) }
                }
                conn.disconnect()
                Prefs.store(activity).edit().putString(PENDING_APK, out.absolutePath).apply()
                activity.runOnUiThread { install(activity, out) }
            } catch (e: Exception) {
                activity.runOnUiThread {
                    onProgress("Обновить")
                    Toast.makeText(activity, "Не удалось скачать обновление", Toast.LENGTH_LONG).show()
                }
            }
        }
    }

    fun install(activity: Activity, apk: File) {
        if (!apk.isFile) return
        val uri = FileProvider.getUriForFile(activity, "${activity.packageName}.fileprovider", apk)
        val intent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, "application/vnd.android.package-archive")
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        activity.startActivity(intent)
    }

    private fun fetchMeta(base: String): RemoteApp? {
        return try {
            val root = base.trimEnd('/')
            val conn = URL("$root/api/android-update").openConnection() as HttpURLConnection
            conn.connectTimeout = 4000
            conn.readTimeout = 6000
            conn.setRequestProperty("Accept", "application/json")
            val code = conn.responseCode
            val body = (if (code in 200..299) conn.inputStream else conn.errorStream)
                ?.bufferedReader()?.use { it.readText() }.orEmpty()
            conn.disconnect()
            if (code != 200) return null
            val obj = JSONObject(body)
            val vc = obj.optInt("versionCode", 0)
            val url = obj.optString("url")
            if (vc <= 0 || url.isBlank()) return null
            val apkUrl = if (url.startsWith("http")) url else "$root$url"
            RemoteApp(
                versionCode = vc,
                versionName = obj.optString("versionName"),
                apkUrl = apkUrl,
                size = obj.optLong("size", 0),
            )
        } catch (_: Exception) {
            null
        }
    }
}
