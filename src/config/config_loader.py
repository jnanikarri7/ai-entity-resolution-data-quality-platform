"""Configuration loader for entity resolution pipeline"""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv


class ConfigLoader:
    """Load and validate configuration from YAML and environment variables"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader

        Args:
            config_path: Path to config.yaml file. If None, uses default location.
        """
        # Load environment variables
        load_dotenv()

        # Determine config file path
        if config_path:
            self.config_path = Path(config_path)
        else:
            self.config_path = Path(__file__).parent / "config.yaml"

        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        # Load configuration
        with open(self.config_path, "r") as f:
            self.config = yaml.safe_load(f)

        # Load AWS configuration from environment
        self.aws_profile = os.getenv("AWS_PROFILE")
        self.aws_region = os.getenv("AWS_REGION", "us-east-1")
        self.s3_bucket = os.getenv("S3_BUCKET")
        self.glue_database = os.getenv("GLUE_DATABASE")

        self._validate_required_config()

    def _validate_required_config(self):
        """Validate that required configuration is present"""
        required_env = ["S3_BUCKET", "GLUE_DATABASE"]
        missing = [key for key in required_env if not os.getenv(key)]

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        required_config_keys = ["sources", "blocking", "matching", "output"]
        missing_keys = [key for key in required_config_keys if key not in self.config]

        if missing_keys:
            raise ValueError(
                f"Missing required config keys: {', '.join(missing_keys)}"
            )

    def get_sources(self) -> list:
        """Get list of data sources"""
        return self.config.get("sources", [])

    def get_blocking_config(self) -> Dict[str, Any]:
        """Get blocking configuration"""
        return self.config.get("blocking", {})

    def get_matching_config(self) -> Dict[str, Any]:
        """Get matching configuration"""
        return self.config.get("matching", {})

    def get_survivorship_config(self) -> Dict[str, Any]:
        """Get survivorship rules"""
        return self.config.get("survivorship", {})

    def get_output_config(self) -> Dict[str, Any]:
        """Get output configuration"""
        return self.config.get("output", {})

    def get_match_threshold(self) -> float:
        """Get match threshold"""
        return float(
            os.getenv("MATCH_THRESHOLD")
            or self.config.get("matching", {}).get("threshold_match", 15.0)
        )

    def get_review_threshold(self) -> float:
        """Get review threshold"""
        return float(
            os.getenv("REVIEW_THRESHOLD")
            or self.config.get("matching", {}).get("threshold_review", -5.0)
        )


if __name__ == "__main__":
    # Test configuration loading
    config = ConfigLoader()
    print(f"Loaded config from: {config.config_path}")
    print(f"S3 Bucket: {config.s3_bucket}")
    print(f"Glue Database: {config.glue_database}")
    print(f"Match Threshold: {config.get_match_threshold()}")
    print(f"Sources: {len(config.get_sources())}")
