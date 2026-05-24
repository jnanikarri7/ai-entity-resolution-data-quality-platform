"""Splink integration for probabilistic record linkage

Splink implements the Fellegi-Sunter probabilistic matching algorithm:
- Calculates match weights for each field comparison
- Uses Expectation-Maximization (EM) to learn m and u probabilities
- Generates match scores and probabilities

Reference: https://github.com/moj-analytical-services/splink
"""

from typing import Dict, Any, List, Optional
import logging
from datetime import datetime

try:
    from splink.duckdb.linker import DuckDBLinker
    from splink.duckdb.comparison_library import (
        exact_match,
        levenshtein_at_thresholds,
        jaro_winkler_at_thresholds,
        jaccard_at_thresholds,
    )
    SPLINK_AVAILABLE = True
except ImportError:
    SPLINK_AVAILABLE = False
    logging.warning("Splink not available. Install with: pip install splink")

logger = logging.getLogger(__name__)


class SplinkMatcher:
    """
    Probabilistic record matching using Splink

    Implements Fellegi-Sunter algorithm with configurable comparison rules.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Splink matcher

        Args:
            config: Matching configuration with comparison rules and thresholds
        """
        if not SPLINK_AVAILABLE:
            raise ImportError("Splink library required. Install with: pip install splink")

        self.config = config
        self.threshold_match = config.get("threshold_match", 15.0)
        self.threshold_review = config.get("threshold_review", -5.0)
        self.comparison_columns = config.get("comparison_columns", [])

        self.linker = None
        self._build_settings()

    def _build_settings(self) -> Dict[str, Any]:
        """
        Build Splink settings from configuration

        Returns:
            Dictionary with Splink configuration
        """
        settings = {
            "link_type": "dedupe_only",
            "blocking_rules_to_generate_predictions": [
                # Use blocking keys from BlockingStrategy
                "l.blocking_key_1 = r.blocking_key_1",
                "l.blocking_key_2 = r.blocking_key_2",
                "l.blocking_key_3 = r.blocking_key_3",
            ],
            "comparisons": self._build_comparison_rules(),
            "retain_matching_columns": True,
            "retain_intermediate_calculation_columns": True,
        }

        self.settings = settings
        return settings

    def _build_comparison_rules(self) -> List[Dict[str, Any]]:
        """
        Build Splink comparison rules from configuration

        Returns:
            List of comparison dictionaries for Splink
        """
        comparisons = []

        for col_config in self.comparison_columns:
            col_name = col_config.get("name")
            weight = col_config.get("weight", 1.0)

            if col_name == "first_name":
                comparison = {
                    "output_column_name": "first_name",
                    "comparison_levels": [
                        {
                            "sql_condition": "first_name_l IS NULL OR first_name_r IS NULL",
                            "label_for_charts": "Null",
                            "is_null_level": True,
                        },
                        {
                            "sql_condition": "first_name_l = first_name_r",
                            "label_for_charts": "Exact match",
                            "m_probability": 0.9,
                        },
                        {
                            "sql_condition": "jaro_winkler_similarity(first_name_l, first_name_r) >= 0.9",
                            "label_for_charts": "Jaro-Winkler >= 0.9",
                            "m_probability": 0.7,
                        },
                        {
                            "sql_condition": "jaro_winkler_similarity(first_name_l, first_name_r) >= 0.8",
                            "label_for_charts": "Jaro-Winkler >= 0.8",
                            "m_probability": 0.4,
                        },
                        {
                            "sql_condition": "ELSE",
                            "label_for_charts": "All other comparisons",
                            "m_probability": 0.05,
                        },
                    ],
                }

            elif col_name == "last_name":
                comparison = {
                    "output_column_name": "last_name",
                    "comparison_levels": [
                        {
                            "sql_condition": "last_name_l IS NULL OR last_name_r IS NULL",
                            "label_for_charts": "Null",
                            "is_null_level": True,
                        },
                        {
                            "sql_condition": "last_name_l = last_name_r",
                            "label_for_charts": "Exact match",
                            "m_probability": 0.95,
                        },
                        {
                            "sql_condition": "levenshtein(last_name_l, last_name_r) <= 2",
                            "label_for_charts": "Levenshtein <= 2",
                            "m_probability": 0.7,
                        },
                        {
                            "sql_condition": "jaro_winkler_similarity(last_name_l, last_name_r) >= 0.85",
                            "label_for_charts": "Jaro-Winkler >= 0.85",
                            "m_probability": 0.5,
                        },
                        {
                            "sql_condition": "ELSE",
                            "label_for_charts": "All other comparisons",
                            "m_probability": 0.02,
                        },
                    ],
                }

            elif col_name == "dob":
                comparison = {
                    "output_column_name": "dob",
                    "comparison_levels": [
                        {
                            "sql_condition": "dob_l IS NULL OR dob_r IS NULL",
                            "label_for_charts": "Null",
                            "is_null_level": True,
                        },
                        {
                            "sql_condition": "dob_l = dob_r",
                            "label_for_charts": "Exact match",
                            "m_probability": 0.98,
                        },
                        {
                            "sql_condition": """
                                strftime('%d', dob_l) = strftime('%m', dob_r) AND
                                strftime('%m', dob_l) = strftime('%d', dob_r) AND
                                strftime('%Y', dob_l) = strftime('%Y', dob_r)
                            """,
                            "label_for_charts": "Day/Month transposed",
                            "m_probability": 0.5,
                        },
                        {
                            "sql_condition": "abs(julianday(dob_l) - julianday(dob_r)) <= 365",
                            "label_for_charts": "Within 1 year",
                            "m_probability": 0.2,
                        },
                        {
                            "sql_condition": "ELSE",
                            "label_for_charts": "All other comparisons",
                            "m_probability": 0.01,
                        },
                    ],
                }

            elif col_name == "address":
                comparison = {
                    "output_column_name": "address",
                    "comparison_levels": [
                        {
                            "sql_condition": "address_l IS NULL OR address_r IS NULL",
                            "label_for_charts": "Null",
                            "is_null_level": True,
                        },
                        {
                            "sql_condition": "address_l = address_r",
                            "label_for_charts": "Exact match",
                            "m_probability": 0.85,
                        },
                        {
                            "sql_condition": "jaccard(address_l, address_r) >= 0.8",
                            "label_for_charts": "Jaccard >= 0.8",
                            "m_probability": 0.6,
                        },
                        {
                            "sql_condition": "substr(zip_code_l, 1, 5) = substr(zip_code_r, 1, 5)",
                            "label_for_charts": "Same ZIP",
                            "m_probability": 0.3,
                        },
                        {
                            "sql_condition": "ELSE",
                            "label_for_charts": "All other comparisons",
                            "m_probability": 0.1,
                        },
                    ],
                }

            else:
                logger.warning(f"Unknown comparison column: {col_name}, using default rules")
                comparison = {
                    "output_column_name": col_name,
                    "comparison_levels": [
                        {
                            "sql_condition": f"{col_name}_l IS NULL OR {col_name}_r IS NULL",
                            "label_for_charts": "Null",
                            "is_null_level": True,
                        },
                        {
                            "sql_condition": f"{col_name}_l = {col_name}_r",
                            "label_for_charts": "Exact match",
                        },
                        {
                            "sql_condition": "ELSE",
                            "label_for_charts": "All other comparisons",
                        },
                    ],
                }

            comparisons.append(comparison)

        return comparisons

    def train_model(self, df_pandas):
        """
        Train Splink model using Expectation-Maximization

        Args:
            df_pandas: Pandas DataFrame with blocked records
        """
        logger.info("Training Splink model with EM algorithm")

        self.linker = DuckDBLinker(df_pandas, self.settings)

        # Estimate m and u probabilities using EM
        self.linker.estimate_u_using_random_sampling(max_pairs=1e6)

        # Run EM training
        training_blocking_rules = [
            "l.blocking_key_1 = r.blocking_key_1",
        ]

        for rule in training_blocking_rules:
            self.linker.estimate_parameters_using_expectation_maximisation(rule)

        logger.info("Model training complete")

    def predict_matches(self, df_pandas, threshold: Optional[float] = None):
        """
        Predict matches using trained model

        Args:
            df_pandas: Pandas DataFrame with records to match
            threshold: Match probability threshold (uses config default if None)

        Returns:
            Pandas DataFrame with match predictions
        """
        if self.linker is None:
            raise ValueError("Model not trained. Call train_model() first.")

        if threshold is None:
            threshold = self.threshold_match

        logger.info(f"Predicting matches with threshold: {threshold}")

        predictions = self.linker.predict(threshold_match_probability=threshold)
        df_predictions = predictions.as_pandas_dataframe()

        logger.info(f"Found {len(df_predictions)} potential matches")

        return df_predictions

    def explain_match(self, record_left: Dict[str, Any], record_right: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate explanation for a match

        Args:
            record_left: First record dictionary
            record_right: Second record dictionary

        Returns:
            Dictionary with field-by-field comparison and overall score
        """
        explanation = {
            "record_left": record_left,
            "record_right": record_right,
            "field_comparisons": {},
            "match_score": 0.0,
            "decision": "unknown",
        }

        # TODO: Implement detailed match explanation
        # For now, placeholder implementation

        return explanation

    def get_match_statistics(self, predictions_df) -> Dict[str, Any]:
        """
        Calculate statistics on match predictions

        Args:
            predictions_df: DataFrame with predictions from predict_matches()

        Returns:
            Dictionary with match statistics
        """
        stats = {
            "total_pairs": len(predictions_df),
            "matches": len(predictions_df[predictions_df["match_probability"] >= self.threshold_match]),
            "review": len(predictions_df[
                (predictions_df["match_probability"] >= self.threshold_review) &
                (predictions_df["match_probability"] < self.threshold_match)
            ]),
            "non_matches": len(predictions_df[predictions_df["match_probability"] < self.threshold_review]),
            "avg_match_probability": predictions_df["match_probability"].mean(),
            "match_rate": len(predictions_df[predictions_df["match_probability"] >= self.threshold_match]) / len(predictions_df),
        }

        # Confidence distribution
        stats["confidence_distribution"] = {
            "p90": predictions_df["match_probability"].quantile(0.9),
            "p50": predictions_df["match_probability"].quantile(0.5),
            "p10": predictions_df["match_probability"].quantile(0.1),
        }

        return stats


if __name__ == "__main__":
    print("Splink matcher module loaded")
    print("Usage:")
    print("  matcher = SplinkMatcher(config)")
    print("  matcher.train_model(df)")
    print("  predictions = matcher.predict_matches(df)")
