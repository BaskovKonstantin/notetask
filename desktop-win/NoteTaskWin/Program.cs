using System.Diagnostics;
using System.Net.Http;
using System.Runtime.InteropServices;
using Photino.NET;

namespace NoteTaskWin;

internal static class Program
{
    const string PublicOrigin = "https://todo.baski.pro";
    const string LanOrigin = "http://192.168.0.6:8100";
    const int VK_SPACE = 0x20;
    const int VK_CONTROL = 0x11;

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);

    [STAThread]
    private static void Main(string[] args)
    {
        EnsureAutostart();

        var origin = ResolveOrigin();
        var appUrl = $"{origin}/?client=desktop";
        var captureUrl = $"{origin}/?client=desktop#capture";
        var startUrl = args.Any(a => a == "--capture") ? captureUrl : appUrl;

        var window = new PhotinoWindow()
            .SetTitle("NoteTask")
            .SetUseOsDefaultSize(false)
            .SetWidth(1180)
            .SetHeight(820)
            .SetMinWidth(720)
            .SetMinHeight(520)
            .Center()
            .SetUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 NoteTaskDesktop/1.0")
            .Load(startUrl);

        StartGlobalCaptureWatcher(window, captureUrl);
        window.WaitForClose();
    }

    /// <summary>
    /// Home Wi‑Fi often has no NAT hairpin to the public IP — prefer LAN when public health fails.
    /// </summary>
    private static string ResolveOrigin()
    {
        if (ProbeHealth($"{PublicOrigin}/api/health")) return PublicOrigin;
        if (ProbeHealth($"{LanOrigin}/api/health")) return LanOrigin;
        return PublicOrigin;
    }

    private static bool ProbeHealth(string url)
    {
        try
        {
            using var http = new HttpClient { Timeout = TimeSpan.FromSeconds(2) };
            using var res = http.GetAsync(url).GetAwaiter().GetResult();
            return res.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private static void StartGlobalCaptureWatcher(PhotinoWindow window, string captureUrl)
    {
        var cts = new CancellationTokenSource();
        AppDomain.CurrentDomain.ProcessExit += (_, _) => cts.Cancel();

        _ = Task.Run(async () =>
        {
            var wasDown = false;
            while (!cts.IsCancellationRequested)
            {
                try
                {
                    var ctrl = (GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0;
                    var space = (GetAsyncKeyState(VK_SPACE) & 0x8000) != 0;
                    var down = ctrl && space;
                    if (down && !wasDown)
                    {
                        window.Load(captureUrl);
                    }
                    wasDown = down;
                }
                catch
                {
                    /* ignore transient native errors */
                }
                await Task.Delay(40, cts.Token).ConfigureAwait(false);
            }
        }, cts.Token);
    }

    private static void EnsureAutostart()
    {
        try
        {
            if (!OperatingSystem.IsWindows()) return;
            var startup = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Startup),
                "NoteTask.lnk");
            if (File.Exists(startup)) return;

            var exe = Environment.ProcessPath;
            if (string.IsNullOrEmpty(exe) || !File.Exists(exe)) return;
            var workDir = Path.GetDirectoryName(exe) ?? "";

            var script = $$"""
                $s = (New-Object -ComObject WScript.Shell).CreateShortcut('{{startup.Replace("'", "''")}}')
                $s.TargetPath = '{{exe.Replace("'", "''")}}'
                $s.WorkingDirectory = '{{workDir.Replace("'", "''")}}'
                $s.Save()
                """;
            Process.Start(new ProcessStartInfo
            {
                FileName = "powershell",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -Command \"" + script.Replace("\"", "\\\"") + "\"",
                CreateNoWindow = true,
                UseShellExecute = false,
            })?.WaitForExit(8000);
        }
        catch
        {
            /* best-effort */
        }
    }
}
