# Installing myDB on your Mac (.dmg)

No Terminal and no Python needed.

## 1. Download the installer
1. Open the repository on GitHub and go to **Actions → Build macOS DMG**.
2. Open the newest run that has a green ✓.
3. Scroll down to **Artifacts** and click **myDB-macOS-dmg**. A `.zip` file downloads.
4. Double-click the zip. You get `myDB-<version>-arm64.dmg`.

If the repository has a **Release** (made by tagging a version, for example `v0.1.0`), the `.dmg` is also attached there.

## 2. Install
1. Double-click the `.dmg`.
2. Drag **myDB** onto the **Applications** folder.
3. Eject the disk image.

## 3. First launch (one time only)
The app is not signed with an Apple Developer ID, so macOS blocks it the first time:

1. Open **myDB** from Applications. macOS says it "cannot be opened" or "cannot verify the developer". Click **Done** / **Cancel**.
2. Go to **System Settings → Privacy & Security** and scroll down. Next to the message about myDB, click **Open Anyway**. Confirm with your password or Touch ID.
3. myDB starts. macOS then asks for **Accessibility** permission, which the Ctrl+Shift+S hotkey needs:
   - Open System Settings → Privacy & Security → **Accessibility**.
   - Switch **myDB** on.
4. Quit myDB (click the 🔍 icon in the menu bar → **Quit myDB**) and open it again. The hotkey now works.

myDB lives in the **menu bar** (🔍 icon, top right). It has no Dock icon and no window. Click the icon for **Search…**, **Settings…** and **Quit myDB**. After each copy the icon briefly shows ✓, and the menu shows what was copied.

Optional: add myDB to **System Settings → General → Login Items** so it starts with your Mac.

## Updating to a new version
1. Quit myDB (🔍 icon in the menu bar → **Quit myDB**).
2. Drag the new version into Applications and choose **Replace**.
3. Each build has a new local signature, so macOS may switch the Accessibility permission off. If the hotkey stops working:
   - Open Privacy & Security → Accessibility.
   - Select myDB and remove it with **–**.
   - Add it again with **+**, then reopen myDB.

Your databases and settings are not affected. They are stored in `~/Library/Application Support/myDB/config.json`.

## Building the .dmg yourself on a Mac (optional)
```bash
./build_dmg.sh
```
The result is `dist/myDB-<version>-arm64.dmg`.
