============================================================
           Roblox Fiddler Intercepting Guide
============================================================

This guide will walk you through the full process of configuring
Fiddler to intercept HTTPS requests made by the Roblox client.
You will install and convert Fiddler's certificate, update Roblox's
trusted certificate store, and apply the correct ClientSettings to
enable HTTP proxying.

Run install.bat to install all requirements for Python

------------------------------------------------------------
1. Set Up Fiddler to Capture HTTPS Traffic
------------------------------------------------------------

To begin capturing encrypted traffic, Fiddler must be configured
to decrypt HTTPS connections.

1. Open Fiddler.
2. Go to:
       Tools > Options > HTTPS
3. Enable both:
       - Capture HTTPS CONNECTs
       - Decrypt HTTPS traffic

This allows Fiddler to act as a man-in-the-middle and inspect
traffic between Roblox and its servers.

------------------------------------------------------------
2. Export Fiddler's Root Certificate
------------------------------------------------------------

To ensure Roblox trusts Fiddler, export Fiddler's root certificate.

1. In Fiddler, go to:
       Tools > Options > HTTPS > Actions > Export Root Certificate to Desktop
2. This creates:
       FiddlerRoot.cer

------------------------------------------------------------
3. Convert .cer to .pem Using certutil
------------------------------------------------------------

Windows includes certutil, so you do not need to install OpenSSL.

1. Open Command Prompt.
2. Run:
       certutil -encode "%USERPROFILE%\Desktop\FiddlerRoot.cer" "%USERPROFILE%\Desktop\FiddlerRoot.pem"

This creates:
       FiddlerRoot.pem

------------------------------------------------------------
4. Modify Roblox's SSL Trust Store
------------------------------------------------------------

Add the PEM certificate to Roblox's CA bundle so Roblox accepts
Fiddler as a valid certificate issuer.

Roblox installation paths:

Default:
    %localappdata%\Roblox\Versions\
    %SystemDrive%\Program Files\Roblox\Versions\
Bloxstrap:
    %localappdata%\Bloxstrap\Versions\
Fishstrap:
    %localappdata%\Fishstrap\Versions\

Steps:
1. Open the version folder and navigate to:
       ssl
2. Find:
       cacert.pem
3. Open both:
       cacert.pem
       FiddlerRoot.pem
   in a text editor (Notepad++, VS Code, etc.).
4. Copy the entire contents of FiddlerRoot.pem and paste it at the
   very end of cacert.pem.
5. Save and close cacert.pem.

At this point, Roblox will trust Fiddler's certificate.

------------------------------------------------------------
5. Configure FastFlags to Use the Fiddler Proxy
------------------------------------------------------------

Add these FastFlags to route Roblox traffic through Fiddler:

{
  "DFStringDebugPlayerHttpProxyUrl": "127.0.0.1:8888",
  "DFStringHttpCurlProxyHostAndPort": "127.0.0.1:8888",
  "DFFlagDebugEnableHttpProxy": "True",
  "DFStringHttpCurlProxyHostAndPortForExternalUrl": "127.0.0.1:8888"
}

Fiddler listens on port 8888 by default.

============================================================
                 Flag Browser Usage Guide
============================================================

------------------------------------------------------------
1. Launch
------------------------------------------------------------

Double-click main.pyw to launch the Flag Browser.

------------------------------------------------------------
2. Create a New JSON File
------------------------------------------------------------

In the same folder:
    1. Right-click → New > Text Document.
    2. Rename it to something like playboicarti.json (name does not matter).
    3. Make sure the file is completely empty (no spaces or text).

------------------------------------------------------------
3. Use the JSON in Flag Browser
------------------------------------------------------------

In the Flag Browser:
    1. Go to the Settings tab.
    2. Click Select File.
    3. Choose the new .json file you created.

Tip: You can change the file anytime to use a different flag set.

------------------------------------------------------------
4. Set Up Fiddler Autoresponder
------------------------------------------------------------

1. Open Fiddler Classic.
2. Go to the AutoResponder tab.
3. Enable "Enable rules".
4. Enable "Unmatched requests passthrough".

------------------------------------------------------------
5. Add Fiddler Rules
------------------------------------------------------------

1. Click Add Rule.
2. In the top box paste this URL:
   https://clientsettingscdn.roblox.com/v2/settings-compressed/application/
3. In the bottom box paste the full path to your .json file. Example:
   C:\Users\YourName\Downloads\FlagBrowser\playboicarti.json
4. This makes Roblox load your custom JSON instead of the default settings.

------------------------------------------------------------
8. Instant Reloading (Required)
------------------------------------------------------------

To make Roblox apply changes instantly without restarting, add this
to your JSON file:

{
    "DFIntSecondsBetweenDynamicVariableReloading": "1"
}

This tells Roblox to check for flag changes every 1 second.

------------------------------------------------------------
Notes
------------------------------------------------------------

- Fiddler must be running before Roblox starts or Roblox will fail
  to connect.
- Roblox updates may replace cacert.pem — repeat Step 4 after updates.
- If Roblox crashes after adding the certificate:
    * Restore the original cacert.pem (keep a backup before editing).
    * Remove the proxy FastFlags and restart Roblox.
- Certificates expire — if Fiddler generates a new FiddlerRoot.cer,
  redo the conversion and merge steps.
- This method may stop working if Roblox changes its security
  mechanisms.
- Only merge certificates from trusted sources.
- Remove Proxy FastFlags when done intercepting traffic.
------------------------------------------------------------
            Flag Browser - imgui.cc - Version 1.8.0
------------------------------------------------------------
