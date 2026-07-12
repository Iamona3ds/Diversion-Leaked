This guide will walk you through the full process of configuring Fiddler to intercept HTTPS requests made by the Roblox client. You will install and convert Fiddler's certificate, update Roblox's trusted certificate store, and apply the correct ClientSettings to enable HTTP proxying.

### 1. Set Up Fiddler to Capture HTTPS Traffic

To begin capturing encrypted traffic, Fiddler must be configured to decrypt HTTPS connections.

* Open **Fiddler**.
* Navigate to the menu:
  **Tools > Options > HTTPS**.
* Enable both of the following checkboxes:

  * **Capture HTTPS CONNECTs**
  * **Decrypt HTTPS traffic**

This allows Fiddler to act as a man-in-the-middle and inspect the traffic between Roblox and its servers.

### 2. Export Fiddler's Root Certificate

To ensure that Roblox trusts Fiddler, you need to extract Fiddler's root certificate and install it into Roblox's list of trusted certificate authorities.

* In Fiddler, go to:
  **Tools > Options > HTTPS > Actions > Export Root Certificate to Desktop**
  File Name it will generate: `FiddlerRoot.cer`

### 3. Convert `.cer` to `.pem` Using `certutil`

Windows already includes `certutil`, so you don’t need to install OpenSSL.

1. Open **Command Prompt**.
2. Run this command

```cmd
certutil -encode "%USERPROFILE%\Desktop\FiddlerRoot.cer" "%USERPROFILE%\Desktop\FiddlerRoot.pem"
```

You will now have
```
FiddlerRoot.pem
```

### 4. Modify Roblox's SSL Trust Store

Now that you have the PEM certificate, you need to add it to Roblox's CA bundle so Roblox accepts Fiddler as a valid certificate issuer.

1. Locate your Roblox installation directory. This is typically found in:

### Default
```
%localappdata%\Roblox\Versions\
```
```
%SystemDrive%\Program Files\Roblox\Versions\
```
### Bloxstrap
```
%localappdata%\Bloxstrap\Versions\
```
### Fishstrap
```
%localappdata%\Fishstrap\Versions\
```

1. Open the version folder and navigate to the `ssl` subfolder.
2. Inside the `ssl` folder, locate the file named `cacert.pem`. This file contains all trusted certificates.
3. Open both the original `cacert.pem` and the `FiddlerRoot.pem` in a text editor (such as Notepad++ or VS Code).
4. Copy the **entire contents** of `FiddlerRoot.pem` and paste it at the **very end** of the `cacert.pem` file.
5. Save and close the `cacert.pem` file.

At this point, Roblox will trust Fiddler's certificate for encrypted connections.

### 5. Configure FastFlags to Use the Fiddler Proxy

Next, add these FastFlags to use Fiddler as its HTTP proxy.

```json
{
  "DFStringDebugPlayerHttpProxyUrl": "127.0.0.1:8888",
  "DFStringHttpCurlProxyHostAndPort": "127.0.0.1:8888",
  "DFFlagDebugEnableHttpProxy": "True",
  "DFStringHttpCurlProxyHostAndPortForExternalUrl": "127.0.0.1:8888"
}
```

These flags instruct Roblox to route all HTTP(S) requests through your local proxy (Fiddler), which listens on port `8888` by default.

### Notes

* **Fiddler must be running** before Roblox starts, or Roblox will fail to connect to its servers.
* Roblox updates may **replace** the `cacert.pem` file — you will need to **repeat step 4** after updates.
* If Roblox crashes on launch after adding the certificate:
  * Restore the original `cacert.pem` (keep a backup before editing).
  * Remove the proxy FastFlags and restart Roblox.
* Certificates expire — if Fiddler regenerates a new `FiddlerRoot.cer`, you must redo the conversion and merge steps.
* This method may stop working if Roblox changes its security mechanisms, so proceed with caution and update your tools as needed.
* Only merge certificates into Roblox’s trust store from **trusted sources** (never accept random PEMs from others).
* Remove the Proxy FastFlags when you are done intercepting traffic to restore Roblox's default security.
-# After you completed setup follow the next guide <#1385808279380426792>