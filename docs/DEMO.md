# Demo scenarios

Each scenario takes about a minute. To try GHOST without touching your real folders, create a test
folder (e.g. `Documents/ghost-test/in` and `Documents/ghost-test/out`) and use those instead of Downloads.

## 1. Sort Downloads by type (template)
1. **Smart Files → Start from a template → Images from Downloads → Pictures**.
2. GHOST asks to allow both folders → **Yes**.
3. Save → the preview lists every image that would move. Click **Apply**.
4. **Dashboard → Undo last run** puts everything back.

## 2. Teach by example: receipts
1. Put `Receipt Shop A.pdf`, `Receipt Shop B.pdf` and `photo.jpg` in a test folder.
2. **Teach Mode → Pick a folder → Start recording**.
3. Select both receipts → **Move selected to…** → choose `out/Receipts`.
4. **Stop and suggest a rule**. GHOST proposes *Move PDF "receipt" → Receipts* and explains why.
5. **Review & save…** → adjust if needed → preview → apply.

Tip: tick *Actually perform these actions* to really move the files while demonstrating (undoable).

## 3. Rename photos with a date
1. Teach Mode, rename `IMG 1.jpg` to `2026-11-11 IMG 1.jpg`.
2. GHOST detects the pattern `{date} {stem}{ext}`, so the date is generalised, not hard-coded.

## 4. Plain language (no AI model needed)
Ask GHOST: `Premjesti sve PDF-ove iz Preuzimanja u Dokumente` → review → save.
Try also: `copy images from Desktop to Pictures`, `move zip files into Documents`.

## 5. With a local model (optional)
Install Ollama, `ollama pull llama3.2:3b`, then **Settings → Local AI → enable → Test connection**.
Now freer requests work, e.g. *"preimenuj slike u preuzimanjima tako da ispred imena stoji datum"*.
Ask something unsafe, e.g. *"format c:"*. The model's answer is rejected and nothing happens.

## 6. Safety
- **Settings/Safety → Allow a folder…** and pick `C:\Windows` or your whole user folder: GHOST refuses.
- Make a rule with **Ask me before every action**. New files wait under *Safety Center → Waiting for your approval*.
- **Pause all** stops every automation immediately. The preview's Apply button is disabled while paused.
- A rule with the *Quarantine* action moves files to the quarantine. Undo restores them.
  Permanent deletion only happens via *Delete permanently…* after typing a confirmation word.

## 7. Quick Action
Create two rules with *Runs: Only when I run it*, then **Quick Actions → New** → tick both → choose a
folder to open → **Run…**. One preview for everything, then the folder opens.
