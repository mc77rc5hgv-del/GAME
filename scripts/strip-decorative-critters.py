#!/usr/bin/env python3
"""Removes ambient sea-creature and decorative elements (fish schools, crabs,
snails, sea urchins, animated seaweed/anemones) from the locally-fetched
Jumpy level files. Run after scripts/fetch-dev-assets.sh, against
assets/map/levels/*.map.yaml (gitignored - see THIRD_PARTY_NOTICES.md).

Kept as an explicit, reproducible project preference (not committed level
data itself, since that stays excluded), so it can be re-applied any time
assets/ gets re-fetched.
"""
import glob
import re
import sys

# Whole map layer removed outright - in every shipped level this layer
# contains only these ambient critters and nothing else.
STRIP_LAYERS = {"critters"}

# Individual element placements removed wherever they appear (e.g. mixed
# into a "decorations" layer alongside kept elements like sproinger).
STRIP_ELEMENTS = {
    "/elements/environment/fish_school/fish_school.element.yaml",
    "/elements/environment/crab/crab.element.yaml",
    "/elements/environment/snail/snail.element.yaml",
    "/elements/environment/urchin/urchin.element.yaml",
    "/elements/decoration/seaweed/seaweed.element.yaml",
    "/elements/decoration/anemones/anemones.element.yaml",
}

LAYER_RE = re.compile(r"^- id: (.+?)\s*$")
POS_RE = re.compile(r"^  - pos:\s*$")
ELEMENT_RE = re.compile(r"^    element: (.+?)\s*$")
# Some levels use YAML flow style for the same element list instead:
# "  - { pos: [x, y], element: /path/to/foo.element.yaml }"
FLOW_RE = re.compile(r"^  - \{.*\belement:\s*(\S+?)\s*\}\s*$")


def strip_file(path: str) -> bool:
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    out = []
    i, n = 0, len(lines)
    while i < n:
        line = lines[i]

        layer_match = LAYER_RE.match(line)
        if layer_match and layer_match.group(1) in STRIP_LAYERS:
            i += 1
            while i < n and not LAYER_RE.match(lines[i]):
                i += 1
            continue

        if POS_RE.match(line) and i + 3 < n and ELEMENT_RE.match(lines[i + 3]):
            element = ELEMENT_RE.match(lines[i + 3]).group(1)
            if element in STRIP_ELEMENTS:
                i += 4
                continue

        flow_match = FLOW_RE.match(line)
        if flow_match and flow_match.group(1) in STRIP_ELEMENTS:
            i += 1
            continue

        out.append(line)
        i += 1

    new_text = "\n".join(out)
    old_text = "\n".join(lines)
    if new_text != old_text:
        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)
        return True
    return False


def main():
    paths = sorted(glob.glob("assets/map/levels/*.map.yaml"))
    if not paths:
        print("No level files found - run scripts/fetch-dev-assets.sh first.", file=sys.stderr)
        sys.exit(1)
    for path in paths:
        changed = strip_file(path)
        print(f"{'patched' if changed else 'unchanged'}: {path}")


if __name__ == "__main__":
    main()
