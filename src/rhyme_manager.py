import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import anthropic

class RhymeManager:
    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.popular_rhymes_file = self.data_dir / "popular_rhymes.json"
        self.generated_rhymes_file = self.data_dir / "generated_rhymes.json"
        self.client = anthropic.Anthropic()
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

    def generate_new_rhyme(self, theme: Optional[str] = None, age_group: str = "2-5") -> Dict:
        """Generate a new nursery rhyme using Claude."""
        theme_hint = f" with theme: {theme}" if theme else ""
        prompt = f"""Create a short, original nursery rhyme for children ages {age_group}{theme_hint}.
Requirements:
- 8-12 lines long
- Simple, fun language
- Rhyming pattern (AABB or similar)
- Safe for young children
- Memorable and singable

Respond with ONLY the rhyme text, no titles or explanations."""

        message = self.client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=300,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        rhyme_text = message.content[0].text.strip()
        lines = rhyme_text.split('\n')
        title = lines[0].strip().rstrip(',.:!') if lines else f"Nursery Rhyme {len(self.generated_rhymes) + 1}"
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
