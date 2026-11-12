#!/usr/bin/env python3
"""Review, adjust, and save detected episode intro cues locally."""

import argparse
from html import escape
from http.server import HTTPServer, SimpleHTTPRequestHandler
import json
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, quote, unquote, urlparse
import webbrowser


def load_candidates(path):
    with Path(path).open() as candidate_file:
        data = json.load(candidate_file)
    if not isinstance(data.get("episodes"), dict):
        raise ValueError("Candidate file must contain an episodes object")
    return data


def save_review(path, form):
    path = Path(path)
    data = load_candidates(path)
    for episode_id, episode in data["episodes"].items():
        cue_values = form.get("cue_" + episode_id, [])
        if cue_values:
            cue = float(cue_values[0])
            if cue <= 0:
                raise ValueError("Cue for %s must be greater than zero" % episode_id)
            episode["intro_end"] = round(cue, 3)
        episode["reviewed"] = ("reviewed_" + episode_id) in form
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    os.replace(str(temporary), str(path))
    return sum(bool(episode["reviewed"]) for episode in data["episodes"].values())


def export_reviewed_cues(candidate_path, destination):
    data = load_candidates(candidate_path)
    cues = {
        episode_id: float(episode["intro_end"])
        for episode_id, episode in data["episodes"].items()
        if episode.get("reviewed") and episode.get("intro_end") is not None
    }
    destination = Path(destination)
    existing = {"episode_cues": {}, "season_defaults": {}}
    if destination.is_file():
        existing = json.loads(destination.read_text())
    existing.setdefault("episode_cues", {}).update(cues)
    existing.setdefault("season_defaults", {})
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n")
    os.replace(str(temporary), str(destination))
    return len(cues)


class IntroReviewHandler(SimpleHTTPRequestHandler):
    candidate_path = None
    output_directory = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self._send_html(render_review(self.candidate_path))
        if parsed.path.startswith("/preview/"):
            return self._send_preview(unquote(parsed.path[len("/preview/") :]))
        return self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/save":
            return self.send_error(404)
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
        try:
            save_review(self.candidate_path, form)
        except (OSError, ValueError, KeyError) as error:
            return self.send_error(400, str(error))
        self.send_response(303)
        self.send_header("Location", "/?saved=1")
        self.end_headers()

    def _send_preview(self, name):
        candidate = (self.output_directory / "previews" / Path(name).name).resolve()
        preview_root = (self.output_directory / "previews").resolve()
        if candidate.parent != preview_root or not candidate.is_file():
            return self.send_error(404)
        self.path = "/previews/" + candidate.name
        return SimpleHTTPRequestHandler.do_GET(self)

    def translate_path(self, path):
        relative = unquote(urlparse(path).path).lstrip("/")
        return str((self.output_directory / relative).resolve())

    def _send_html(self, document):
        payload = document.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format_string, *args):
        return


def render_review(candidate_path):
    data = load_candidates(candidate_path)
    cards = []
    for episode_id, episode in sorted(data["episodes"].items()):
        confidence = escape(str(episode.get("confidence", "unknown")))
        cue = episode.get("intro_end")
        checked = " checked" if episode.get("reviewed") else ""
        before = quote(episode_id + "-before.mp4")
        after = quote(episode_id + "-after.mp4")
        cards.append(
            "<article class='%s'><h2>%s</h2><p>%s</p>"
            "<div class='videos'><div><strong>Before cut</strong><video controls preload='metadata' src='/preview/%s'></video></div>"
            "<div><strong>After resume</strong><video controls preload='metadata' src='/preview/%s'></video></div></div>"
            "<p>Confidence: <strong>%s</strong> · Similarity %.1f%% · Peer %s</p>"
            "<label>Cue seconds <input type='number' step='0.001' min='0.001' name='cue_%s' value='%.3f'></label> "
            "<label><input type='checkbox' name='reviewed_%s'%s> Approved</label></article>"
            % (
                confidence,
                escape(episode_id),
                escape(Path(episode["source_file"]).name),
                before,
                after,
                confidence,
                float(episode.get("audio_similarity", 0)) * 100,
                escape(str(episode.get("best_peer") or "none")),
                escape(episode_id),
                float(cue or 0),
                escape(episode_id),
                checked,
            )
        )
    return """<!doctype html><html><head><meta charset='utf-8'><title>Intro cue review</title>
<style>body{font:16px system-ui;background:#171527;color:#fff;margin:2rem}main{display:grid;gap:1rem}
article{background:#292545;padding:1rem;border-radius:12px}.videos{display:grid;grid-template-columns:1fr 1fr;gap:1rem}
video{width:100%%}.high{border-left:8px solid #58d68d}.medium{border-left:8px solid #f4d03f}.low{border-left:8px solid #ec7063}
.controls{position:sticky;top:0;background:#171527;padding:1rem 0;z-index:2}button{font:700 18px system-ui;padding:.7rem 1.2rem}</style>
</head><body><h1>Season %s intro cues</h1><p>Compare the final five seconds before the cut with the first five seconds after resume.
Adjust the cue if needed, check Approved, then save.</p><form method='post' action='/save'><div class='controls'>
<button type='submit'>Save review</button></div><main>%s</main></form></body></html>""" % (
        escape(str(data.get("season", ""))),
        "".join(cards),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--export", type=Path, help="export approved cues and exit")
    args = parser.parse_args(argv)
    candidate_path = args.candidates.expanduser().resolve()
    if args.export:
        try:
            count = export_reviewed_cues(candidate_path, args.export.expanduser().resolve())
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
            print("Could not export cues: %s" % error, file=sys.stderr)
            return 1
        print("Exported %d reviewed cues to %s" % (count, args.export))
        return 0
    try:
        load_candidates(candidate_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("Could not open candidates: %s" % error, file=sys.stderr)
        return 1
    IntroReviewHandler.candidate_path = candidate_path
    IntroReviewHandler.output_directory = candidate_path.parent
    server = HTTPServer(("127.0.0.1", args.port), IntroReviewHandler)
    url = "http://127.0.0.1:%d/" % args.port
    print("Intro cue reviewer: %s" % url)
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
