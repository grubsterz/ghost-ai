"""Built-in desktop recipes (no model needed): open links/apps/folders/terminal, start Steam games,
close apps, web/YouTube search, lock/shut down. They only *produce* commands; the UI runs them on click."""

from __future__ import annotations

import os
import re
import urllib.parse

from ..ai.natural import FOLDER_WORDS, standard_folders
from ..i18n import tr
from .commands import CommandStep

_SAFE_NAME = re.compile(r"^[\w .+\-]{1,60}$")
_URL = re.compile(r"(https?://[A-Za-z0-9\-._~:/?#\[\]@!$&()*+,;=%]+|(?:www\.)?[a-z0-9\-]+\.(?:com|hr|net|org|io|dev|"
                  r"app|eu|de|tv|gg|co|me|ai)(?:/[A-Za-z0-9\-._~:/?#\[\]@!$&()*+,;=%]*)?)", re.I)

# spoken name -> (Windows process name, macOS app name, name to search in the Start menu)
APP_ALIASES: dict[str, tuple[str, str, str]] = {
    "chrome": ("chrome", "Google Chrome", "Google Chrome"),
    "google chrome": ("chrome", "Google Chrome", "Google Chrome"),
    "edge": ("msedge", "Microsoft Edge", "Microsoft Edge"),
    "firefox": ("firefox", "Firefox", "Firefox"),
    "word": ("winword", "Microsoft Word", "Word"),
    "excel": ("excel", "Microsoft Excel", "Excel"),
    "powerpoint": ("powerpnt", "Microsoft PowerPoint", "PowerPoint"),
    "spotify": ("spotify", "Spotify", "Spotify"),
    "discord": ("discord", "Discord", "Discord"),
    "steam": ("steam", "Steam", "Steam"),
    "notepad": ("notepad", "TextEdit", "Notepad"),
    "biljeznica": ("notepad", "TextEdit", "Notepad"),
    "kalkulator": ("CalculatorApp", "Calculator", "Calculator"),
    "calculator": ("CalculatorApp", "Calculator", "Calculator"),
    "vs code": ("code", "Visual Studio Code", "Visual Studio Code"),
    "vscode": ("code", "Visual Studio Code", "Visual Studio Code"),
    "visual studio code": ("code", "Visual Studio Code", "Visual Studio Code"),
    "whatsapp": ("WhatsApp", "WhatsApp", "WhatsApp"),
    "teams": ("ms-teams", "Microsoft Teams", "Teams"),
    "outlook": ("olk", "Microsoft Outlook", "Outlook"),
    "blender": ("blender", "Blender", "Blender"),
    "obs": ("obs64", "OBS", "OBS Studio"),
}

# Never closed by "close X" even if the name matches.
PROTECTED = "'explorer','csrss','winlogon','lsass','services','svchost','dwm','smss','wininit','System','GHOST AI'"


def _ps(s: str) -> str:
    """PowerShell single-quoted literal."""
    return "'" + s.replace("'", "''") + "'"


