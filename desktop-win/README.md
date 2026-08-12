# NoteTask Windows (Photino / .NET)

Portable `NoteTask.exe` — WebView to https://todo.baski.pro/, global Ctrl+Space, Startup shortcut.

## Build (from Linux or Windows)

```bash
export PATH="$HOME/.dotnet:$PATH"
cd desktop-win/NoteTaskWin
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true -o ./publish
```

Publish to site:

```bash
./scripts/publish-downloads.sh
```

Output served as `/downloads/NoteTask-Setup.exe`.
