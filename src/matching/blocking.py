"""Blocking strategy for entity resolution

Blocking reduces the comparison space from O(n²) to O(n) by grouping
records into blocks. Only records within the same block are compared.

Example:
    Without blocking: 50M records = 1.25 quadrillion comparisons
    With blocking: 50M records / 100 per block = 50M comparisons (99.996% reduction)

Multi-pass blocking ensures high recall - if first blocking pass misses a match
due to data quality, subsequent passes with different keys may catch it.
"""

from typing import List, Dict, Any, Optional
import logging
from pyspark.sql import DataFrame
from pyspark.sql import functions as F

from ..preprocessing.phonetic_transforms import PhoneticEncoder
from ..preprocessing.standardization import NameStandardizer

logger = logging.getLogger(__name__)


class BlockingStrategy:
    """
    Multi-pass blocking strategy for entity resolution

    Implements multiple blocking passes with different keys to maximize recall
    while minimizing unnecessary comparisons.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize blocking strategy

        Args:
            config: Blocking configuration with passes definition
        """
        self.config = config
        self.passes = config.get("passes", [])
        self.phonetic_encoder = PhoneticEncoder()

        if not self.passes:
            raise ValueError("At least one blocking pass must be configured")

    def apply_blocking(self, df: DataFrame) -> DataFrame:
        """
        Apply multi-pass blocking to DataFrame

        Args:
            df: Input DataFrame with standardized records

        Returns:
            DataFrame with blocking_key columns added
        """
        logger.info(f"Applying {len(self.passes)} blocking passes")

        # Apply each blocking pass
        for i, pass_config in enumerate(self.passes, 1):
            key_type = pass_config.get("key")
            col_name = f"blocking_key_{i}"

            logger.info(f"Pass {i}: {pass_config.get('description', key_type)}")

            df = self._add_blocking_key(df, key_type, col_name)

        return df

    def _add_blocking_key(
        self,
        df: DataFrame,
        key_type: str,
        col_name: str
    ) -> DataFrame:
        """
        Add blocking key column based on key type

        Args:
            df: Input DataFrame
            key_type: Type of blocking key to generate
            col_name: Name for blocking key column

        Returns:
            DataFrame with new blocking key column
        """
        if key_type == "soundex_lastname_dob_year":
            # High precision: Soundex(last_name) + DOB year
            df = df.withColumn(
                col_name,
                F.concat(
                    F.udf(lambda x: self.phonetic_encoder.soundex(x) if x else None)(F.col("last_name")),
                    F.lit("_"),
                    F.year(F.col("dob"))
                )
            )

        elif key_type == "first3_last3_dob":
            # Typo tolerance: First 3 chars of first/last name + DOB
            df = df.withColumn(
                col_name,
                F.concat(
                    F.substring(F.col("first_name"), 1, 3),
                    F.lit("_"),
                    F.substring(F.col("last_name"), 1, 3),
                    F.lit("_"),
                    F.date_format(F.col("dob"), "yyyy-MM-dd")
                )
            )

        elif key_type == "zip_metaphone_lastname":
            # Geographic: ZIP + Metaphone(last_name)
            # Note: Requires jellyfish library
            df = df.withColumn(
                col_name,
                F.concat(
                    F.col("zip_code"),
                    F.lit("_"),
                    F.udf(lambda x: self.phonetic_encoder.metaphone(x) if x else None)(F.col("last_name"))
                )
            )

        elif key_type == "ssn_last4_dob":
            # High confidence: Last 4 SSN + DOB
            df = df.withColumn(
                col_name,
                F.concat(
                    F.col("ssn_last4"),
                    F.lit("_"),
                    F.date_format(F.col("dob"), "yyyy-MM-dd")
                )
            )

        else:
            logger.warning(f"Unknown blocking key type: {key_type}")
            df = df.withColumn(col_name, F.lit(None))

        return df

    def get_blocking_efficiency(
        self,
        df: DataFrame,
        blocking_key_col: str = "blocking_key_1"
    ) -> Dict[str, Any]:
        """
        Calculate blocking efficiency metrics

        Args:
            df: DataFrame with blocking keys
            blocking_key_col: Column name of blocking key to analyze

        Returns:
            Dictionary with efficiency metrics
        """
        total_records = df.count()

        # Calculate block sizes
        block_stats = (
            df.groupBy(blocking_key_col)
            .agg(F.count("*").alias("block_size"))
            .select(
                F.avg("block_size").alias("avg_block_size"),
                F.max("block_size").alias("max_block_size"),
                F.min("block_size").alias("min_block_size"),
                F.count("*").alias("num_blocks")
            )
            .first()
        )

        avg_block_size = block_stats["avg_block_size"]
        num_blocks = block_stats["num_blocks"]

        # Calculate comparison reduction
        comparisons_without_blocking = (total_records * (total_records - 1)) // 2
        comparisons_with_blocking = (num_blocks * avg_block_size * (avg_block_size - 1)) // 2

        reduction_percent = (
            (comparisons_without_blocking - comparisons_with_blocking)
            / comparisons_without_blocking
            * 100
        )

        return {
            "total_records": total_records,
            "num_blocks": num_blocks,
            "avg_block_size": round(avg_block_size, 2),
            "max_block_size": block_stats["max_block_size"],
            "min_block_size": block_stats["min_block_size"],
            "comparisons_without_blocking": comparisons_without_blocking,
            "comparisons_with_blocking": int(comparisons_with_blocking),
            "reduction_percent": round(reduction_percent, 2),
        }


