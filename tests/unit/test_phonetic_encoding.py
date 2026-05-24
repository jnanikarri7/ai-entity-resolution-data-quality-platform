"""Unit tests for phonetic encoding"""

import pytest
from src.preprocessing.phonetic_transforms import PhoneticEncoder


class TestPhoneticEncoder:
    """Test phonetic encoding algorithms"""

    def test_soundex_similar_names(self):
        """Should generate same Soundex for phonetically similar names"""
        # Smith and Smyth sound the same
        assert PhoneticEncoder.soundex("Smith") == PhoneticEncoder.soundex("Smyth")

        # Johnson and Johnsen
        assert PhoneticEncoder.soundex("Johnson") == PhoneticEncoder.soundex("Johnsen")

    def test_soundex_different_names(self):
        """Should generate different Soundex for different sounding names"""
        assert PhoneticEncoder.soundex("Smith") != PhoneticEncoder.soundex("Jones")
        assert PhoneticEncoder.soundex("Robert") != PhoneticEncoder.soundex("Michael")

    def test_soundex_format(self):
        """Soundex should return 4-character code"""
        result = PhoneticEncoder.soundex("Smith")
        assert result is not None
        assert len(result) == 4
        assert result[0].isalpha()  # First char is letter
        assert result[1:].isdigit()  # Rest are digits

    def test_soundex_null_handling(self):
        """Should handle None and empty strings"""
        assert PhoneticEncoder.soundex(None) is None
        assert PhoneticEncoder.soundex("") is None

    def test_soundex_case_insensitive(self):
        """Should be case insensitive"""
        assert PhoneticEncoder.soundex("Smith") == PhoneticEncoder.soundex("SMITH")
        assert PhoneticEncoder.soundex("Smith") == PhoneticEncoder.soundex("smith")

    def test_encode_all(self):
        """Should return dictionary with all encodings"""
        encodings = PhoneticEncoder.encode_all("Smith")
        assert isinstance(encodings, dict)
        assert "soundex" in encodings
        assert encodings["soundex"] is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
