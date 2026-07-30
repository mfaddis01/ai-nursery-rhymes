import json
import os
import random
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

CLAUDE_TIMEOUT_SECONDS = 180

# Rotated per generation so successive runs don't converge on the same rhyme.
THEMES = [
    "animals", "bedtime", "counting", "weather", "food", "the seasons",
    "colours", "things that go", "the sea", "the garden", "family",
    "playtime", "the farm", "morning routines", "birds", "the forest",
]

class RhymeManager:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.popular_rhymes_file = self.data_dir / "popular_rhymes.json"
        self.generated_rhymes_file = self.data_dir / "generated_rhymes.json"
        self.claude_bin = os.getenv("CLAUDE_BIN", "claude")
        self._load_rhymes()

    def _load_rhymes(self):
        """Load all rhymes from disk."""
        self.popular_rhymes = self._load_json(self.popular_rhymes_file)
        self.generated_rhymes = self._load_json(self.generated_rhymes_file)

    def _load_json(self, filepath: Path) -> List[Dict]:
        """Safely load JSON file."""
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_rhymes(self):
        """Save all rhymes to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.popular_rhymes_file, 'w') as f:
            json.dump(self.popular_rhymes, f, indent=2)
        with open(self.generated_rhymes_file, 'w') as f:
            json.dump(self.generated_rhymes, f, indent=2)

    def _call_claude(self, prompt: str) -> str:
        """Run a one-shot prompt through the Claude Code CLI.

        Uses the CLI rather than the Anthropic SDK so the scheduler runs on the
        existing Claude Code login and needs no ANTHROPIC_API_KEY.
        """
        # An ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN in the environment takes
        # precedence over the CLI's own login and makes it exit 1. We rely on
        # the Claude Code login here, so strip both for the subprocess.
        env = os.environ.copy()
        env.pop("ANTHROPIC_API_KEY", None)
        env.pop("ANTHROPIC_AUTH_TOKEN", None)

        result = subprocess.run(
            [self.claude_bin, "-p", prompt],
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_SECONDS,
            env=env,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"claude CLI exited {result.returncode}: {result.stderr.strip()[:500]}"
            )
        output = result.stdout.strip()
        if not output:
            raise RuntimeError("claude CLI returned empty output")
        return output

    @staticmethod
    def _parse_rhyme_json(output: str) -> Dict:
        """Pull the {title, text} object out of the CLI's reply."""
        fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", output, re.DOTALL)
        candidate = fenced.group(1) if fenced else output
        brace = re.search(r"\{.*\}", candidate, re.DOTALL)
        if not brace:
            raise ValueError(f"no JSON object in claude output: {output[:300]}")
        data = json.loads(brace.group(0))
        title = str(data.get("title", "")).strip()
        text = str(data.get("text", "")).strip()
        if not title or not text:
            raise ValueError(f"claude output missing title or text: {output[:300]}")
        return {"title": title, "text": text}

    def generate_new_rhyme(self, theme: Optional[str] = None, age_group: str = "2-5") -> Dict:
        """Generate a new nursery rhyme using Claude."""
        # With a fixed prompt the CLI returns the same rhyme every run, so the
        # AI half of the batch would publish one identical video forever. Vary
        # the theme and tell Claude what already exists.
        if theme is None:
            theme = random.choice(THEMES)
        theme_hint = f" with theme: {theme}"

        previous = [r.get("title", "") for r in self.generated_rhymes][-40:]
        avoid = ""
        if previous:
            avoid = (
                "\n\nThese rhymes already exist - your rhyme must be clearly "
                "different from all of them in title, subject, and imagery:\n"
                + "\n".join(f"- {t}" for t in previous)
            )

        prompt = f"""Create a short, original nursery rhyme for children ages {age_group}{theme_hint}.
Requirements:
- 8-12 lines long
- Simple, fun language
- Rhyming pattern (AABB or similar)
- Safe for young children
- Memorable and singable

Respond with ONLY a JSON object, no prose and no code fence, in exactly this shape:
{{"title": "<a short title, 2-5 words>", "text": "<the rhyme, lines separated by \\n>"}}{avoid}"""

        parsed = self._parse_rhyme_json(self._call_claude(prompt))
        title = parsed["title"]
        rhyme_text = parsed["text"]
        rhyme_id = f"generated_{len(self.generated_rhymes)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        rhyme = {
            "id": rhyme_id,
            "title": title,
            "text": rhyme_text,
            "source": "ai-generated",
            "theme": [theme] if theme else ["general"],
            "age_group": age_group,
            "duration_estimate": len(rhyme_text.split()) * 2,
            "created": datetime.now().isoformat()
        }

        self.generated_rhymes.append(rhyme)
        self._save_rhymes()
        return rhyme

    def get_random_rhyme(self, source: str = "all") -> Dict:
        """Get a random rhyme."""
        import random
        if source == "popular":
            pool = self.popular_rhymes
        elif source == "generated":
            pool = self.generated_rhymes
        else:
            pool = self.popular_rhymes + self.generated_rhymes

        if not pool:
            raise ValueError(f"No rhymes available for source: {source}")
        return random.choice(pool)

    def get_rhymes_by_theme(self, theme: str) -> List[Dict]:
        """Get all rhymes matching a theme."""
        all_rhymes = self.popular_rhymes + self.generated_rhymes
        return [r for r in all_rhymes if theme.lower() in [t.lower() for t in r.get("theme", [])]]

    def get_rhyme_by_id(self, rhyme_id: str) -> Optional[Dict]:
        """Get a specific rhyme by ID."""
        all_rhymes = self.popular_rhymes + self.generated_rhymes
        for rhyme in all_rhymes:
            if rhyme["id"] == rhyme_id:
                return rhyme
        return None
