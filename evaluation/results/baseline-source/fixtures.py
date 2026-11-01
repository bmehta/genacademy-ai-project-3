"""Synthetic data only. Runbooks are demonstration guidance, not company policy."""
EMPLOYEES = [
    {"id": "NS-1001", "name": "Maya Chen", "department": "Engineering", "email": "maya.chen@northstar.example"},
    {"id": "NS-1002", "name": "Jordan Patel", "department": "Design", "email": "jordan.patel@northstar.example"},
    {"id": "NS-1003", "name": "Alex Rivera", "department": "Operations", "email": "alex.rivera@northstar.example"},
]
RUNBOOKS = {
    "vpn": {"title": "VPN won't connect", "keywords": ["vpn", "remote connection"], "steps": [
        "Open a public website to confirm your internet works. Does it load?",
        "Disconnect the VPN, close the VPN app, then reopen it and reconnect. Use your usual sign-in flow; don't share any codes here. Does the VPN connect now?",
        "Restart your device when it is safe to do so, then try the VPN again. Did that restore your VPN connection?"], "example": "My VPN won't connect."},
    "account": {"title": "Account locked", "keywords": ["locked", "lockout", "password", "account"], "steps": [
        "Open the company's usual sign-in page and select the self-service account recovery option. Can you reach that page?",
        "Complete recovery privately using your registered recovery method. Never read your password or verification code aloud. Can you sign in now?",
        "Wait for any lockout period shown on the sign-in page, then try once more. Did access return?"], "example": "My employee account is locked."},
    "wifi": {"title": "Wi-Fi without internet", "keywords": ["wi-fi", "wifi", "internet", "wireless"], "steps": [
        "Check whether a second device on the same Wi-Fi can open a website. Is only your work device affected?",
        "Turn Wi-Fi off and back on, then reconnect to your usual network. Can you open a website now?",
        "Save your work and restart your device when safe. Does internet access work now?"], "example": "My Wi-Fi is connected but I have no internet."},
    "printer": {"title": "Printer offline", "keywords": ["printer", "print"], "steps": [
        "Check that the printer is powered on and your device is on the same office network. Are both connected?",
        "Select the correct printer and resume any paused print queue. Does a test page print now?",
        "Cancel only your own stuck print job and retry a test page. Did it print successfully?"], "example": "The office printer appears offline."},
    "microphone": {"title": "Meeting microphone", "keywords": ["microphone", "mic", "meeting", "audio", "mute"], "steps": [
        "Check that you are unmuted and the meeting app has your intended microphone selected. Is the correct device selected?",
        "Allow microphone access in browser settings for the meeting site, then rejoin. Can others hear you now?",
        "Close other apps using the microphone, then try the meeting's audio test. Does the test pick up your voice?"], "example": "My microphone isn't working in meetings."},
    "access": {"title": "Restricted software access", "keywords": ["access", "software", "license", "restricted", "install", "admin"], "steps": [], "example": "I need access to restricted analytics software for a customer report."},
}
