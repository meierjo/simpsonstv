"""Safe Wi-Fi request parsing and wpa_supplicant configuration updates."""

import hashlib
import os
from pathlib import Path
import re
import tempfile


ALLOWED_KEYS = ("country", "ssid", "password")
COUNTRY_RE = re.compile(r"^[A-Za-z]{2}$")
HEX_PSK_RE = re.compile(r"^[0-9A-Fa-f]{64}$")


class WifiRequest:
    def __init__(self, country, ssid, password):
        self.country = country
        self.ssid = ssid
        self.password = password


def parse_wifi_request(text):
    """Parse a strict three-key request without evaluating shell syntax."""
    values = {}
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        if not raw_line.strip():
            continue
        if "=" not in raw_line:
            raise ValueError("line %d must use key=value" % line_number)
        key, value = raw_line.split("=", 1)
        key = key.strip()
        if key not in ALLOWED_KEYS:
            raise ValueError("unknown key on line %d: %s" % (line_number, key))
        if key in values:
            raise ValueError("duplicate key on line %d: %s" % (line_number, key))
        values[key] = value

    missing = [key for key in ALLOWED_KEYS if key not in values]
    if missing:
        raise ValueError("missing required key(s): %s" % ", ".join(missing))

    country = values["country"].upper()
    ssid = values["ssid"]
    password = values["password"]
    if not COUNTRY_RE.match(country):
        raise ValueError("country must be a two-letter code")
    if not 1 <= len(ssid.encode("utf-8")) <= 32:
        raise ValueError("ssid must contain 1 to 32 UTF-8 bytes")
    _reject_controls("ssid", ssid)
    _reject_controls("password", password)
    password_bytes = len(password.encode("utf-8"))
    if not (8 <= password_bytes <= 63 or HEX_PSK_RE.match(password)):
        raise ValueError(
            "password must contain 8 to 63 UTF-8 bytes or a 64-digit PSK"
        )
    return WifiRequest(country, ssid, password)


def _reject_controls(label, value):
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError("%s cannot contain control characters" % label)


def _quote_wpa(value):
    return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')


def derive_psk(ssid, password):
    """Return a WPA PSK without retaining the plaintext passphrase."""
    if HEX_PSK_RE.match(password):
        return password.lower()
    return hashlib.pbkdf2_hmac(
        "sha1", password.encode("utf-8"), ssid.encode("utf-8"), 4096, 32
    ).hex()


def render_wpa_supplicant(request):
    return (
        "country=%s\n"
        "ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev\n"
        "update_config=1\n"
        "\n"
        "network={\n"
        "    ssid=%s\n"
        "    psk=%s\n"
        "}\n"
        % (
            request.country,
            _quote_wpa(request.ssid),
            derive_psk(request.ssid, request.password),
        )
    )


def atomic_write(path, text, mode=0o600):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=path.name + ".", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w") as output:
            output.write(text)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary_name, mode)
        os.replace(temporary_name, str(path))
        directory_fd = os.open(str(path.parent), os.O_RDONLY)
        try:
            try:
                os.fsync(directory_fd)
            except OSError:
                # Some FAT boot partitions cannot fsync a directory. The file
                # itself was still flushed before the atomic replacement.
                pass
        finally:
            os.close(directory_fd)
    except Exception:
        try:
            os.unlink(temporary_name)
        except OSError:
            pass
        raise


def import_wifi_request(request_path, config_path, backup_path=None, result_path=None):
    request_path = Path(request_path)
    config_path = Path(config_path)
    backup_path = Path(backup_path or (str(config_path) + ".simpsonstv-backup"))
    result_path = Path(
        result_path or (request_path.parent / "simpsonstv-wifi-result.txt")
    )

    request = parse_wifi_request(request_path.read_text())
    if config_path.exists() and not backup_path.exists():
        atomic_write(backup_path, config_path.read_text())

    atomic_write(config_path, render_wpa_supplicant(request))
    request_path.unlink()
    atomic_write(
        result_path,
        "status=success\ncountry=%s\nssid=%s\nmessage=Wi-Fi settings imported\n"
        % (request.country, request.ssid),
    )
    return request


def write_error_result(result_path, message):
    clean_message = " ".join(str(message).splitlines())
    atomic_write(
        result_path,
        "status=error\nmessage=%s\n" % clean_message,
    )
