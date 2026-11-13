#!/usr/bin/env python3
"""Serve a local commercial review UI that saves manifest approvals."""

import argparse
from html import escape
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, quote, unquote, urlparse
import webbrowser


def manifest_paths(root):
    return tuple(sorted((Path(root).resolve() / "manifests").glob("*.json")))


def load_manifest(path):
    with Path(path).open() as manifest_file:
        manifest = json.load(manifest_file)
    if not isinstance(manifest.get("clips"), list):
        raise ValueError("Invalid clips in %s" % path)
    return manifest


def save_selections(path, selected_sequences):
    """Atomically save approved sequence numbers for one manifest."""
    path = Path(path)
    manifest = load_manifest(path)
    selected = {int(sequence) for sequence in selected_sequences}
    for clip in manifest["clips"]:
        clip["approved"] = int(clip["sequence"]) in selected
    manifest["status"] = (
        "approved" if all(clip["approved"] for clip in manifest["clips"]) else "needs-review"
    )
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    temporary_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    os.replace(str(temporary_path), str(path))
    return sum(bool(clip["approved"]) for clip in manifest["clips"])


def reset_conservative(root):
    """Keep normal commercials and confirmed bumpers; uncheck candidates."""
    manifest_count = 0
    approved_count = 0
    for path in manifest_paths(root):
        manifest = load_manifest(path)
        selected = [
            clip["sequence"]
            for clip in manifest["clips"]
            if clip.get("kind") in ("commercial", "sponsor-bumper")
        ]
        approved_count += save_selections(path, selected)
        manifest_count += 1
    if not manifest_count:
        raise ValueError("No commercial manifests found below %s" % root)
    return manifest_count, approved_count


class ReviewHandler(SimpleHTTPRequestHandler):
    root = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._send_html(render_index(self.root))
        if parsed.path.startswith("/review/"):
            path = self._manifest_path(unquote(parsed.path[len("/review/") :]))
            if path is None:
                return self.send_error(404)
            return self._send_html(render_review(self.root, path))
        if parsed.path.startswith("/media/"):
            return self._send_media(unquote(parsed.path[len("/media/") :]))
        return self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/save/"):
            return self.send_error(404)
        path = self._manifest_path(unquote(parsed.path[len("/save/") :]))
        if path is None:
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", "0"))
        fields = parse_qs(self.rfile.read(length).decode("utf-8"))
        try:
            save_selections(path, fields.get("keep", []))
        except (OSError, ValueError, KeyError) as error:
            return self.send_error(400, str(error))
        self.send_response(303)
        self.send_header("Location", "/review/%s?saved=1" % quote(path.name))
        self.end_headers()

    def _manifest_path(self, name):
        candidate = (self.root / "manifests" / Path(name).name).resolve()
        if candidate.parent != (self.root / "manifests").resolve() or not candidate.is_file():
            return None
        return candidate

    def _send_media(self, relative_name):
        candidate = (self.root / relative_name).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:
            return self.send_error(404)
        if not candidate.is_file():
            return self.send_error(404)
        self.path = "/" + str(candidate.relative_to(self.root))
        return SimpleHTTPRequestHandler.do_GET(self)

    def translate_path(self, path):
        relative = unquote(urlparse(path).path).lstrip("/")
        return str((self.root / relative).resolve())

    def _send_html(self, document):
        payload = document.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format_string, *args):
        return


STYLE = """
body{font:16px system-ui;background:#171527;color:#fff;margin:2rem}
a{color:#ffd54a}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:1rem}
article{background:#292545;padding:1rem;border-radius:12px}video{width:100%}
.controls{position:sticky;top:0;background:#171527;padding:1rem 0;z-index:2}
button{font:700 18px system-ui;padding:.7rem 1.2rem}small{color:#c9c3e8}
.badges{display:flex;flex-wrap:wrap;gap:.35rem}.badge{background:#4a446f;border-radius:999px;padding:.25rem .55rem;font-size:.78rem;font-weight:700}
.badge.good{background:#236841}.badge.warn{background:#8a4725}.transcript{background:#1c1931;padding:.7rem;border-radius:8px;max-height:9rem;overflow:auto}
.reasons{color:#ded9f5;padding-left:1.2rem;font-size:.9rem}
"""


