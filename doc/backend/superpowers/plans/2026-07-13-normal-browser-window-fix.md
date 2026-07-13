# Normal Browser Window Launcher Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Open Workhours in a normal isolated browser window without extension-install or sync reminders while preserving automatic server shutdown when that window closes.

**Architecture:** Keep the unique temporary browser profile because it gives the launcher an independently trackable browser process. Generate browser arguments in a pure PowerShell helper, replace app mode with a normal new window, and disable extensions and sync only inside the disposable profile.

**Tech Stack:** Windows PowerShell 5.1, Microsoft Edge or Google Chrome command-line flags, native PowerShell tests, CMD/Uvicorn launcher.

## Global Constraints

- Keep the unique temporary profile and the existing close-window-to-stop-server lifecycle.
- Open `http://127.0.0.1:8000` with `--new-window`; do not pass any `--app=` argument.
- Pass `--disable-extensions` and `--disable-sync` only to the disposable launcher profile.
- Preserve `--no-first-run`, `--no-default-browser-check`, and `--disable-background-mode`.
- Do not change the user's normal Edge/Chrome profile, extensions, account, bookmarks, sync, or global browser configuration.
- Do not change Poetry/npm behavior, proxy behavior, port ownership checks, server cleanup, or temporary-profile deletion boundaries.
- Do not add dependencies, a shutdown API, a heartbeat, or a persistent browser profile.
- Update README so the documented window behavior matches the implementation.

---

### Task 1: Replace browser app mode with an isolated normal window

**Files:**
- Modify: `scripts/tests/start-workhours.tests.ps1`
- Modify: `scripts/start-workhours.ps1`
- Modify: `README.md`

**Interfaces:**
- Consumes: the existing unique `$profileDir`, browser `Start-Process`, `Wait-Process`, and cleanup lifecycle.
- Produces: `Get-WorkhoursBrowserArguments([string]$ProfilePath) -> string[]`; the launcher passes this array directly to `Start-Process -ArgumentList`.

- [ ] **Step 1: Add a failing browser-argument test**

In `scripts/tests/start-workhours.tests.ps1`, add this block inside the existing main `try`:

```powershell
$argumentProfile = Join-Path (
    [System.IO.Path]::GetTempPath()
) ("worktime-statistics-browser-args-{0}" -f [guid]::NewGuid().ToString('N'))
$browserArguments = Get-WorkhoursBrowserArguments -ProfilePath $argumentProfile
Assert-True ($browserArguments -contains '--new-window') 'Normal-window flag is missing.'
Assert-True (
    $browserArguments -contains 'http://127.0.0.1:8000'
) 'Workhours URL is missing from browser arguments.'
Assert-True (
    $browserArguments -contains '--disable-extensions'
) 'Disposable browser extensions are not disabled.'
Assert-True (
    $browserArguments -contains '--disable-sync'
) 'Disposable browser sync is not disabled.'
Assert-True (
    -not @($browserArguments | Where-Object { $_ -like '--app=*' }).Count
) 'Browser arguments still contain app mode.'
Assert-True (
    @($browserArguments | Where-Object { $_ -like '--user-data-dir=*' }).Count -eq 1
) 'Exactly one disposable profile argument is required.'
```

- [ ] **Step 2: Run the native launcher test and verify RED**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\tests\start-workhours.tests.ps1
```

Expected: non-zero exit because `Get-WorkhoursBrowserArguments` is not defined.

- [ ] **Step 3: Add the pure argument helper and use it**

In `scripts/start-workhours.ps1`, add this function immediately after `Get-WorkhoursBrowserPath`:

```powershell
function Get-WorkhoursBrowserArguments {
    param([Parameter(Mandatory)][string]$ProfilePath)

    return @(
        '--new-window',
        'http://127.0.0.1:8000',
        "--user-data-dir=`"$ProfilePath`"",
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-background-mode',
        '--disable-extensions',
        '--disable-sync'
    )
}
```

Replace the inline `$browserArguments = @(...)` block in `Invoke-WorkhoursLauncher` with:

```powershell
$browserArguments = Get-WorkhoursBrowserArguments -ProfilePath $profileDir
```

Do not change browser PID waiting, Uvicorn ownership, cleanup, or profile creation.

- [ ] **Step 4: Update README wording**

In `README.md`, replace items 3 and 4 under `## Windows 一键启动` with:

```markdown
3. 服务健康后会打开一个普通的独立 Edge/Chrome 窗口。这个临时窗口不加载扩展或同步用户资料，因此不会反复出现扩展安装页或同步提醒；你平时使用的浏览器配置不会被修改。
4. 关闭这个专用普通窗口后，本次启动的 Uvicorn 服务会自动停止。
```

Keep the existing paragraph that explains port conflicts, missing tools, and process safety unchanged.

- [ ] **Step 5: Run focused GREEN checks**

Run:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts\tests\start-workhours.tests.ps1
powershell.exe -NoProfile -Command "[void][scriptblock]::Create((Get-Content -Raw 'scripts/start-workhours.ps1')); 'PowerShell syntax OK'"
```

Expected: unit tests print `PowerShell launcher unit tests passed.` and the parser prints `PowerShell syntax OK`.

- [ ] **Step 6: Run the real launcher and inspect the normal window**

Start `start-workhours.cmd` from the repository root. Verify all of the following before normally closing the dedicated window:

```text
/api/health returns status=ok
the visible main window is a normal Edge/Chrome window with address and tab bars
the selected tab displays 工时 · Workhours at http://127.0.0.1:8000
no Adblock Plus installation page is open
no sync reminder is shown
no extra first-run or welcome tab is open
the dedicated process command line contains --new-window, --disable-extensions, and --disable-sync
the dedicated process command line does not contain --app=
```

Close the dedicated browser with its normal window close action, then verify:

```text
the CMD wrapper exits with code 0
port 8000 has no listener
the disposable profile directory is removed
no process using that profile remains
all browser PIDs that existed before launch remain alive
```

If the default test database did not exist before the run, remove only the newly created `backend/data/workhours.db`, `workhours.db-wal`, and `workhours.db-shm` after confirming each absolute path stays under the repository `backend/data/` directory.

- [ ] **Step 7: Run full regression verification**

Run:

```powershell
poetry -C backend run pytest -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
git diff --check
git status --short
```

Expected: backend 78 passed with only the existing TestClient deprecation warning; frontend 3 files/10 tests passed; TypeScript/Vite build passed; `git diff --check` printed nothing; status lists only the three intended files.

- [ ] **Step 8: Commit**

```powershell
git add scripts/start-workhours.ps1 scripts/tests/start-workhours.tests.ps1 README.md
git commit -m "fix: open launcher in a normal browser window"
```

Expected: one focused commit and a clean tracked working tree.
