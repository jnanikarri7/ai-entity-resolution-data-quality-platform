"""Survivorship rules for selecting best field values

When multiple records are matched to the same entity, survivorship rules
determine which field values to keep in the golden record.

Common strategies:
- Most recent: Latest updated_date
- Most complete: Longest/most detailed value
- Most common: Majority vote across records
- Most trusted source: Based on source_system priority
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import Counter
import logging

logger = logging.getLogger(__name__)


class SurvivorshipResolver:
    """
    Apply survivorship rules to resolve field conflicts in matched records
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize survivorship resolver

        Args:
            config: Survivorship configuration with rules per field
        """
        self.config = config
        self.field_rules = config

    def resolve_cluster(self, records: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Apply survivorship rules to a cluster of matched records

        Args:
            records: List of matched record dictionaries

        Returns:
            Golden record dictionary with best field values
        """
        if not records:
            return {}

        if len(records) == 1:
            return records[0]

        golden_record = {}

        # Get all fields from first record as template
        fields = records[0].keys()

        for field in fields:
            # Skip metadata fields
            if field in ["record_id", "source_system_id", "ingestion_timestamp"]:
                continue

            rule_config = self.field_rules.get(field, {})
            rule = rule_config.get("rule", "most_recent")
            fallback = rule_config.get("fallback", "most_recent")

            try:
                value = self._apply_rule(records, field, rule)

                # If primary rule returns None, try fallback
                if value is None and fallback:
                    value = self._apply_rule(records, field, fallback)

                golden_record[field] = value

            except Exception as e:
                logger.warning(f"Error resolving field {field}: {e}")
                # Default: use first non-null value
                golden_record[field] = next(
                    (r[field] for r in records if r.get(field) is not None),
                    None
                )

        # Add metadata
        golden_record["cluster_size"] = len(records)
        golden_record["source_record_ids"] = [r["record_id"] for r in records]
        golden_record["created_at"] = datetime.utcnow().isoformat()

        return golden_record

    def _apply_rule(
        self,
        records: List[Dict[str, Any]],
        field: str,
        rule: str
    ) -> Any:
        """
        Apply specific survivorship rule to field

        Args:
            records: List of records
            field: Field name to resolve
            rule: Rule to apply

        Returns:
            Resolved field value
        """
        if rule == "most_recent":
            return self._most_recent(records, field)

        elif rule == "most_complete":
            return self._most_complete(records, field)

        elif rule == "most_common":
            return self._most_common(records, field)

        elif rule == "most_trusted_source":
            return self._most_trusted_source(records, field)

        elif rule == "longest":
            return self._longest(records, field)

        elif rule == "newest_non_null":
            return self._newest_non_null(records, field)

        else:
            logger.warning(f"Unknown rule: {rule}, using most_recent")
            return self._most_recent(records, field)

    def _most_recent(self, records: List[Dict[str, Any]], field: str) -> Any:
        """
        Select value from most recently updated record

        Args:
            records: List of records
            field: Field name

        Returns:
            Value from most recent record
        """
        # Filter records with non-null field and updated_date
        candidates = [
            r for r in records
            if r.get(field) is not None and r.get("updated_date")
        ]

        if not candidates:
            return None

        # Sort by updated_date descending
        candidates.sort(
            key=lambda r: r.get("updated_date", "1900-01-01"),
            reverse=True
        )

        return candidates[0][field]

    def _most_complete(self, records: List[Dict[str, Any]], field: str) -> Any:
        """
        Select most complete (longest/most detailed) value

        Args:
            records: List of records
            field: Field name

        Returns:
            Most complete value
        """
        values = [r.get(field) for r in records if r.get(field) is not None]

        if not values:
            return None

        # For strings: longest
        if isinstance(values[0], str):
            return max(values, key=len)

        # For dates: most precise (has day/month/year vs just year)
        # For now, return first non-null
        return values[0]

    def _most_common(self, records: List[Dict[str, Any]], field: str) -> Any:
        """
        Select most frequent value (majority vote)

        Args:
            records: List of records
            field: Field name

        Returns:
            Most common value
        """
        values = [r.get(field) for r in records if r.get(field) is not None]

        if not values:
            return None

        # Count occurrences
        counter = Counter(values)
        most_common = counter.most_common(1)

        return most_common[0][0] if most_common else None

    def _most_trusted_source(self, records: List[Dict[str, Any]], field: str) -> Any:
        """
        Select value from most trusted source system

        Args:
            records: List of records
            field: Field name

        Returns:
            Value from highest priority source
        """
        rule_config = self.field_rules.get(field, {})
        source_priority = rule_config.get("source_priority", [])

        if not source_priority:
            logger.warning(f"No source priority defined for {field}")
            return self._most_recent(records, field)

        # Create priority map
        priority_map = {source: i for i, source in enumerate(source_priority)}

        # Filter and sort by source priority
        candidates = [
            r for r in records
            if r.get(field) is not None and r.get("source_system_id")
        ]

        if not candidates:
            return None

        candidates.sort(
            key=lambda r: priority_map.get(r.get("source_system_id"), 999)
        )

        return candidates[0][field]

    def _longest(self, records: List[Dict[str, Any]], field: str) -> Any:
        """
        Select longest string value

        Args:
            records: List of records
            field: Field name

        Returns:
            Longest value
        """
        values = [
            r.get(field) for r in records
            if r.get(field) is not None and isinstance(r.get(field), str)
        ]

        if not values:
            return None

        return max(values, key=len)

    def _newest_non_null(self, records: List[Dict[str, Any]], field: str) -> Any:
        """
        Select newest non-null value

        Args:
            records: List of records
            field: Field name

        Returns:
            Newest non-null value
        """
        candidates = [
            r for r in records
            if r.get(field) is not None
        ]

        if not candidates:
            return None

        # Sort by created_date or updated_date
        candidates.sort(
            key=lambda r: r.get("updated_date") or r.get("created_date", "1900-01-01"),
            reverse=True
        )

        return candidates[0][field]

    def get_survivorship_metadata(
        self,
        records: List[Dict[str, Any]],
        golden_record: Dict[str, Any]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate metadata showing which source each field came from

        Args:
            records: Original matched records
            golden_record: Resolved golden record

        Returns:
            Dictionary mapping fields to source metadata
        """
        metadata = {}

        for field, value in golden_record.items():
            if field in ["cluster_size", "source_record_ids", "created_at"]:
                continue

            # Find which record this value came from
            source_record = next(
                (r for r in records if r.get(field) == value),
                None
            )

            if source_record:
                metadata[field] = {
                    "value": value,
                    "source_system": source_record.get("source_system_id"),
                    "source_record_id": source_record.get("record_id"),
                    "updated_date": source_record.get("updated_date"),
                }

        return metadata


if __name__ == "__main__":
    # Test survivorship
    print("=== Survivorship Rule Testing ===\n")

    config = {
        "first_name": {"rule": "most_common", "fallback": "most_recent"},
        "last_name": {"rule": "most_common", "fallback": "most_recent"},
        "address": {"rule": "most_recent"},
    }

    resolver = SurvivorshipResolver(config)

    test_records = [
        {
            "record_id": "1",
            "source_system_id": "enrollment",
            "first_name": "JOHN",
            "last_name": "SMITH",
            "address": "123 OLD ST",
            "updated_date": "2024-01-01",
        },
        {
            "record_id": "2",
            "source_system_id": "claims",
            "first_name": "JOHN",
            "last_name": "SMITH",
            "address": "456 NEW AVE",
            "updated_date": "2024-06-01",
        },
        {
            "record_id": "3",
            "source_system_id": "case_mgmt",
            "first_name": "JON",  # Typo
            "last_name": "SMITH",
            "address": "456 NEW AVE",
            "updated_date": "2024-03-01",
        },
    ]

    golden = resolver.resolve_cluster(test_records)

    print("Golden Record:")
    print(f"  first_name: {golden['first_name']} (most common)")
    print(f"  last_name: {golden['last_name']}")
    print(f"  address: {golden['address']} (most recent)")
    print(f"  cluster_size: {golden['cluster_size']}")
