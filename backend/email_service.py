import os
import re
import ipaddress
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

# Managed provider endpoint, not an application API address.
EMAIL_BASE_URL = 'https://integrations.emergentagent.com'
_SHORTENERS = ('bit.ly', 'tinyurl.com', 't.co', 'is.gd', 'cutt.ly', 'goo.gl', 'rebrand.ly')
_CRED_ASK = ('reply with your password', 'reply with the code', 'send your password', 'cvv',
             'send us your password', 'enter your password below', 'confirm your card number',
             'your full card number', 'seed phrase', 'recovery phrase', 'verify your card',
             'social security number', 'confirm your bank details')
_HOSTISH = re.compile(r'\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})', re.I)


def _host_ok(host):
    if not host or 'xn--' in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith('.' + s) for s in _SHORTENERS)


def _same_site(shown, real):
    return shown == real or real.endswith('.' + shown) or shown.endswith('.' + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ('href', 'src') and v]
        if tag.lower() == 'a':
            self._href = dict((k.lower(), v) for k, v in attrs).get('href')
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._href is not None:
            self.anchors.append((self._href, ''.join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject, html):
    scan = _EmailScan(); scan.feed(html)
    if scan.tags & {'form', 'input', 'textarea', 'select'}:
        raise ValueError('No forms or input fields in email (G2)')
    body = f'{subject}\n{html}'.lower()
    for phrase in _CRED_ASK:
        if phrase in body:
            raise ValueError('Email asks the recipient for credentials (G2)')
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(('mailto:', 'tel:', 'cid:', '#')):
            continue
        if not low.startswith('https://'):
            raise ValueError('Email links must be absolute https (G3)')
        host = urlparse(low).hostname or ''
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError('Invalid email link (G3)')
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ''
        if not real:
            continue
        for match in _HOSTISH.finditer(text):
            if not _same_site(match.group(1).lower(), real):
                raise ValueError('Anchor host mismatch (G3)')


async def send_email(*, to, subject, html):
    """Internal only: recipient from booking record; subject/body from fixed template."""
    _assert_safe_email(subject, html)
    payload = {'to': [to], 'subject': subject, 'html': html,
               'from_name': os.environ['EMAIL_FROM_NAME']}
    if os.environ.get('EMAIL_REPLY_TO'):
        payload['contact_email'] = os.environ['EMAIL_REPLY_TO']
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(f'{EMAIL_BASE_URL}/api/v1/email/send',
            headers={'X-Email-Key': os.environ['EMERGENT_EMAIL_KEY']}, json=payload)
    response.raise_for_status()
    message_id = response.json().get('id')
    if not message_id:
        raise ValueError('Email provider did not acknowledge the message')
    return message_id