def _sh(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def _name(raw: str) -> str | None:
    n = raw.strip().strip("\"'„“”.!?").strip()
    n = re.sub(r"^(program|aplikaciju|aplikacija|app|igru|igricu|igrica|game|the)\s+", "", n)
    return n if _SAFE_NAME.match(n) else None


def _url_from(raw: str) -> str | None:
    m = _URL.search(raw)
    if not m:
        return None
    url = m.group(1).rstrip(".,;)")
    if not url.lower().startswith("http"):
        url = "https://" + url
    return url


def _open_url(url: str, win: bool, chrome: bool) -> str:
    if win:
        return f"Start-Process chrome {_ps(url)}" if chrome else f"Start-Process {_ps(url)}"
    return f"open -a 'Google Chrome' {_sh(url)}" if chrome else f"open {_sh(url)}"


def _folder_from(t: str) -> str | None:
    folders = standard_folders()
    for key, words in FOLDER_WORDS.items():
        if any(w in t for w in words) or key in t:
            return folders.get(key)
    return None


def _open_app(name: str, win: bool) -> str:
    alias = APP_ALIASES.get(name.lower())
    if win:
        # Start-menu names are localized (e.g. "Kalkulator" on Croatian Windows) - try English and spoken names.
        queries = list(dict.fromkeys([alias[2], name] if alias else [name]))
        qs = ",".join(_ps(q) for q in queries)
        return ("$qs=@(" + qs + "); $all=(New-Object -ComObject Shell.Application).NameSpace('shell:AppsFolder')."
                "Items(); $a=$null; foreach ($q in $qs) { $a=$all | Where-Object { $_.Name -like \"*$q*\" } | "
                "Select-Object -First 1; if ($a) { break } }; "
                "if ($a) { Start-Process ('shell:AppsFolder\\' + $a.Path); 'Started: ' + $a.Name } "
                "else { Start-Process $qs[0] }")
    return f"open -a {_sh(alias[1] if alias else name)}"


def _close_app(name: str, win: bool) -> str:
    alias = APP_ALIASES.get(name.lower())
    if win:
        proc = alias[0] if alias else name
        return ("$q=" + _ps(proc) + "; $s=(Get-Process -Id $PID).SessionId; "
                "$p=Get-Process | Where-Object { $_.SessionId -eq $s -and $_.ProcessName -like \"*$q*\" -and "
                f"$_.ProcessName -notin @({PROTECTED}) }}; "
                "if (-not $p) { 'Not running: ' + $q } else { "
                "$p | ForEach-Object { [void]$_.CloseMainWindow() }; Start-Sleep 3; "
                "$left=$p | Where-Object { -not $_.HasExited }; "
                "'Closed: ' + (($p | Select-Object -ExpandProperty ProcessName -Unique) -join ', '); "
                "if ($left) { 'Still open (force with: Stop-Process -Id ' + (($left.Id) -join ',') + ' -Force)' } }")
    return f"osascript -e {_sh('quit app \"' + (alias[1] if alias else name) + '\"')}"


def _steam_game(name: str, win: bool) -> str:
    if win:
        return ("$q=" + _ps(name) + "; $root=(Get-ItemProperty 'HKCU:\\Software\\Valve\\Steam' -ErrorAction "
                "SilentlyContinue).SteamPath; if (-not $root) { 'Steam is not installed'; return }; "
                "$libs=@(\"$root/steamapps\"); $vdf=\"$root/steamapps/libraryfolders.vdf\"; "
                "if (Test-Path $vdf) { $libs += (Select-String -Path $vdf -Pattern '\"path\"\\s+\"(.+)\"').Matches | "
                "ForEach-Object { ($_.Groups[1].Value -replace '\\\\\\\\','\\') + '\\steamapps' } }; "
                "$m=$libs | Where-Object { Test-Path $_ } | ForEach-Object { Get-ChildItem $_ -Filter 'appmanifest_*.acf' } | "
                "ForEach-Object { $t=Get-Content $_.FullName -Raw; if ($t -match '\"name\"\\s+\"([^\"]+)\"') { "
                "[pscustomobject]@{ Id=($_.BaseName -replace 'appmanifest_',''); Name=$Matches[1] } } } | "
                "Where-Object { $_.Name -like \"*$q*\" } | Select-Object -First 1; "
                "if ($m) { Start-Process \"steam://rungameid/$($m.Id)\"; 'Starting: ' + $m.Name } "
                "else { 'No installed Steam game matches: ' + $q }")
    return ("f=$(grep -il " + _sh('"name".*' + name) + " \"$HOME/Library/Application Support/Steam/steamapps/\""
            "appmanifest_*.acf 2>/dev/null | head -1); id=$(basename \"$f\" .acf | sed 's/appmanifest_//'); "
            "[ -n \"$f\" ] && open \"steam://rungameid/$id\" && echo \"Starting $id\" || "
            "echo " + _sh("No installed Steam game matches: " + name))


def desktop_plan(raw: str, t: str, win: bool) -> list[CommandStep] | None:
    """`raw` = original text, `t` = folded lowercase text. Returns steps or None."""
    lead = r"^(?:molim te\s+|please\s+|mozes li\s+|can you\s+)?"

    # power / lock
    if re.search(lead + r"(?:ugasi|iskljuci|shut ?down|turn off)\s+(?:racunalo|kompjuter|komp|pc|computer)\b", t):
        cmd = "shutdown /s /t 60" if win else "osascript -e 'tell app \"System Events\" to shut down'"
        return [CommandStep(cmd, tr("desk.shutdown"))]
    if re.search(lead + r"(?:restartaj|ponovno pokreni|restart|reboot)\s+(?:racunalo|kompjuter|komp|pc|computer)\b", t):
        cmd = "shutdown /r /t 60" if win else "osascript -e 'tell app \"System Events\" to restart'"
        return [CommandStep(cmd, tr("desk.restart"))]
    if re.search(r"\b(zakljucaj|lock)\s+(?:racunalo|ekran|zaslon|pc|computer|screen)\b", t):
        cmd = "rundll32.exe user32.dll,LockWorkStation" if win else "pmset displaysleepnow"
        return [CommandStep(cmd, tr("desk.lock"))]
    if re.search(r"\b(otkazi gasenje|cancel shutdown)\b", t):
        return [CommandStep("shutdown /a" if win else "sudo killall shutdown", tr("desk.cancel_shutdown"))]

    # web search / YouTube
    m = re.match(lead + r"(?:pusti|play|pronadi|nadi|trazi)?\s*(?:na\s+)?(?:youtube\w*|yt)\s+(.+)$", t) or \
        re.match(lead + r"(?:pusti|play)\s+(.+?)\s+(?:na|on)\s+youtube\w*$", t)
    if m:
        q = m.group(1).strip()
        url = "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)
        return [CommandStep(_open_url(url, win, "chrome" in t), tr("desk.youtube", q=q))]
    m = re.match(lead + r"(?:pretrazi|potrazi|guglaj|googlaj|google|search(?: for)?)\s+(?:na googleu\s+|on google\s+)?(.+)$",
                 t)
    if m:
        q = m.group(1).strip()
        url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(q)
        return [CommandStep(_open_url(url, win, "chrome" in t), tr("desk.google", q=q))]

    verb_open = r"(?:otvori|pokreni|upali|startaj|open|launch|start|run)"
    verb_close = r"(?:zatvori|ugasi|iskljuci|close|quit|exit|kill)"

    # links
    if re.match(lead + verb_open, t) or re.match(r"^(?:idi na|go to)\b", t):
        url = _url_from(raw)
        if url:
            return [CommandStep(_open_url(url, win, "chrome" in t), tr("desk.open_url", url=url))]

    # terminal
    if re.match(lead + verb_open + r"\s+(?:novi\s+|new\s+)?(?:terminal|konzolu|powershell|cmd|command prompt)\b", t):
        cmd = ("if (Get-Command wt -ErrorAction SilentlyContinue) { Start-Process wt } else { Start-Process powershell }"
               if win else "open -a Terminal")
        return [CommandStep(cmd, tr("desk.terminal"))]

    # folders
    m = re.match(lead + verb_open + r"\s+(?:mapu|folder|direktorij)\s+(.+)$", t) or \
        re.match(lead + verb_open + r"\s+(preuzimanja|downloads|dokumente|documents|radnu povrsinu|desktop|slike|pictures)$", t)
    if m:
        folder = _folder_from(m.group(1)) or ({"slike": standard_folders()["pictures"],
                                               "pictures": standard_folders()["pictures"]}.get(m.group(1).strip()))
        if folder:
            cmd = f"Start-Process explorer {_ps(folder)}" if win else f"open {_sh(folder)}"
            return [CommandStep(cmd, tr("desk.open_folder", folder=os.path.basename(folder)))]

    # Steam games
    m = re.match(lead + r"(?:pokreni|upali|otvori|startaj|igraj|zaigraj|launch|start|play|open)\s+"
                 r"(?:steam\s+)?(?:igru|igricu|igrica|game)\s+(.+)$", t)
    if m and (name := _name(m.group(1))):
        return [CommandStep(_steam_game(name, win), tr("desk.game", name=name))]

    # close apps
    m = re.match(lead + verb_close + r"\s+(.+)$", t)
    if m and (name := _name(m.group(1))):
        return [CommandStep(_close_app(name, win), tr("desk.close", name=name))]

    # open apps
    m = re.match(lead + verb_open + r"\s+(.+)$", t)
    if m and (name := _name(m.group(1))):
        return [CommandStep(_open_app(name, win), tr("desk.open_app", name=name))]
    return None
