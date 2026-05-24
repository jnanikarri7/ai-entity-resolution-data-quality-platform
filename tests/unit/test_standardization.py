"""Unit tests for data standardization module"""

import pytest
from src.preprocessing.standardization import (
    NameStandardizer,
    AddressStandardizer,
    DateParser
)


class TestNameStandardizer:
    """Test name standardization"""

    def test_remove_titles(self):
        """Should remove common titles like Mr, Mrs, Dr"""
        assert NameStandardizer.standardize_name("Mr. John Smith") == "JOHN SMITH"
        assert NameStandardizer.standardize_name("Dr. Sarah Lee") == "SARAH LEE"
        assert NameStandardizer.standardize_name("Mrs. Jane Doe") == "JANE DOE"

    def test_remove_suffixes(self):
        """Should remove suffixes like Jr, Sr, III"""
        assert NameStandardizer.standardize_name("John Smith Jr.") == "JOHN SMITH"
        assert NameStandardizer.standardize_name("Robert Johnson Sr.") == "ROBERT JOHNSON"
        assert NameStandardizer.standardize_name("William III") == "WILLIAM"

    def test_uppercase_conversion(self):
        """Should convert to uppercase"""
        assert NameStandardizer.standardize_name("john smith") == "JOHN SMITH"
        assert NameStandardizer.standardize_name("Mary Jones") == "MARY JONES"

    def test_preserve_hyphen_apostrophe(self):
        """Should preserve hyphens and apostrophes"""
        assert NameStandardizer.standardize_name("Mary O'Brien") == "MARY O'BRIEN"
        assert NameStandardizer.standardize_name("Jean-Paul") == "JEAN-PAUL"

    def test_handle_null_names(self):
        """Should handle None and empty strings gracefully"""
        assert NameStandardizer.standardize_name(None) is None
        assert NameStandardizer.standardize_name("") is None
        assert NameStandardizer.standardize_name("   ") is None

    def test_parse_full_name(self):
        """Should parse full name into components"""
        first, middle, last = NameStandardizer.parse_name("John Michael Smith")
        assert first == "JOHN"
        assert middle == "MICHAEL"
        assert last == "SMITH"

    def test_parse_two_part_name(self):
        """Should handle two-part names"""
        first, middle, last = NameStandardizer.parse_name("John Smith")
        assert first == "JOHN"
        assert middle is None
        assert last == "SMITH"


class TestAddressStandardizer:
    """Test address standardization"""

    def test_abbreviate_street_types(self):
        """Should abbreviate street types"""
        assert "MAIN ST" in AddressStandardizer.standardize_address("123 Main Street")
        assert "OAK AVE" in AddressStandardizer.standardize_address("456 Oak Avenue")
        assert "ELM BLVD" in AddressStandardizer.standardize_address("789 Elm Boulevard")

    def test_normalize_apartment_notation(self):
        """Should normalize apartment/suite notation to #"""
        assert "#2B" in AddressStandardizer.standardize_address("123 Main St Apt 2B")
        assert "#100" in AddressStandardizer.standardize_address("456 Oak Ave Suite 100")
        assert "#5" in AddressStandardizer.standardize_address("789 Elm St Unit 5")

    def test_uppercase_conversion(self):
        """Should convert to uppercase"""
        result = AddressStandardizer.standardize_address("123 main street")
        assert result == "123 MAIN ST"

    def test_handle_null_addresses(self):
        """Should handle None and empty strings"""
        assert AddressStandardizer.standardize_address(None) is None
        assert AddressStandardizer.standardize_address("") is None

    def test_extract_zip_code(self):
        """Should extract ZIP code from address"""
        assert AddressStandardizer.extract_zip_code("123 Main St, Baltimore MD 21201") == "21201"
        assert AddressStandardizer.extract_zip_code("456 Oak Ave 21201-1234") == "21201-1234"

    def test_extract_zip_code_not_found(self):
        """Should return None when ZIP not found"""
        assert AddressStandardizer.extract_zip_code("123 Main Street") is None
        assert AddressStandardizer.extract_zip_code(None) is None


class TestDateParser:
    """Test date parsing and standardization"""

    def test_parse_iso_format(self):
        """Should parse ISO 8601 format"""
        assert DateParser.standardize_date("2024-01-15") == "2024-01-15"

    def test_parse_us_format(self):
        """Should parse US date format MM/DD/YYYY"""
        assert DateParser.standardize_date("01/15/2024") == "2024-01-15"
        assert DateParser.standardize_date("12/31/1985") == "1985-12-31"

    def test_parse_text_format(self):
        """Should parse text date formats"""
        assert DateParser.standardize_date("Jan 15, 2024") == "2024-01-15"
        assert DateParser.standardize_date("January 15, 2024") == "2024-01-15"

    def test_handle_invalid_dates(self):
        """Should return None for invalid dates"""
        assert DateParser.standardize_date("not-a-date") is None
        assert DateParser.standardize_date("99/99/9999") is None
        assert DateParser.standardize_date(None) is None

    def test_validate_dob_valid(self):
        """Should validate reasonable DOBs"""
        assert DateParser.validate_dob("01/15/1985") is True
        assert DateParser.validate_dob("2000-12-31") is True

    def test_validate_dob_invalid(self):
        """Should reject unreasonable DOBs"""
        assert DateParser.validate_dob("01/01/1800") is False  # Too old
        assert DateParser.validate_dob("01/01/2050") is False  # In future
        assert DateParser.validate_dob("invalid") is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
