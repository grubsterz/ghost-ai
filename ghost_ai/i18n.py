"""Tiny HR/EN translation table. Keys are stable identifiers; missing keys fall back to English."""

from __future__ import annotations

_lang = "en"

T: dict[str, tuple[str, str]] = {
    # navigation
    "nav.dashboard": ("Dashboard", "Pregled"),
    "nav.files": ("Smart Files", "Pametne datoteke"),
    "nav.teach": ("Teach Mode", "Način učenja"),
    "nav.natural": ("Ask GHOST", "Pitaj GHOST"),
    "nav.quick": ("Quick Actions", "Brze radnje"),
    "nav.safety": ("Safety Center", "Sigurnost"),
    "nav.settings": ("Settings", "Postavke"),
    "nav.about": ("About", "O aplikaciji"),
    "tagline": ("Private automation. Runs on your computer.", "Privatna automatizacija. Radi na tvom računalu."),
    # common
    "ok": ("OK", "U redu"), "cancel": ("Cancel", "Odustani"), "save": ("Save", "Spremi"),
    "delete": ("Delete", "Obriši"), "edit": ("Edit", "Uredi"), "add": ("Add", "Dodaj"),
    "remove": ("Remove", "Ukloni"), "browse": ("Browse…", "Odaberi…"), "close": ("Close", "Zatvori"),
    "yes": ("Yes", "Da"), "no": ("No", "Ne"), "on": ("On", "Uključeno"), "off": ("Off", "Isključeno"),
    "run_now": ("Run now…", "Pokreni sad…"), "preview": ("Preview (dry-run)", "Pregled (bez promjena)"),
    "apply": ("Apply", "Primijeni"), "undo": ("Undo", "Poništi"), "undo_last": ("Undo last run", "Poništi zadnje"),
    "none_yet": ("Nothing yet.", "Još ništa."),
    # status
    "status.watching": ("Watching {n} folder(s)", "Prati {n} mapa"),
    "status.idle": ("Not watching - no active rules", "Ne prati ništa - nema aktivnih pravila"),
    "status.paused": ("All automations paused", "Sve automatizacije pauzirane"),
    "status.ai_ready": ("Local AI ready · {model}", "Lokalni AI spreman · {model}"),
    "status.ai_off": ("Local AI not running - built-in parser in use", "Lokalni AI ne radi - koristi se ugrađeni parser"),
    "status.ai_nomodel": ("Ollama running, model '{model}' not installed", "Ollama radi, model '{model}' nije instaliran"),
    # dashboard
    "dash.title": ("Good to see you", "Drago mi je što si tu"),
    "dash.rules_active": ("Active rules", "Aktivna pravila"),
    "dash.actions_24h": ("Actions · 24 h", "Radnje · 24 h"),
    "dash.actions_7d": ("Actions · 7 days", "Radnje · 7 dana"),
    "dash.undone": ("Undone", "Poništeno"),
    "dash.recent": ("Recent actions", "Nedavne radnje"),
    "dash.engine": ("Engine", "Pokretač"),
    "dash.ai": ("Local AI", "Lokalni AI"),
    "dash.pause_all": ("Pause all", "Pauziraj sve"),
    "dash.resume_all": ("Resume", "Nastavi"),
    "dash.empty": ("No rules yet. Start in Smart Files, teach GHOST by example, or just ask.",
                   "Još nema pravila. Kreni u Pametnim datotekama, pokaži GHOST-u primjer ili ga samo pitaj."),
    "dash.new_rule": ("New rule", "Novo pravilo"),
    "dash.teach": ("Teach by example", "Nauči na primjeru"),
    "dash.ask": ("Describe a task", "Opiši zadatak"),
    # rules / smart files
    "files.title": ("Smart Files", "Pametne datoteke"),
    "files.sub": ("Rules that sort, copy and rename files in folders you choose.",
                  "Pravila koja razvrstavaju, kopiraju i preimenuju datoteke u mapama koje odabereš."),
    "files.templates": ("Start from a template", "Kreni od predloška"),
    "rule.name": ("Name", "Naziv"), "rule.watch": ("Watch folder", "Mapa koju pratim"),
    "rule.when": ("When a file…", "Kad datoteka…"),
    "rule.exts": ("has extension", "ima nastavak"), "rule.exts_ph": ("pdf, docx, jpg", "pdf, docx, jpg"),
    "rule.contains": ("name contains", "naziv sadrži"), "rule.contains_ph": ("invoice, racun", "racun, invoice"),
    "rule.glob": ("name matches pattern", "naziv odgovara uzorku"), "rule.glob_ph": ("scan_*", "scan_*"),
    "rule.then": ("Then…", "Onda…"), "rule.action": ("Action", "Radnja"),
    "rule.target": ("Target folder", "Odredišna mapa"),
    "rule.template": ("New name", "Novi naziv"),
    "rule.template_help": ("Use {stem} {ext} {date} {time} {year} {month} {day}",
                           "Koristi {stem} {ext} {date} {time} {year} {month} {day}"),
    "rule.case": ("Letters", "Slova"), "rule.spaces": ("Spaces", "Razmaci"),
    "rule.trigger": ("Runs", "Pokreće se"),
    "trigger.watch": ("Automatically, when a new file arrives", "Automatski, kad stigne nova datoteka"),
    "trigger.manual": ("Only when I run it", "Samo kad ga ja pokrenem"),
    "rule.conflict": ("If the name is taken", "Ako naziv već postoji"),
    "conflict.rename": ("Keep both - add (1)", "Zadrži obje - dodaj (1)"),
    "conflict.skip": ("Skip the file", "Preskoči datoteku"),
    "rule.recursive": ("Include subfolders", "Uključi podmape"),
    "rule.confirm_each": ("Ask me before every action", "Pitaj me prije svake radnje"),
    "rule.enabled": ("Enabled", "Uključeno"),
    "rule.example": ("Example", "Primjer"),
    "rule.no_target": ("Pick a target folder.", "Odaberi odredišnu mapu."),
    "rule.no_condition": ("Add at least one condition.", "Dodaj barem jedan uvjet."),
    "case.keep": ("Keep", "Zadrži"), "case.lower": ("lowercase", "mala slova"), "case.upper": ("UPPERCASE", "VELIKA SLOVA"),
    "spaces.keep": ("Keep", "Zadrži"), "spaces.underscore": ("Replace with _", "Zamijeni s _"),
    "spaces.dash": ("Replace with -", "Zamijeni s -"),
    "action.move": ("Move", "Premjesti"), "action.copy": ("Copy", "Kopiraj"), "action.rename": ("Rename", "Preimenuj"),
    "action.trash": ("Quarantine (recoverable)", "Karantena (može se vratiti)"),
    "rule.editor_title": ("Rule", "Pravilo"),
    "rule.delete_q": ("Delete rule '{name}'? Files are not affected.", "Obrisati pravilo '{name}'? Datoteke ostaju netaknute."),
    "rule.summary_move": ("Move {what} from {src} to {dst}", "Premjesti {what} iz {src} u {dst}"),
    "rule.summary_copy": ("Copy {what} from {src} to {dst}", "Kopiraj {what} iz {src} u {dst}"),
    "rule.summary_rename": ("Rename {what} in {src} → {tpl}", "Preimenuj {what} u {src} → {tpl}"),
    "rule.summary_trash": ("Quarantine {what} in {src}", "Stavi u karantenu {what} u {src}"),
    "rule.what_any": ("files", "datoteke"),
    "rule.manual_badge": ("manual", "ručno"), "rule.ask_badge": ("asks first", "pita prije"),
    "rule.disabled_badge": ("off", "isključeno"),
    "rule.turn_off": ("Turn off", "Isključi"), "rule.turn_on": ("Turn on", "Uključi"),
    "folder.grant_q": ("GHOST AI needs access to:\n{folders}\n\nAllow GHOST to work in these folder(s)?",
                       "GHOST AI treba pristup:\n{folders}\n\nDopustiti GHOST-u rad u tim mapama?"),
    # preview dialog
    "pv.title": ("Review before anything changes", "Pregledaj prije nego se išta promijeni"),
    "pv.count": ("{n} file(s) will be changed, {s} skipped.", "Promijenit će se {n} datoteka, preskočeno {s}."),
    "pv.nothing": ("No matching files right now.", "Trenutno nema datoteka koje odgovaraju."),
    "pv.from": ("From", "Iz"), "pv.to": ("To", "U"), "pv.action": ("Action", "Radnja"), "pv.note": ("Note", "Napomena"),
    "pv.apply": ("Apply {n} change(s)", "Primijeni {n} promjena"),
    "note.renamed_conflict": ("name taken - kept both", "naziv zauzet - zadržane obje"),
    "note.name_conflict": ("name taken - skipped", "naziv zauzet - preskočeno"),
    "note.already_in_place": ("already in place", "već je na mjestu"),
    "done.summary": ("Done: {ok} changed, {bad} not changed. You can undo it.",
                     "Gotovo: promijenjeno {ok}, nepromijenjeno {bad}. Može se poništiti."),
    # teach
    "teach.title": ("Teach by example", "Nauči na primjeru"),
    "teach.sub": ("Show GHOST what you do with a few files. It suggests a rule - you check and approve it.\n"
                  "GHOST only sees what you do in this panel. It does not watch your screen or keyboard.",
                  "Pokaži GHOST-u što radiš s nekoliko datoteka. Predložit će pravilo - ti ga provjeriš i odobriš.\n"
                  "GHOST vidi samo ono što napraviš u ovom panelu. Ne prati ekran ni tipkovnicu."),
    "teach.pick": ("1 · Pick a folder", "1 · Odaberi mapu"),
    "teach.start": ("2 · Start recording", "2 · Pokreni snimanje"),
    "teach.stop": ("3 · Stop and suggest a rule", "3 · Zaustavi i predloži pravilo"),
    "teach.recording": ("● Recording your demonstration", "● Snimam tvoju demonstraciju"),
    "teach.move": ("Move selected to…", "Premjesti odabrano u…"),
    "teach.copy": ("Copy selected to…", "Kopiraj odabrano u…"),
    "teach.rename": ("Rename selected…", "Preimenuj odabrano…"),
    "teach.really": ("Actually perform these actions (undoable)", "Stvarno izvrši radnje (može se poništiti)"),
    "teach.steps": ("Demonstrated steps", "Pokazani koraci"),
    "teach.suggestions": ("Suggested rules", "Predložena pravila"),
    "teach.no_steps": ("Do at least one move, copy or rename first.", "Prvo napravi barem jedno premještanje, kopiranje ili preimenovanje."),
    "teach.confidence": ("confidence {p}%", "sigurnost {p}%"),
    "teach.review": ("Review & save…", "Pregledaj i spremi…"),
    "teach.rename_prompt": ("New name for {name}", "Novi naziv za {name}"),
    "teach.undo_step": ("Remove last step", "Ukloni zadnji korak"),
    "expl.examples": ("Based on {0} example(s)", "Na temelju {0} primjera"),
    "expl.common_text": ("All names contain “{0}”", "Svi nazivi sadrže “{0}”"),
    "expl.extensions": ("File types: {0}", "Vrste datoteka: {0}"),
    "expl.untouched_similar": ("{0} similar file(s) were left alone - check the conditions",
                               "{0} sličnih datoteka nisi dirao - provjeri uvjete"),
    "expl.rename_pattern": ("Name pattern: {0}", "Uzorak naziva: {0}"),
    "expl.rename_unclear": ("Rename pattern unclear - edit it", "Uzorak preimenovanja nije jasan - uredi ga"),
    "expl.no_condition": ("Could not find what the files have in common", "Nije jasno što datoteke imaju zajedničko"),
    "expl.single_example": ("Only one example - more examples give better rules",
                            "Samo jedan primjer - više primjera daje bolje pravilo"),
    # natural
    "nl.title": ("Describe what you want", "Opiši što želiš"),
    "nl.sub": ("Write or say it in Croatian or English. GHOST turns it into a rule you can check - it never runs commands.",
               "Napiši ili izgovori na hrvatskom ili engleskom. GHOST to pretvara u pravilo koje provjeriš - nikad ne pokreće naredbe."),
    "nl.placeholder": ("e.g. Move all PDFs from Downloads to Documents",
                       "npr. Premjesti sve PDF-ove iz Preuzimanja u Dokumente"),
    "nl.go": ("Suggest a rule", "Predloži pravilo"),
    "nl.thinking": ("Thinking locally…", "Razmišljam lokalno…"),
    "nl.provider_keywords": ("Understood by the built-in parser", "Razumio ugrađeni parser"),
    "nl.provider_ollama": ("Understood by local model ({model})", "Razumio lokalni model ({model})"),
    "nl.err.no_condition": ("I couldn't tell which files you mean. Mention a type (PDF, images…) or a word in the name.",
                            "Nije jasno koje datoteke misliš. Navedi vrstu (PDF, slike…) ili riječ iz naziva."),
    "nl.err.no_target": ("Where should the files go? Name a folder (Documents, Pictures, Desktop…).",
                         "Kamo da idu datoteke? Navedi mapu (Dokumenti, Slike, Radna površina…)."),
    "nl.err.generic": ("I couldn't turn that into a safe rule: {e}", "Ne mogu to pretvoriti u sigurno pravilo: {e}"),
    "nl.warn.assumed_downloads": ("No source folder mentioned - assumed Downloads.", "Izvorna mapa nije navedena - pretpostavljam Preuzimanja."),
    "nl.warn.ollama_failed": ("The local model's answer was rejected; used the built-in parser instead.",
                              "Odgovor lokalnog modela je odbijen; korišten je ugrađeni parser."),
    "nl.examples": ("Try:", "Probaj:"),
    "voice.start": ("🎙 Speak", "🎙 Govori"), "voice.stop": ("■ Stop recording", "■ Zaustavi snimanje"),
    "voice.recording": ("● Microphone is ON - recording", "● Mikrofon je UKLJUČEN - snimam"),
    "voice.transcribing": ("Transcribing locally…", "Pretvaram govor u tekst lokalno…"),
    "voice.unavailable": ("Voice input is optional. Install with: pip install \"ghost-ai[voice]\"",
                          "Glasovni unos je opcionalan. Instalacija: pip install \"ghost-ai[voice]\""),
    "voice.error": ("Microphone error: {e}", "Greška mikrofona: {e}"),
    # quick actions
    "qa.title": ("Quick Actions", "Brze radnje"),
    "qa.sub": ("One click runs several of your rules on the files already there, then opens folders you choose.",
               "Jedan klik pokreće više tvojih pravila na datotekama koje već postoje, pa otvara odabrane mape."),
    "qa.new": ("New quick action", "Nova brza radnja"),
    "qa.name": ("Name", "Naziv"), "qa.rules": ("Rules to run", "Pravila koja se pokreću"),
    "qa.open": ("Open folder afterwards (optional)", "Nakon toga otvori mapu (opcionalno)"),
    "qa.run": ("Run…", "Pokreni…"),
    "qa.empty": ("No quick actions yet.", "Još nema brzih radnji."),
    "qa.needs_rules": ("Create a rule first.", "Prvo napravi pravilo."),
    # safety
    "safety.title": ("Safety Center", "Sigurnosni centar"),
    "safety.promises": ("GHOST AI promises", "GHOST AI obećava"),
    "safety.p1": ("Works only in folders you allow.", "Radi samo u mapama koje dopustiš."),
    "safety.p2": ("Never deletes files - removed files go to a recoverable quarantine.",
                  "Nikad ne briše datoteke - uklonjene idu u karantenu iz koje se vraćaju."),
    "safety.p3": ("Never overwrites a file - a free name is used instead.", "Nikad ne prepisuje datoteku - koristi slobodan naziv."),
    "safety.p4": ("No telemetry, no cloud, no accounts. Everything stays on this computer.",
                  "Nema telemetrije, oblaka ni računa. Sve ostaje na ovom računalu."),
    "safety.p5": ("Never touches system folders, passwords, keys, tokens or browser data.",
                  "Nikad ne dira sistemske mape, lozinke, ključeve, tokene ni podatke preglednika."),
    "safety.p6": ("AI text is treated as untrusted and can only become a rule you review.",
                  "Tekst AI-ja je nepouzdan ulaz i može postati samo pravilo koje pregledaš."),
    "safety.folders": ("Allowed folders", "Dopuštene mape"),
    "safety.add_folder": ("Allow a folder…", "Dopusti mapu…"),
    "safety.approvals": ("Waiting for your approval", "Čeka tvoje odobrenje"),
    "safety.approve": ("Approve", "Odobri"), "safety.reject": ("Reject", "Odbij"),
    "safety.journal": ("Action log", "Dnevnik radnji"),
    "safety.undo_sel": ("Undo selected", "Poništi odabrano"),
    "safety.quarantine": ("Quarantine", "Karantena"),
    "safety.q_info": ("{n} file(s), {size}", "{n} datoteka, {size}"),
    "safety.q_open": ("Open quarantine folder", "Otvori mapu karantene"),
    "safety.q_empty": ("Delete permanently…", "Trajno obriši…"),
    "safety.q_confirm": ("This PERMANENTLY deletes {n} file(s) from quarantine. This cannot be undone.\n\nType DELETE to confirm.",
                         "Ovo TRAJNO briše {n} datoteka iz karantene. To se ne može poništiti.\n\nUpiši OBRISI za potvrdu."),
    "safety.q_word": ("DELETE", "OBRISI"),
    "safety.logs": ("Open log file", "Otvori log datoteku"),
    "safety.blocked": ("Blocked", "Blokirano"),
    "blocked.drive_root": ("A whole drive can't be allowed - pick a specific folder.", "Cijeli disk se ne može dopustiti - odaberi konkretnu mapu."),
    "blocked.home_root": ("Your whole home folder is too broad - pick a folder inside it.", "Cijela korisnička mapa je preširoka - odaberi mapu unutar nje."),
    "blocked.system_folder": ("System and app-data folders are protected.", "Sistemske mape i podaci aplikacija su zaštićeni."),
    "blocked.secret_folder": ("Folders with keys or credentials are protected.", "Mape s ključevima i pristupnim podacima su zaštićene."),
    "blocked.secret_file": ("Secret-looking file protected", "Zaštićena datoteka s tajnama"),
    "blocked.outside_allowed": ("Folder not allowed yet", "Mapa još nije dopuštena"),
    "status.done": ("done", "gotovo"), "status.dry_run": ("preview", "pregled"), "status.skipped": ("skipped", "preskočeno"),
    "status.failed": ("failed", "neuspjelo"), "status.blocked": ("blocked", "blokirano"), "status.undone": ("undone", "poništeno"),
    "col.time": ("Time", "Vrijeme"), "col.action": ("Action", "Radnja"), "col.file": ("File", "Datoteka"),
    "col.to": ("To", "Kamo"), "col.status": ("Status", "Stanje"), "col.rule": ("Rule", "Pravilo"),
    # settings
    "set.title": ("Settings", "Postavke"),
    "set.language": ("Language", "Jezik"), "set.theme": ("Theme", "Tema"),
    "theme.dark": ("Dark", "Tamna"), "theme.light": ("Light", "Svijetla"),
    "set.scale": ("Text size", "Veličina teksta"),
    "set.ai": ("Local AI (optional)", "Lokalni AI (opcionalno)"),
    "set.ai_enable": ("Use a local Ollama model for understanding requests", "Koristi lokalni Ollama model za razumijevanje zahtjeva"),
    "set.ai_model": ("Model", "Model"), "set.ai_test": ("Test connection", "Provjeri vezu"),
    "set.ai_help": ("Install Ollama from ollama.com, then run: ollama pull llama3.2:3b",
                    "Instaliraj Ollamu s ollama.com, pa pokreni: ollama pull llama3.2:3b"),
    "set.voice": ("Voice", "Glas"), "set.voice_model": ("Whisper model", "Whisper model"),
    "set.rules_io": ("Rules", "Pravila"), "set.export": ("Export rules…", "Izvezi pravila…"),
    "set.import": ("Import rules…", "Uvezi pravila…"),
    "set.imported": ("Imported {ok} rule(s). Rejected {bad}.", "Uvezeno {ok} pravila. Odbijeno {bad}."),
    "set.imported_disabled": ("Imported rules start switched off - review them first.",
                              "Uvezena pravila su isključena - prvo ih pregledaj."),
    "set.storage": ("Local storage", "Lokalna pohrana"), "set.open_data": ("Open data folder", "Otvori mapu s podacima"),
    "set.telemetry": ("Telemetry: none. GHOST AI never sends data anywhere.", "Telemetrija: nema. GHOST AI nikamo ne šalje podatke."),
    "set.restart_lang": ("Language changed.", "Jezik promijenjen."),
    "set.onboarding": ("Show welcome tour again", "Ponovno prikaži uvod"),
    # about
    "about.title": ("About GHOST AI", "O GHOST AI"),
    "about.text": ("A free, private, offline-first assistant that automates repetitive file chores.\n"
                   "Built with Python, PySide6, SQLite and watchdog. Optional: Ollama and faster-whisper.",
                   "Besplatan, privatan asistent koji radi bez interneta i automatizira dosadne poslove s datotekama.\n"
                   "Izrađen u Pythonu, PySide6, SQLite i watchdog. Opcionalno: Ollama i faster-whisper."),
    "about.website": ("Official website", "Službena stranica"),
    "about.source": ("Source code", "Izvorni kod"),
    "about.other": ("Other Projects", "Ostali projekti"),
    "about.rivoxo": ("RIVOXO Games - quick browser games with rules you get in seconds.",
                     "RIVOXO Games - brze igre u pregledniku s pravilima koja shvatiš u sekundi."),
    "about.links_note": ("Links can be changed in config.json in the data folder.",
                         "Poveznice se mijenjaju u config.json u mapi s podacima."),
    "about.version": ("Version {v}", "Verzija {v}"),
    # onboarding
    "ob.title": ("Welcome to GHOST AI", "Dobrodošao u GHOST AI"),
    "ob.p1": ("GHOST tidies your folders automatically - you decide the rules.",
              "GHOST automatski sređuje tvoje mape - ti odlučuješ o pravilima."),
    "ob.p2": ("Everything runs on this computer. No account, no cloud, no telemetry.",
              "Sve radi na ovom računalu. Bez računa, bez oblaka, bez telemetrije."),
    "ob.p3": ("Every change is shown first and can be undone.", "Svaka promjena se prvo pokaže i može se poništiti."),
    "ob.start": ("Pick a starter rule (you can skip):", "Odaberi početno pravilo (možeš preskočiti):"),
    "ob.skip": ("Skip", "Preskoči"), "ob.create": ("Create and preview", "Napravi i pregledaj"),
    "tpl.images": ("Images from Downloads → Pictures", "Slike iz Preuzimanja → Slike"),
    "tpl.docs": ("Documents from Downloads → Documents", "Dokumenti iz Preuzimanja → Dokumenti"),
    "tpl.installers": ("Installers in Downloads → quarantine", "Instalacije u Preuzimanjima → karantena"),
    "tpl.screenshots": ("Screenshots on Desktop → Pictures/Screenshots", "Snimke zaslona s radne površine → Slike/Screenshots"),
    "tpl.archives": ("Archives from Downloads → Documents/Archives", "Arhive iz Preuzimanja → Dokumenti/Archives"),
}


def set_language(lang: str) -> None:
    global _lang
    _lang = "hr" if lang == "hr" else "en"


def language() -> str:
    return _lang


def tr(key: str, **kw: object) -> str:
    pair = T.get(key)
    if pair is None:
        text = key
    else:
        text = pair[1] if _lang == "hr" else pair[0]
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError):
            return text
    return text


def explain(item: str) -> str:
    """Render a generalizer explanation key like 'common_text:invoice'."""
    key, _, arg = item.partition(":")
    pair = T.get(f"expl.{key}")
    if not pair:
        return item
    text = pair[1] if _lang == "hr" else pair[0]
    return text.replace("{0}", arg)