def render_analysis(clip):
    analysis = clip.get("analysis")
    if not isinstance(analysis, dict):
        return "<p><small>Not analyzed yet.</small></p>"
    recommended = bool(analysis.get("recommended_approved"))
    badge_class = "good" if recommended else "warn"
    labels = [
        "<span class='badge %s'>%s</span>"
        % (badge_class, "RECOMMENDED KEEP" if recommended else "REVIEW / REJECT")
    ]
    labels.append(
        "<span class='badge'>%s · %.0f%%</span>"
        % (
            escape(str(analysis.get("suggested_kind", "uncertain")).upper()),
            float(analysis.get("confidence", 0)) * 100,
        )
    )
    reasons = "".join(
        "<li>%s</li>" % escape(str(reason)) for reason in analysis.get("reasons", [])
    )
    transcript = escape(str(analysis.get("transcript") or "No speech transcript."))
    return (
        "<div class='badges'>%s</div><p class='transcript'>%s</p><ul class='reasons'>%s</ul>"
        % ("".join(labels), transcript, reasons)
    )


def render_index(root):
    rows = []
    total = approved = 0
    for path in manifest_paths(root):
        manifest = load_manifest(path)
        clip_count = len(manifest["clips"])
        kept = sum(bool(clip.get("approved")) for clip in manifest["clips"])
        total += clip_count
        approved += kept
        rows.append(
            "<li><a href='/review/%s'>%s</a> — %d of %d kept</li>"
            % (quote(path.name), escape(str(manifest.get("year", path.stem))), kept, clip_count)
        )
    return """<!doctype html><html><head><meta charset='utf-8'><title>Commercial review</title>
<style>%s</style></head><body><h1>Commercial review</h1><p><strong>%d of %d clips kept.</strong></p>
<p>Open each year, change the Keep boxes, and press Save this year.</p><ol>%s</ol></body></html>""" % (
        STYLE,
        approved,
        total,
        "".join(rows),
    )


def render_review(root, path):
    manifest = load_manifest(path)
    cards = []
    for clip in manifest["clips"]:
        checked = " checked" if clip.get("approved") else ""
        relative = clip["file"]
        cards.append(
            "<article><h2>Clip %03d</h2><video controls preload='metadata' src='/media/%s'></video>"
            "<p><strong>%s</strong><br>%.1f seconds</p>%s"
            "<label><input type='checkbox' name='keep' value='%d'%s> Keep</label></article>"
            % (
                int(clip["sequence"]),
                quote(relative),
                escape(str(clip.get("kind", "unknown"))),
                float(clip.get("duration", 0)),
                render_analysis(clip),
                int(clip["sequence"]),
                checked,
            )
        )
    return """<!doctype html><html><head><meta charset='utf-8'><title>%s review</title>
<style>%s</style></head><body><p><a href='/'>← All years</a></p><h1>%s commercials</h1>
<form method='post' action='/save/%s'><div class='controls'><button type='submit'>Save this year</button>
 <small>Unchecked clips will not play.</small></div><main>%s</main></form></body></html>""" % (
        escape(str(manifest.get("year", "Commercial"))),
        STYLE,
        escape(str(manifest.get("year", "Commercial"))),
        quote(path.name),
        "".join(cards),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description="Review and save commercial Keep choices.")
    parser.add_argument("root", type=Path, help="import root, such as commercials/v2")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    root = args.root.expanduser().resolve()
    if not manifest_paths(root):
        print("No manifests found below %s" % root, file=sys.stderr)
        return 1
    ReviewHandler.root = root
    server = HTTPServer(("127.0.0.1", args.port), ReviewHandler)
    url = "http://127.0.0.1:%d/" % args.port
    print("Commercial reviewer: %s" % url)
    print("Press Ctrl+C when review is complete.")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nReview server stopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
