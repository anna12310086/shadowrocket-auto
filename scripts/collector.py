import base64
import json
import os
import re
import socket
import urllib.parse
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / "config" / "sources.txt"
OUTPUT = ROOT / "docs" / "shadowrocket.txt"

TIMEOUT = 3
MAX_NODES = 100


def decode_base64(value):
    value = value.strip()
    value += "=" * (-len(value) % 4)
    try:
        return base64.urlsafe_b64decode(value).decode("utf-8")
    except Exception:
        return ""


def decode_subscription(content):
    content = content.strip()

    decoded = decode_base64(content)
    if decoded and "://" in decoded:
        content = decoded

    return content.splitlines()


def get_endpoint(line):
    line = line.strip()

    if line.startswith("vmess://"):
        raw = decode_base64(line[8:].split("#")[0])
        try:
            data = json.loads(raw)
            return data.get("add"), int(data.get("port", 0))
        except Exception:
            return None, None

    if line.startswith(("vless://", "trojan://")):
        try:
            parsed = urllib.parse.urlsplit(line)
            return parsed.hostname, parsed.port
        except Exception:
            return None, None

    if line.startswith("ss://"):
        try:
            value = line[5:].split("#")[0].split("?")[0]

            if "@" in value:
                endpoint = value.rsplit("@", 1)[1]
            else:
                decoded = decode_base64(value)
                endpoint = decoded.rsplit("@", 1)[-1]

            parsed = urllib.parse.urlsplit("//" + endpoint)
            return parsed.hostname, parsed.port
        except Exception:
            return None, None

    return None, None


def reachable(host, port):
    if not host or not port or not (1 <= port <= 65535):
        return False

    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return True
    except Exception:
        return False


def main():
    sources = []

    if SOURCES.exists():
        for line in SOURCES.read_text(
            encoding="utf-8"
        ).splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)

    nodes = []
    seen = set()

    for url in sources:
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            response.raise_for_status()

            for line in decode_subscription(response.text):
                line = line.strip()

                if not re.match(
                    r"^(ss|vmess|vless|trojan)://",
                    line
                ):
                    continue

                if line in seen:
                    continue

                host, port = get_endpoint(line)

                if reachable(host, port):
                    seen.add(line)
                    nodes.append(line)

                if len(nodes) >= MAX_NODES:
                    break

        except Exception as error:
            print("Source failed:", error)

    if not nodes:
        print("No usable nodes. Keeping previous subscription.")
        return

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    content = base64.b64encode(
        "\n".join(nodes).encode("utf-8")
    ).decode("ascii")

    OUTPUT.write_text(content + "\n", encoding="utf-8")

    print("Published nodes:", len(nodes))


if __name__ == "__main__":
    main()
