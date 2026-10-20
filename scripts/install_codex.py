"""Install both local skills and register this checkout's MCP server."""
from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("building-a-voiceprint", "writing-in-your-voice")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", type=Path,
                        default=Path.home() / ".agents" / "skills")
    args = parser.parse_args()
    if sys.version_info < (3, 10):
        parser.error("Python 3.10 or newer is required")
    codex = shutil.which("codex")
    if not codex:
        parser.error("Install the Codex CLI first, then run this installer again")
    destination = args.skills_dir.expanduser().resolve()
    for name in NAMES:
        target = destination / name
        if (target.exists() or target.is_symlink()) and target.resolve() != ROOT / "skills" / name:
            parser.error(f"{target} already exists. Move it aside before installing")

    # The CLI updates only this named server and preserves other settings.
    subprocess.run([codex, "mcp", "add", "voiceprint", "--env",
                    f"PYTHONPATH={ROOT}", "--", sys.executable,
                    "-m", "voiceprint.mcp"], check=True)
    destination.mkdir(parents=True, exist_ok=True)
    for name in NAMES:
        target = destination / name
        if not target.is_symlink():
            target.symlink_to(ROOT / "skills" / name, target_is_directory=True)
        print(f"Skill linked: {target}")
    print("Restart Codex and say: learn how I write")
    print(f"Keep this checkout at {ROOT}, the skills and server use it directly")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"Installation failed: {error}", file=sys.stderr)
        sys.exit(1)
