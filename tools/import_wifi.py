#!/usr/bin/env python3
"""Import Simpsons TV Wi-Fi credentials from the SD card boot partition."""

import argparse
from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPOSITORY_ROOT))

from tv.wifi import import_wifi_request, write_error_result  # noqa: E402


DEFAULT_REQUESTS = (
    Path("/boot/simpsonstv-wifi.txt"),
    Path("/boot/firmware/simpsonstv-wifi.txt"),
)
DEFAULT_CONFIG = Path("/etc/wpa_supplicant/wpa_supplicant.conf")


def find_request(paths):
    return next((path for path in paths if path.is_file()), None)


def run(args):
    request_paths = (Path(args.request),) if args.request else DEFAULT_REQUESTS
    request_path = find_request(request_paths)
    if request_path is None:
        print("No Simpsons TV Wi-Fi request found; leaving network unchanged")
        return 0

    result_path = (
        Path(args.result)
        if args.result
        else request_path.parent / "simpsonstv-wifi-result.txt"
    )
    try:
        request = import_wifi_request(
            request_path,
            Path(args.config),
            backup_path=Path(args.backup) if args.backup else None,
            result_path=result_path,
        )
    except (OSError, ValueError) as error:
        try:
            write_error_result(result_path, error)
        except OSError:
            pass
        print("Wi-Fi import failed: %s" % error, file=sys.stderr)
        return 1

    print("Wi-Fi settings imported for SSID %s" % request.ssid)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", help="request file (default: boot partition)")
    parser.add_argument(
        "--config", default=str(DEFAULT_CONFIG), help="wpa_supplicant file"
    )
    parser.add_argument("--backup", help="one-time recovery backup path")
    parser.add_argument("--result", help="redacted result file path")
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
