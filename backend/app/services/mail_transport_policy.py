"""The approved unencrypted exception is restricted to one internal endpoint."""

MAIL_TRANSPORT_MODES = ('ssl', 'starttls', 'internal')
INTERNAL_SMTP_HOST = '10.10.1.150'
INTERNAL_SMTP_PORT = 25


def transport_allowed(host, port, security):
    try:
        port = int(port)
    except (TypeError, ValueError):
        return False
    return (security in MAIL_TRANSPORT_MODES and 1 <= port <= 65535
            and (security != 'internal' or (host == INTERNAL_SMTP_HOST and port == INTERNAL_SMTP_PORT)))
