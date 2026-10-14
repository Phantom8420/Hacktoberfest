"""Windows toast for reminders, through PowerShell so there is nothing to install.
The text travels in an environment variable and is XML-escaped there, never pasted
into the script.
"""
import os
import subprocess

SCRIPT = r"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] > $null
$t = [Security.SecurityElement]::Escape($env:DEJA_TITLE)
$b = [Security.SecurityElement]::Escape($env:DEJA_BODY)
$x = New-Object Windows.Data.Xml.Dom.XmlDocument
$x.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$t</text><text>$b</text></binding></visual></toast>")
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show(
    [Windows.UI.Notifications.ToastNotification]::new($x))
"""


def toast(title, body):
    env = {**os.environ, "DEJA_TITLE": title, "DEJA_BODY": body}
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", SCRIPT], env=env,
                   capture_output=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
