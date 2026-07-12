# YOU MUST HAVE COMPLETED <#1379277464840306721> BEFORE PROCEEDING

## PROCEED TO STEP 3
-# If you want the source code ask me.

### Zip Password
```
imgui.cc_imguiX_1392782528321945681_7zQw9LkPx83VmNa2R1k7O8NKm9HsTuYeHbGtDcBjWcRf
```
~~1. **Run the Installer**
   * After downloading and extracting the folder, double-click `install.bat`.
   * This will install all required Python libraries.
   * Once it says **“All requirements installed successfully”**, you can now run the python script.

2. **Launch**
   * Double-click `main.pyw` to launch the Flag Browser.~~

3. **Create a new JSON file**
   * In the folder, right-click and select **New > Text Document**.
   * Rename the file to something like `playboicarti.json` any name will work.
   * Make sure the file is completely empty.

4. **Use the JSON for Flag Browser**
   * In the Flag Browser, go to the **Settings** tab.
   * Select File
-# You select the new JSON you made

5. **Set Up Fiddler Autoresponder**
   * Open **Fiddler Classic**.
   * Go to the **AutoResponder** tab.
   * ✅ Enable **"Enable rules"**.
   * ✅ Enable **"Unmatched requests passthrough"**.

6. **Fiddler Rules**
   * Click **“Add Rule”**.
   * In the **top box** paste this URL:
     ```
     https://clientsettingscdn.roblox.com/v2/settings-compressed/application/
     ```
   * In the **bottom box** paste the **full path** to your `.json` file. Example:
     ```
     C:\Users\YourName\Downloads\FlagBrowser\playboicarti.json
     ```
7. **Instant Reloading**
```json
{
    "DFIntSecondsBetweenDynamicVariableReloading": "1"
}
```

-# If you can't run the python script ask anyone here for the binary