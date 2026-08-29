using System.Diagnostics;
using System.Net;
using System.Runtime.InteropServices;
using System.Text;
using Photino.NET;

namespace NoteTaskWin;

internal static class Program
{
    const string AppUrl = "https://todo.baski.pro/?client=desktop";
    const string CaptureUrl = "https://todo.baski.pro/?client=desktop#capture";
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

        var startUrl = args.Any(a => a == "--capture") ? CaptureUrl : AppUrl;
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

        StartGlobalCaptureWatcher(window);
        window.WaitForClose();
    }

    /// <summary>
    /// Home Wi‑Fi has no NAT hairpin to the public IP. Split-DNS (dnsmasq) maps
    /// todo.baski.pro → LAN IP; if Windows uses 8.8.8.8, write a hosts line so the
    /// domain still hits the same server (Caddy + LE cert), never a raw :8100 URL.
    /// </summary>
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
            /* needs admin once — domain still works outside LAN / with DNS 192.168.0.6 */
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

    private static void StartGlobalCaptureWatcher(PhotinoWindow window)
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
                        window.Load(CaptureUrl);
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
