"""Explicit localhost-only helper for Painter's opt-in remote scripting server."""
import argparse
import base64
import json
from pathlib import Path
import urllib.request


def run(source, timeout=90):
    payload = json.dumps({"python": base64.b64encode(source.encode("utf-8")).decode("ascii")}).encode()
    request = urllib.request.Request("http://localhost:60041/run.json", payload,
                                     {"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        result = json.loads(response.read())
    if isinstance(result, dict) and "error" in result:
        raise RuntimeError(result["error"])
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", help="Python expression, or an absolute Python file path with --file")
    parser.add_argument("--file", action="store_true")
    args = parser.parse_args()
    source = args.source
    if args.file:
        path = Path(source)
        if not path.is_absolute():
            parser.error("--file requires an absolute path")
        source = ("exec(compile(" + repr(path.read_text(encoding="utf-8")) + ", " + repr(str(path))
                  + ", 'exec'), {'__file__': " + repr(str(path)) + ", '__name__': '__main__'})")
    print(json.dumps(run(source), indent=2))