class BlockGenerator:
    """
    Generate record pairs within blocks for comparison

    After blocking, this class generates all pairwise combinations
    within each block for matching.
    """

    @staticmethod
    def generate_pairs(
        df: DataFrame,
        blocking_key_col: str,
        max_pairs_per_block: int = 10000
    ) -> DataFrame:
        """
        Generate record pairs within each block

        Args:
            df: DataFrame with blocking keys
            blocking_key_col: Column name of blocking key
            max_pairs_per_block: Maximum pairs to generate per block
                                 (prevents OOM on large blocks)

        Returns:
            DataFrame with pairs: (record_id_left, record_id_right, blocking_key)
        """
        # Self-join within blocks
        df_left = df.alias("left")
        df_right = df.alias("right")

        pairs = (
            df_left.join(
                df_right,
                (F.col(f"left.{blocking_key_col}") == F.col(f"right.{blocking_key_col}"))
                & (F.col("left.record_id") < F.col("right.record_id")),  # Avoid duplicates
                "inner"
            )
            .select(
                F.col("left.record_id").alias("record_id_left"),
                F.col("right.record_id").alias("record_id_right"),
                F.col(f"left.{blocking_key_col}").alias("blocking_key"),
            )
        )

        # Add pair count warning for large blocks
        pair_counts = (
            pairs.groupBy("blocking_key")
            .agg(F.count("*").alias("pair_count"))
        )

        large_blocks = pair_counts.filter(F.col("pair_count") > max_pairs_per_block)
        large_block_count = large_blocks.count()

        if large_block_count > 0:
            logger.warning(
                f"Found {large_block_count} blocks with >{max_pairs_per_block} pairs. "
                "These may need manual review or stricter blocking."
            )

        return pairs

    @staticmethod
    def sample_large_blocks(
        pairs: DataFrame,
        blocking_key_col: str = "blocking_key",
        max_pairs_per_block: int = 10000,
        sample_fraction: float = 0.1
    ) -> DataFrame:
        """
        Sample pairs from large blocks to prevent OOM

        Args:
            pairs: DataFrame with record pairs
            blocking_key_col: Blocking key column
            max_pairs_per_block: Threshold for "large" block
            sample_fraction: Fraction of pairs to sample from large blocks

        Returns:
            DataFrame with sampled pairs
        """
        # Identify large blocks
        block_sizes = (
            pairs.groupBy(blocking_key_col)
            .agg(F.count("*").alias("pair_count"))
        )

        large_blocks = (
            block_sizes
            .filter(F.col("pair_count") > max_pairs_per_block)
            .select(blocking_key_col)
        )

        # Split into large and small blocks
        large_block_pairs = pairs.join(large_blocks, blocking_key_col, "inner")
        small_block_pairs = pairs.join(large_blocks, blocking_key_col, "left_anti")

        # Sample large blocks
        sampled_large = large_block_pairs.sample(withReplacement=False, fraction=sample_fraction)

        logger.info(
            f"Sampled {sampled_large.count()} pairs from large blocks "
            f"(originally {large_block_pairs.count()})"
        )

        # Combine
        return small_block_pairs.union(sampled_large)


if __name__ == "__main__":
    # Example usage (requires PySpark context)
    print("Blocking strategy module loaded")
    print("Usage: blocking_strategy = BlockingStrategy(config)")
    print("       df_blocked = blocking_strategy.apply_blocking(df)")
