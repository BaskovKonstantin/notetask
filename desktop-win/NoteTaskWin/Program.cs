using System.Diagnostics;
using System.Net;
using System.Net.Http;
using System.Runtime.InteropServices;
using System.Text;
using Photino.NET;

namespace NoteTaskWin;

internal static class Program
{
    const string AppUrl = "https://todo.baski.pro/?client=desktop";
    const string LanUrl = "http://192.168.0.6:8100/?client=desktop";
    const string CaptureOverlayUrl = "https://todo.baski.pro/capture";
    const string LanCaptureOverlayUrl = "http://192.168.0.6:8100/capture";
    const string LanIp = "192.168.0.6";
    const string HostName = "todo.baski.pro";
    const int VK_SPACE = 0x20;
    const int VK_CONTROL = 0x11;

    [DllImport("user32.dll")]
    private static extern short GetAsyncKeyState(int vKey);

    [STAThread]
    private static void Main(string[] args)
    {
        EnsureAutostart();
        EnsureLanHostsEntry();

        if (args.Any(a => a == "--overlay" || a == "--capture"))
        {
            RunOverlay();
            return;
        }

        var startUrl = PickStartUrl(overlay: false);
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

        StartGlobalCaptureWatcher();
        window.WaitForClose();
    }

    private static void RunOverlay()
    {
        var url = PickStartUrl(overlay: true);
        var window = new PhotinoWindow()
            .SetTitle("NoteTask · задача")
            .SetUseOsDefaultSize(false)
            .SetWidth(460)
            .SetHeight(150)
            .SetResizable(false)
            .SetTopMost(true)
            .Center()
            .SetUserAgent(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 NoteTaskDesktop/1.0")
            .Load(url);
        window.WaitForClose();
    }

    private static string PickStartUrl(bool overlay)
    {
        if (CanReach("http://192.168.0.6:8100/api/health", 1200))
            return overlay ? LanCaptureOverlayUrl : LanUrl;
        if (CanReach("https://todo.baski.pro/api/health", 4000))
            return overlay ? CaptureOverlayUrl : AppUrl;
        return overlay ? LanCaptureOverlayUrl : LanUrl;
    }

    private static bool CanReach(string url, int timeoutMs)
    {
        try
        {
            using var client = new HttpClient { Timeout = TimeSpan.FromMilliseconds(timeoutMs) };
            using var resp = client.GetAsync(url).GetAwaiter().GetResult();
            return resp.IsSuccessStatusCode;
        }
        catch
        {
            return false;
        }
    }

    private static void EnsureLanHostsEntry()
    {
        try
        {
            if (!OperatingSystem.IsWindows()) return;
            if (!LooksLikePublicHairpin()) return;

            var hostsPath = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.System),
                "drivers",
                "etc",
                "hosts");
            if (!File.Exists(hostsPath)) return;

            var text = File.ReadAllText(hostsPath, Encoding.ASCII);
            if (text.Contains(HostName, StringComparison.OrdinalIgnoreCase)) return;

            var line = $"{LanIp} {HostName}";
            var suffix = text.EndsWith("\n", StringComparison.Ordinal) ? line + "\n" : "\n" + line + "\n";
            File.AppendAllText(hostsPath, suffix, Encoding.ASCII);
        }
        catch
        {
            /* needs admin once — PickStartUrl falls back to LAN HTTP */
        }
    }

    private static bool LooksLikePublicHairpin()
    {
        try
        {
            var addrs = Dns.GetHostAddresses(HostName);
            return addrs.Any(a => a.ToString() == "5.144.98.126");
        }
        catch
        {
            return false;
        }
    }

    private static void StartGlobalCaptureWatcher()
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
                        LaunchOverlayProcess();
                    }
                    wasDown = down;
                }
                catch
                {
                    /* ignore */
                }
                await Task.Delay(80, cts.Token).ConfigureAwait(false);
            }
        }, cts.Token);
    }

    private static void LaunchOverlayProcess()
    {
        try
        {
            var exe = Environment.ProcessPath;
            if (string.IsNullOrEmpty(exe)) return;
            Process.Start(
                new ProcessStartInfo
                {
                    FileName = exe,
                    Arguments = "--overlay",
                    UseShellExecute = false,
                });
        }
        catch
        {
            /* ignore */
        }
    }

    private static void EnsureAutostart()
    {
        try
        {
            if (!OperatingSystem.IsWindows()) return;
            var exe = Environment.ProcessPath;
            if (string.IsNullOrEmpty(exe)) return;
            var startup = Environment.GetFolderPath(Environment.SpecialFolder.Startup);
            var lnk = Path.Combine(startup, "NoteTask.lnk");
            if (File.Exists(lnk)) return;

            var ps =
                "$s=(New-Object -ComObject WScript.Shell).CreateShortcut('"
                + lnk.Replace("'", "''")
                + "');$s.TargetPath='"
                + exe.Replace("'", "''")
                + "';$s.WorkingDirectory='"
                + Path.GetDirectoryName(exe)!.Replace("'", "''")
                + "';$s.Save()";
            Process.Start(
                new ProcessStartInfo
                {
                    FileName = "powershell",
                    Arguments = "-NoProfile -Command " + ps,
                    CreateNoWindow = true,
                    UseShellExecute = false,
                })?.WaitForExit(5000);
        }
        catch
        {
            /* ignore */
        }
    }
}
