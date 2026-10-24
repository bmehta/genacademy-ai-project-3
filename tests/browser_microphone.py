"""Browser capture regression: mock providers; never sends audio or keys externally."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
    page = browser.new_page(permissions=['microphone'])
    errors, uploads = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.route('**/api/config', lambda route: route.fulfill(json={'mode':'scripted','voice_ready':True,'employees':[], 'runbooks':{}}))
    page.route('**/api/tickets', lambda route: route.fulfill(json=[]))
    page.route('**/api/sessions', lambda route: route.fulfill(json={'id':'mic-test','closed':False,'outcome':'active','agent':'intake','messages':[], 'events':[]}))
    page.route('**/api/sessions/mic-test/end', lambda route: route.fulfill(json={}))
    def capture(route):
        payload = route.request.post_data_buffer
        assert b'filename="recording.webm"' in payload
        assert b'audio/webm;codecs=opus' in payload
        assert len(payload) > 1000
        uploads.append(len(payload))
        route.fulfill(status=422, json={'detail':'No speech was recognized. Check your microphone selection in Chrome.'})
    page.route('**/api/voice/transcribe',capture)
    page.goto('http://127.0.0.1:8000')
    page.locator('#audio-enabled').uncheck()
    page.locator('#start').click()
    page.locator('#record').click()
    page.get_by_role('button',name='Stop & send').wait_for()
    page.wait_for_timeout(700)
    assert page.locator('#microphone').count() == 0
    page.locator('#record').click()
    page.locator('#notice').get_by_text('No speech was recognized.',exact=False).wait_for()
    assert page.locator('#recording-preview').count() == 0
    assert page.locator('#message').is_enabled()
    assert len(uploads)==1 and not errors, errors
    browser.close()
    print('Microphone browser regression passed: capture, MIME metadata, simplified controls, empty-transcript recovery.')
