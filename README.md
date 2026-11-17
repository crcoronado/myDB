# myDB — hotkey quick-search for your CSV price lists

Press **Ctrl + Shift + S** anywhere on your Mac. Then:

1. **Choose the database.** Press `1`, `2`, … (or use the arrows and Enter).
2. **Type to filter.** The list updates as you type. Words can be in any order (`xgs wifi` finds "XGS-PON ONU … Wi-Fi 6").
3. **Pick the row.** Use ↑ / ↓ and Enter, or double-click.
4. **Choose what to copy.** `1` Part Number · `2` Price · `3` All info. The value goes to the clipboard and you paste it with ⌘V. You can also turn on auto-paste in Settings.

`Esc` always goes back one step.

Target: **macOS on Apple Silicon (M1/M2/M3/M4)**. It also runs on Windows and Linux.

## Install (macOS)

1. Install Python 3.11+ with Tk 8.6. Use **one** of these:
   - the [python.org macOS installer](https://www.python.org/downloads/macos/) ("universal2", includes Tk), or
   - Homebrew: `brew install python@3.13 python-tk@3.13`

   Do **not** use Apple's `/usr/bin/python3`. Its old Tk does not work well.
2. In Terminal, inside this folder:
   ```bash
   ./install_mac.sh
   ```
3. Start the app:
   ```bash
   ./run_mac.command
   ```
   You can also double-click `run_mac.command` in Finder.
4. **Grant permission.** The first time, macOS asks for **Accessibility** permission. Watching a global hotkey needs it, and so does auto-paste.
   - Go to System Settings → Privacy & Security → Accessibility.
   - Enable **Terminal** if you run the app from source, or **myDB** if you run the built app.
   - Restart myDB.

### Build a real `myDB.app` (recommended for daily use)

```bash
./build_mac_app.sh
```

1. Drag `dist/myDB.app` to Applications.
2. Grant it Accessibility permission.
3. Optional: add it to System Settings → General → **Login Items** so it starts with your Mac.

Note: the build is signed locally ("ad-hoc"). After each rebuild, macOS may ask for the Accessibility permission again. If the hotkey stops working, remove myDB from the Accessibility list and add it again.

## Configure your databases

Open myDB and go to **Settings**:

- **Add…** Choose a CSV file and give it a name, for example "Price list – simple" or "Price list – enhanced".
- **Part Number / Price column.** By default the app detects these automatically. It recognises headers such as `Part Number`, `P/N`, `SKU`, `Model`, `Número de parte`, `Código` and `Price`, `List Price`, `Cost`, `Precio`, `Costo`. You can also choose the exact column yourself.
- **Hotkey.** For example `<ctrl>+<shift>+s` or `<cmd>+<shift>+k`.
- **Auto-paste.** After you choose, myDB switches back to the app you were in and presses ⌘V for you.
- **"All info" format:**
  - `lines`: one `Header: value` per line, good for e-mail and chat.
  - `tsv`: pastes into Excel or Numbers as a header row plus a data row.
  - `json`

CSV handling:

- Separators: comma, semicolon, tab and `|` are detected automatically.
- Encodings: UTF-8 and Windows/Excel (cp1252), so accents work.
- Updates: if you change the CSV file, myDB reloads it the next time you search.
- **myDB never writes to your CSV files.** Your settings are saved in `~/Library/Application Support/myDB/config.json`.

## Project layout

| Path | What it is |
|---|---|
| `mydb/data.py` | CSV loading, column detection, search, output formats (no GUI) |
| `mydb/system.py` | macOS hotkey (NSEvent), focus switching, ⌘V paste; Windows/Linux fallbacks |
| `mydb/hotkey.py` | hotkey parsing; pynput listener for Windows/Linux |
| `mydb/app.py` | Tkinter windows: control panel, search popup, settings |
| `data/` | two sample databases (simple + enhanced) |
| `tests/` | unit tests: `python3 -m unittest discover -s tests` |

## Known limits

- On macOS the hotkey is **observed, not captured**. The app in front also receives Ctrl+Shift+S. Few Mac apps use Control+Shift+S, so this is rarely a problem.
- The list shows up to 500 matching rows (`max_results` in the config). The count of all matches is always shown below the list.
