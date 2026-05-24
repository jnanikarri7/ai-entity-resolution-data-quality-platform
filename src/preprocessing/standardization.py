"""Data standardization utilities for entity resolution

This module handles cleaning and normalizing names, addresses, and dates
to improve matching accuracy.
"""

import re
from datetime import datetime
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class NameStandardizer:
    """Standardize person names for matching"""

    # Common titles to remove
    TITLES = [
        "mr", "mrs", "ms", "miss", "dr", "prof", "rev",
        "hon", "sir", "madam", "master", "esq"
    ]

    # Common suffixes to remove
    SUFFIXES = [
        "jr", "sr", "ii", "iii", "iv", "v",
        "phd", "md", "dds", "esq", "cpa"
    ]

    @classmethod
    def standardize_name(cls, name: Optional[str]) -> Optional[str]:
        """
        Standardize a name for matching

        Steps:
        1. Convert to uppercase
        2. Remove titles (Mr, Mrs, Dr)
        3. Remove suffixes (Jr, Sr, III)
        4. Remove extra whitespace
        5. Remove special characters (except hyphen, apostrophe)

        Args:
            name: Raw name string

        Returns:
            Standardized name or None if input is null/empty

        Examples:
            "Mr. John Smith Jr." -> "JOHN SMITH"
            "Mary O'Brien-Jones" -> "MARY O'BRIEN-JONES"
            "Dr. Sarah Lee, PhD" -> "SARAH LEE"
        """
        if not name or not isinstance(name, str):
            return None

        # Convert to uppercase
        name = name.upper().strip()

        # Remove punctuation except hyphen and apostrophe
        name = re.sub(r"[^\w\s\-']", " ", name)

        # Split into tokens
        tokens = name.split()

        # Remove titles
        tokens = [t for t in tokens if t.lower() not in cls.TITLES]

        # Remove suffixes
        tokens = [t for t in tokens if t.lower() not in cls.SUFFIXES]

        # Remove empty tokens
        tokens = [t for t in tokens if t]

        if not tokens:
            return None

        # Join and normalize whitespace
        standardized = " ".join(tokens)

        return standardized if standardized else None

    @classmethod
    def parse_name(cls, full_name: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Parse full name into first, middle, last components

        Args:
            full_name: Full name string

        Returns:
            Tuple of (first_name, middle_name, last_name)

        Note:
            This is a simple parser. Complex names (hyphenated, multiple middle names)
            may not parse perfectly. Consider using dedicated name parsing library
            like nameparser for production use.
        """
        if not full_name:
            return None, None, None

        standardized = cls.standardize_name(full_name)
        if not standardized:
            return None, None, None

        parts = standardized.split()

        if len(parts) == 1:
            return parts[0], None, None
        elif len(parts) == 2:
            return parts[0], None, parts[1]
        elif len(parts) == 3:
            return parts[0], parts[1], parts[2]
        else:
            # More than 3 parts: first, middle(s), last
            return parts[0], " ".join(parts[1:-1]), parts[-1]


class AddressStandardizer:
    """Standardize addresses for matching"""

    # Common address abbreviations
    ABBREVIATIONS = {
        "STREET": "ST",
        "AVENUE": "AVE",
        "BOULEVARD": "BLVD",
        "ROAD": "RD",
        "DRIVE": "DR",
        "LANE": "LN",
        "COURT": "CT",
        "CIRCLE": "CIR",
        "PLACE": "PL",
        "APARTMENT": "APT",
        "SUITE": "STE",
        "BUILDING": "BLDG",
        "FLOOR": "FL",
        "NORTH": "N",
        "SOUTH": "S",
        "EAST": "E",
        "WEST": "W",
    }

    @classmethod
    def standardize_address(cls, address: Optional[str]) -> Optional[str]:
        """
        Standardize address for matching

        Steps:
        1. Convert to uppercase
        2. Normalize abbreviations (Street -> ST)
        3. Normalize apartment/unit notation (Apt 2B -> #2B)
        4. Remove extra whitespace

        Args:
            address: Raw address string

        Returns:
            Standardized address or None

        Examples:
            "123 Main Street Apt 2B" -> "123 MAIN ST #2B"
            "456 Oak Avenue, Suite 100" -> "456 OAK AVE #100"
        """
        if not address or not isinstance(address, str):
            return None

        # Convert to uppercase
        address = address.upper().strip()

        # Remove extra punctuation
        address = re.sub(r"[,.]", " ", address)

        # Normalize apartment/suite notation
        address = re.sub(r"\bAPT\s+", "#", address)
        address = re.sub(r"\bSUITE\s+", "#", address)
        address = re.sub(r"\bUNIT\s+", "#", address)
        address = re.sub(r"\bNUMBER\s+", "#", address)

        # Apply abbreviations
        for full, abbrev in cls.ABBREVIATIONS.items():
            address = re.sub(r"\b" + full + r"\b", abbrev, address)

        # Normalize whitespace
        address = re.sub(r"\s+", " ", address).strip()

        return address if address else None

    @classmethod
    def extract_zip_code(cls, address: Optional[str]) -> Optional[str]:
        """
        Extract ZIP code from address string

        Args:
            address: Address string potentially containing ZIP

        Returns:
            ZIP code (5 digits) or ZIP+4 (9 digits) or None
        """
        if not address:
            return None

        # Match 5-digit ZIP or 5+4 ZIP
        match = re.search(r"\b(\d{5})(?:-(\d{4}))?\b", address)
        if match:
            zip5 = match.group(1)
            zip4 = match.group(2)
            return f"{zip5}-{zip4}" if zip4 else zip5

        return None


class DateParser:
    """Parse and standardize dates from multiple formats"""

    # Common date formats to try
    DATE_FORMATS = [
        "%Y-%m-%d",      # 2024-01-15
        "%m/%d/%Y",      # 01/15/2024
        "%d/%m/%Y",      # 15/01/2024
        "%m-%d-%Y",      # 01-15-2024
        "%Y/%m/%d",      # 2024/01/15
        "%m/%d/%y",      # 01/15/24
        "%d-%b-%Y",      # 15-Jan-2024
        "%b %d, %Y",     # Jan 15, 2024
        "%B %d, %Y",     # January 15, 2024
    ]

    @classmethod
    def parse_date(cls, date_str: Optional[str]) -> Optional[datetime]:
        """
        Parse date from string, trying multiple formats

        Args:
            date_str: Date string in various formats

        Returns:
            datetime object or None if parsing fails
        """
        if not date_str or not isinstance(date_str, str):
            return None

        date_str = date_str.strip()

        # Try each format
        for fmt in cls.DATE_FORMATS:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    @classmethod
    def standardize_date(cls, date_str: Optional[str]) -> Optional[str]:
        """
        Standardize date to ISO 8601 format (YYYY-MM-DD)

        Args:
            date_str: Date string in various formats

        Returns:
            ISO 8601 date string or None
        """
        parsed = cls.parse_date(date_str)
        if parsed:
            return parsed.strftime("%Y-%m-%d")
        return None

    @classmethod
    def validate_dob(cls, date_str: Optional[str],
                     min_year: int = 1900,
                     max_year: Optional[int] = None) -> bool:
        """
        Validate date of birth is within reasonable range

        Args:
            date_str: Date string
            min_year: Minimum valid year (default 1900)
            max_year: Maximum valid year (default current year)

        Returns:
            True if valid, False otherwise
        """
        if max_year is None:
            max_year = datetime.now().year

        parsed = cls.parse_date(date_str)
        if not parsed:
            return False

        return min_year <= parsed.year <= max_year


if __name__ == "__main__":
    # Test standardization
    print("=== Name Standardization ===")
    test_names = [
        "Mr. John Smith Jr.",
        "Mary O'Brien-Jones",
        "Dr. Sarah Lee, PhD",
        "ROBERT JOHNSON",
        None,
    ]
    for name in test_names:
        print(f"{name} -> {NameStandardizer.standardize_name(name)}")

    print("\n=== Address Standardization ===")
    test_addresses = [
        "123 Main Street Apt 2B",
        "456 Oak Avenue, Suite 100",
        "789 Broadway, New York, NY 10001",
    ]
    for addr in test_addresses:
        print(f"{addr} -> {AddressStandardizer.standardize_address(addr)}")

    print("\n=== Date Parsing ===")
    test_dates = [
        "01/15/1985",
        "1985-01-15",
        "Jan 15, 1985",
        "15-01-1985",
    ]
    for date in test_dates:
        print(f"{date} -> {DateParser.standardize_date(date)}")
