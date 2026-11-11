"""Builds a throw-away demo (fake Downloads/Documents with sample files), runs real rules on it
and saves screenshots of every page into docs/screenshots/. Touches nothing outside ./.demo.

    python tools/demo_screenshots.py [--lang hr|en] [--theme dark|light]
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lang", default="en")
    ap.add_argument("--theme", default="dark")
    ap.add_argument("--out", default=str(ROOT / "docs" / "screenshots"))
    ap.add_argument("--root", default=str(ROOT / ".demo"), help="where the throw-away demo folders go")
    args = ap.parse_args()

    demo = Path(args.root)
    shutil.rmtree(demo, ignore_errors=True)
    home = demo / "home"
    dl, docs, pics = home / "Downloads", home / "Documents", home / "Pictures"
    for d in (dl, docs, pics):
        d.mkdir(parents=True)
    for name in ["Invoice March.pdf", "Invoice April.pdf", "contract.docx", "holiday 1.jpg", "holiday 2.jpg",
                 "screenshot 2026-11-10.png", "setup-tool.exe", "notes.txt", "song.mp3", "big.zip"]:
        (dl / name).write_text("demo")
    os.environ["GHOST_AI_HOME"] = str(demo / "appdata")

    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    from ghost_ai.app import build_context
    from ghost_ai.domain.models import Action, ActionType, Conditions, Rule, Trigger
    from ghost_ai.engine.quick import QuickAction
    from ghost_ai.ui.main_window import NAV, MainWindow

    ctx = build_context()
    ctx.set_setting("language", args.lang)
    ctx.set_setting("theme", args.theme)
    ctx.set_setting("onboarded", True)
    ctx.known_folders = lambda: {"downloads": str(dl), "documents": str(docs), "pictures": str(pics),
                                 "desktop": str(home / "Desktop"), "music": str(home / "Music"),
                                 "videos": str(home / "Videos")}
    for f in (dl, docs, pics):
        ctx.service.add_folder(str(f))
    r1 = Rule(name="Invoices → Documents/Invoices", watch_dir=str(dl),
              conditions=Conditions(extensions=["pdf"], name_contains=["invoice"]),
              action=Action(ActionType.MOVE, target_dir=str(docs / "Invoices")))
    r2 = Rule(name="Photos → Pictures", watch_dir=str(dl), conditions=Conditions(extensions=["jpg", "png"]),
              action=Action(ActionType.MOVE, target_dir=str(pics), rename_template="{date} {stem}{ext}"))
    r3 = Rule(name="Old installers → quarantine", watch_dir=str(dl), conditions=Conditions(extensions=["exe"]),
              action=Action(ActionType.TRASH), trigger=Trigger.MANUAL, confirm_each=True)
    for r in (r1, r2, r3):
        ctx.service.save_rule(r)
    ctx.service.execute(ctx.service.preview_rules([r1, r2]))
    qa = QuickAction(name="Tidy Downloads", steps=[{"type": "run_rule", "rule_id": r3.id},
                                                   {"type": "open_folder", "path": str(docs)}])
    ctx.store.save_quick_action(qa.id, qa.to_dict())
    ctx.service.start_watching()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    win = MainWindow(ctx)
    win.resize(1280, 800)
    win.show()
    for key, _i, _c in NAV:
        win.go(key, animate=False)
        if key == "natural":
            page = win.pages[key]
            page.input.setPlainText("Premjesti sve PDF-ove iz Preuzimanja u Dokumente" if args.lang == "hr"
                                    else "Move all PDFs from Downloads to Documents")
            from ghost_ai.ai.natural import propose_rule
            page._show(propose_rule(page.input.toPlainText(), ctx.known_folders(), None))
        if key == "agent":
            from ghost_ai.agent.planner import builtin_plan
            ctx.set_setting("full_access", True)
            page = win.pages[key]
            page.refresh()
            page.input.setText("instaliraj 7zip" if args.lang == "hr" else "install 7zip")
            page._show_plan(builtin_plan(page.input.text(), is_windows=True))
            page.steps[0].status, page.steps[0].exit_code = "done", 0
            page.console.setPlainText('$ winget search "7zip" --accept-source-agreements\n'
                                      "Name    Id         Version  Match\n"
                                      "-----------------------------------------\n"
                                      "7-Zip   7zip.7zip  26.06    Moniker: 7zip\n")
            page._render()
        if key == "teach":
            from ghost_ai.teach.generalizer import DemoStep
            page = win.pages[key]
            (dl / "Receipt Store A.pdf").write_text("demo")
            (dl / "Receipt Store B.pdf").write_text("demo")
            page.folder = str(dl)
            page.folder_label.setText(str(dl))
            page._load_files()
            page.start()
            for n in ("Receipt Store A.pdf", "Receipt Store B.pdf"):
                step = DemoStep(ActionType.MOVE, str(dl / n), str(docs / "Receipts" / n))
                page.recorder.record(step)
                page.steps.addItem(f"Move: {n} → {docs / 'Receipts'}")
            page.stop()
        for _ in range(5):
            app.processEvents()
        path = out / f"{args.theme}-{args.lang}-{key}.png"
        win.grab().save(str(path))
        print(path)
    ctx.service.stop_watching()
    win.close()


if __name__ == "__main__":
    main()
