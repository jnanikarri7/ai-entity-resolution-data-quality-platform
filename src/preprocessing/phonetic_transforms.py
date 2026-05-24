"""Phonetic encoding for fuzzy name matching

Phonetic algorithms encode names to their phonetic representation,
allowing matching of names that sound similar but are spelled differently.

Examples:
    "Smith" and "Smyth" -> Same Soundex code (S530)
    "Johnson" and "Johnsen" -> Same Soundex code (J525)
"""

from typing import Optional
import logging

try:
    import jellyfish
    JELLYFISH_AVAILABLE = True
except ImportError:
    JELLYFISH_AVAILABLE = False
    logging.warning("jellyfish library not available. Install with: pip install jellyfish")


class PhoneticEncoder:
    """Encode names using phonetic algorithms"""

    @staticmethod
    def soundex(name: Optional[str]) -> Optional[str]:
        """
        Generate Soundex code for name

        Soundex algorithm:
        - Developed by Robert C. Russell and Margaret King Odell
        - Encodes names by sound (phonetic similarity)
        - 4-character code: 1 letter + 3 digits

        Args:
            name: Name to encode

        Returns:
            Soundex code (e.g., "S530") or None

        Reference:
            https://en.wikipedia.org/wiki/Soundex
        """
        if not name or not isinstance(name, str):
            return None

        if JELLYFISH_AVAILABLE:
            return jellyfish.soundex(name.upper())

        # Fallback: Simple Soundex implementation
        return PhoneticEncoder._simple_soundex(name)

    @staticmethod
    def _simple_soundex(name: str) -> str:
        """
        Simple Soundex implementation (fallback when jellyfish not available)

        Note: This is a simplified version. Production should use jellyfish library.
        """
        name = name.upper().strip()
        if not name:
            return ""

        # Keep first letter
        soundex = name[0]

        # Soundex mapping
        mapping = {
            'B': '1', 'F': '1', 'P': '1', 'V': '1',
            'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
            'D': '3', 'T': '3',
            'L': '4',
            'M': '5', 'N': '5',
            'R': '6'
        }

        # Encode remaining letters
        prev_code = mapping.get(name[0], '0')
        for char in name[1:]:
            code = mapping.get(char, '0')
            if code != '0' and code != prev_code:
                soundex += code
            prev_code = code

            if len(soundex) == 4:
                break

        # Pad with zeros
        soundex = (soundex + '000')[:4]
        return soundex

    @staticmethod
    def metaphone(name: Optional[str]) -> Optional[str]:
        """
        Generate Metaphone code for name

        Metaphone algorithm:
        - More sophisticated than Soundex
        - Better handling of English pronunciation rules
        - Variable length code

        Args:
            name: Name to encode

        Returns:
            Metaphone code or None
        """
        if not name or not isinstance(name, str):
            return None

        if not JELLYFISH_AVAILABLE:
            logging.warning("Metaphone requires jellyfish library")
            return None

        return jellyfish.metaphone(name.upper())

    @staticmethod
    def double_metaphone(name: Optional[str]) -> tuple:
        """
        Generate Double Metaphone codes for name

        Double Metaphone:
        - Returns primary and secondary encodings
        - Handles non-English names better than Metaphone
        - Considers alternative pronunciations

        Args:
            name: Name to encode

        Returns:
            Tuple of (primary_code, secondary_code)
        """
        if not name or not isinstance(name, str):
            return None, None

        if not JELLYFISH_AVAILABLE:
            logging.warning("Double Metaphone requires jellyfish library")
            return None, None

        return jellyfish.match_rating_codex(name.upper())

    @staticmethod
    def nysiis(name: Optional[str]) -> Optional[str]:
        """
        Generate NYSIIS code for name

        NYSIIS (New York State Identification and Intelligence System):
        - Developed for genealogy research
        - Better than Soundex for names with common variations
        - Variable length code

        Args:
            name: Name to encode

        Returns:
            NYSIIS code or None
        """
        if not name or not isinstance(name, str):
            return None

        if not JELLYFISH_AVAILABLE:
            logging.warning("NYSIIS requires jellyfish library")
            return None

        return jellyfish.nysiis(name.upper())

    @classmethod
    def encode_all(cls, name: Optional[str]) -> dict:
        """
        Encode name using all available phonetic algorithms

        Useful for debugging or choosing best algorithm for your dataset.

        Args:
            name: Name to encode

        Returns:
            Dictionary with all encoding results
        """
        if not name:
            return {}

        return {
            "soundex": cls.soundex(name),
            "metaphone": cls.metaphone(name),
            "nysiis": cls.nysiis(name),
        }


if __name__ == "__main__":
    # Test phonetic encoding
    print("=== Phonetic Encoding Tests ===\n")

    test_names = [
        ("Smith", "Smyth"),
        ("Johnson", "Johnsen"),
        ("Robert", "Rupert"),
        ("Catherine", "Katherine"),
        ("Lee", "Li"),
    ]

    encoder = PhoneticEncoder()

    for name1, name2 in test_names:
        print(f"Comparing: {name1} vs {name2}")

        s1 = encoder.soundex(name1)
        s2 = encoder.soundex(name2)
        print(f"  Soundex: {s1} vs {s2} {'✓ Match' if s1 == s2 else '✗ No match'}")

        if JELLYFISH_AVAILABLE:
            m1 = encoder.metaphone(name1)
            m2 = encoder.metaphone(name2)
            print(f"  Metaphone: {m1} vs {m2} {'✓ Match' if m1 == m2 else '✗ No match'}")

        print()

    # Show all encodings for a name
    print("\n=== All Encodings for 'Robert Johnson' ===")
    encodings = encoder.encode_all("Robert Johnson")
    for algorithm, code in encodings.items():
        print(f"  {algorithm}: {code}")
