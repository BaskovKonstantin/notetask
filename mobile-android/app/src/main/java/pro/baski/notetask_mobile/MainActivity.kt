package pro.baski.notetask_mobile

import android.annotation.SuppressLint
import android.app.Activity
import android.os.Bundle
import android.view.View
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

class MainActivity : Activity() {
    private lateinit var web: WebView
    private lateinit var errorPanel: View
    private lateinit var errorText: TextView
    private lateinit var updateBar: LinearLayout
    private lateinit var updateText: TextView
    private lateinit var btnUpdate: Button
    private var pendingRemote: RemoteApp? = null
    private var loadedOk = false

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        web = findViewById(R.id.web)
        errorPanel = findViewById(R.id.error_panel)
        errorText = findViewById(R.id.error_text)
        updateBar = findViewById(R.id.update_bar)
        updateText = findViewById(R.id.update_text)
        btnUpdate = findViewById(R.id.btn_update)
        findViewById<Button>(R.id.btn_retry).setOnClickListener { load(Prefs.PUBLIC_BASE) }
        findViewById<Button>(R.id.btn_lan).setOnClickListener { load(Prefs.LAN_BASE) }
        btnUpdate.setOnClickListener {
            val remote = pendingRemote ?: return@setOnClickListener
            AppUpdate.downloadAndInstall(this, remote) { btnUpdate.text = it }
        }
        findViewById<Button>(R.id.btn_update_later).setOnClickListener {
            pendingRemote?.let { AppUpdate.skip(this, it.versionCode) }
            updateBar.visibility = View.GONE
        }

        CookieManager.getInstance().setAcceptCookie(true)
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, true)
        web.settings.apply {
            javaScriptEnabled = true
            domStorageEnabled = true
            databaseEnabled = true
            cacheMode = WebSettings.LOAD_DEFAULT
            mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
            useWideViewPort = true
            loadWithOverviewMode = false
            builtInZoomControls = false
            displayZoomControls = false
            textZoom = 100
            userAgentString = "$userAgentString NoteTaskAndroid"
        }
        web.setInitialScale(100)
        web.webChromeClient = WebChromeClient()
        web.webViewClient = object : WebViewClient() {
            override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
                val host = request.url.host ?: return false
                return host != "todo.baski.pro" && host != "192.168.0.6" && host != "baski.pro"
            }

            override fun onPageFinished(view: WebView, url: String) {
                if (loadedOk) hideError()
                pullTokenAndWidget()
            }

            override fun onReceivedError(
                view: WebView,
                request: WebResourceRequest,
                error: WebResourceError,
            ) {
                if (!request.isForMainFrame) return
                loadedOk = false
                showError("Нет связи с ${request.url.host ?: "сайтом"}")
            }
        }
        load(Prefs.store(this).getString(Prefs.BASE, Prefs.PUBLIC_BASE) ?: Prefs.PUBLIC_BASE)
        AppUpdate.check(this, ::showUpdate)
    }

    private fun load(base: String) {
        loadedOk = true
        hideError()
        Prefs.store(this).edit().putString(Prefs.BASE, base).apply()
        val root = base.trimEnd('/')
        web.loadUrl(root)
    }

    private fun showError(msg: String) {
        errorText.text = msg
        errorPanel.visibility = View.VISIBLE
    }

    private fun hideError() {
        errorPanel.visibility = View.GONE
    }

    private fun pullTokenAndWidget() {
        web.evaluateJavascript(
            "(function(){try{return localStorage.getItem('notetask_token')||'';}catch(e){return '';}})()",
        ) { raw ->
            val token = raw?.trim('"')?.replace("\\\"", "\"")?.replace("\\\\", "\\").orEmpty()
            val clean = if (token == "null") "" else token
            Prefs.store(this).edit().putString(Prefs.TOKEN, clean).apply()
            WidgetSync.refreshAsync(this)
        }
    }

    override fun onResume() {
        super.onResume()
        if (::web.isInitialized) pullTokenAndWidget()
        AppUpdate.check(this, ::showUpdate)
    }

    private fun showUpdate(remote: RemoteApp) {
        pendingRemote = remote
        val label = remote.versionName.ifBlank { remote.versionCode.toString() }
        updateText.text = "Доступна версия $label"
        btnUpdate.text = "Обновить"
        updateBar.visibility = View.VISIBLE
    }

    override fun onBackPressed() {
        if (::web.isInitialized && web.canGoBack()) {
            web.goBack()
            return
        }
        super.onBackPressed()
    }
}
