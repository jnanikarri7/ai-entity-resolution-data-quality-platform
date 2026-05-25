# Entity Resolution Platform - Architecture Diagram

## High-Level Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              SOURCE SYSTEMS                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────────┐  ┌────────────┐  ┌──────────┐   │
│  │Enrollment│  │  Claims  │  │     Case     │  │  Provider  │  │   EDI    │   │
│  │   DB     │  │    DB    │  │  Management  │  │   Portal   │  │  Files   │   │
│  └────┬─────┘  └────┬─────┘  └──────┬───────┘  └─────┬──────┘  └────┬─────┘   │
└───────┼─────────────┼───────────────┼────────────────┼──────────────┼─────────┘
        │             │               │                │              │
        └─────────────┴───────────────┴────────────────┴──────────────┘
                                      │
                                      ▼
        ┌─────────────────────────────────────────────────────────────┐
        │              AWS S3 - RAW ZONE (Bronze Layer)               │
        │                   Parquet Files - 50M Records               │
        │          Partitioned by: source_system / run_date           │
        └─────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                  AWS GLUE ETL JOB                           │
        │              (PySpark 3.3 + Python 3.9)                     │
        │                                                             │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │ STAGE 1: DATA INGESTION & VALIDATION                 │  │
        │  │  • Read Parquet files from S3                        │  │
        │  │  • Schema validation                                 │  │
        │  │  • Data quality checks (nulls, formats)              │  │
        │  │  • DLQ for invalid records                           │  │
        │  └──────────────────┬───────────────────────────────────┘  │
        │                     ▼                                       │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │ STAGE 2: PREPROCESSING & STANDARDIZATION             │  │
        │  │  (src/preprocessing/)                                │  │
        │  │                                                       │  │
        │  │  Names:     Mr. Robert Johnson → ROBERT JOHNSON      │  │
        │  │  Addresses: 123 Main St Apt 2B → 123 MAIN STREET #2B │  │
        │  │  Dates:     01/15/1985 → 1985-01-15                  │  │
        │  │  Phonetics: Johnson → J525 (Soundex), JNS (Metaphone)│  │
        │  └──────────────────┬───────────────────────────────────┘  │
        │                     ▼                                       │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │ STAGE 3: MULTI-PASS BLOCKING                         │  │
        │  │  (src/matching/blocking.py)                          │  │
        │  │                                                       │  │
        │  │  Pass 1: Soundex(last_name) + DOB_year               │  │
        │  │  Pass 2: First3(last) + First3(first) + DOB          │  │
        │  │  Pass 3: ZIP + Metaphone(last_name)                  │  │
        │  │  Pass 4: SSN_last4 + DOB                             │  │
        │  │                                                       │  │
        │  │  Reduction: 2.5 trillion → 200M comparisons          │  │
        │  │  (99.996% reduction)                                 │  │
        │  └──────────────────┬───────────────────────────────────┘  │
        │                     ▼                                       │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │ STAGE 4: PROBABILISTIC MATCHING                      │  │
        │  │  (src/matching/splink_matcher.py)                    │  │
        │  │                                                       │  │
        │  │  Algorithm: Fellegi-Sunter (via Splink)              │  │
        │  │                                                       │  │
        │  │  Compare pairs within each block:                    │  │
        │  │   • First name: Jaro-Winkler similarity              │  │
        │  │   • Last name: Levenshtein + Metaphone               │  │
        │  │   • DOB: Exact / day-month swap / year tolerance     │  │
        │  │   • Address: Token Jaccard / ZIP match               │  │
        │  │                                                       │  │
        │  │  Score: Σ log₂(m/u) per field                        │  │
        │  │   • Score ≥ 15  → MATCH                              │  │
        │  │   • -5 ≤ Score < 15 → REVIEW                         │  │
        │  │   • Score < -5  → NON-MATCH                          │  │
        │  └──────────────────┬───────────────────────────────────┘  │
        │                     ▼                                       │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │ STAGE 5: CLUSTERING                                  │  │
        │  │                                                       │  │
        │  │  Build entity graph:                                 │  │
        │  │   • Nodes = records                                  │  │
        │  │   • Edges = matches (score > threshold)              │  │
        │  │   • Connected components = entity clusters           │  │
        │  │                                                       │  │
        │  │  Handle transitive conflicts conservatively          │  │
        │  └──────────────────┬───────────────────────────────────┘  │
        │                     ▼                                       │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │ STAGE 6: SURVIVORSHIP & GOLDEN RECORDS              │  │
        │  │  (src/survivorship/rules.py)                         │  │
        │  │                                                       │  │
        │  │  Resolve conflicts per field:                        │  │
        │  │   • Name: most_common                                │  │
        │  │   • DOB: most_complete                               │  │
        │  │   • Address: most_recent                             │  │
        │  │   • SSN: source_trust (enrollment > claims)          │  │
        │  │                                                       │  │
        │  │  Output golden record per entity                     │  │
        │  └──────────────────┬───────────────────────────────────┘  │
        │                     ▼                                       │
        │  ┌──────────────────────────────────────────────────────┐  │
        │  │ STAGE 7: DATA QUALITY VALIDATION                     │  │
        │  │                                                       │  │
        │  │  Great Expectations checks:                          │  │
        │  │   • Unique golden_id                                 │  │
        │  │   • Match rate within expected range (60-80%)        │  │
        │  │   • Cluster size distribution                        │  │
        │  │   • Confidence score distribution                    │  │
        │  └──────────────────┬───────────────────────────────────┘  │
        └────────────────────┼───────────────────────────────────────┘
                             ▼
        ┌─────────────────────────────────────────────────────────────┐
        │       AWS S3 - CURATED ZONE (Silver Layer - Iceberg)        │
        │                                                             │
        │  ┌──────────────────┐  ┌──────────────────┐               │
        │  │  golden_records  │  │   match_pairs    │               │
        │  │                  │  │                  │               │
        │  │  • golden_id     │  │  • record_id_L   │               │
        │  │  • first_name    │  │  • record_id_R   │               │
        │  │  • last_name     │  │  • match_score   │               │
        │  │  • dob           │  │  • method        │               │
        │  │  • address       │  │  • comparison_   │               │
        │  │  • cluster_size  │  │    vector        │               │
        │  │  • confidence    │  │                  │               │
        │  └──────────────────┘  └──────────────────┘               │
        │                                                             │
        │  ┌──────────────────┐  ┌──────────────────┐               │
        │  │cluster_metadata  │  │   dq_metrics     │               │
        │  │                  │  │                  │               │
        │  │  • golden_id     │  │  • run_date      │               │
        │  │  • source_ids    │  │  • match_rate    │               │
        │  │  • create_date   │  │  • singleton_%   │               │
        │  │  • update_date   │  │  • avg_cluster   │               │
        │  └──────────────────┘  └──────────────────┘               │
        │                                                             │
        │  Partitioned by: run_date                                  │
        │  Format: Apache Iceberg (time travel, schema evolution)    │
        └─────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────────────────────────┐
        │                  QUERY & ANALYTICS LAYER                    │
        │                                                             │
        │  ┌──────────────┐        ┌──────────────┐                  │
        │  │ AWS Athena   │        │  Redshift    │                  │
        │  │              │        │  Spectrum    │                  │
        │  │  Serverless  │        │              │                  │
        │  │  SQL queries │        │  BI/Reports  │                  │
        │  └──────────────┘        └──────────────┘                  │
        └─────────────────────────────────────────────────────────────┘
```

## Component Breakdown

### 1. Source Systems
- **Type:** Heterogeneous databases and file systems
- **Volume:** 50M records total across 5 systems
- **Refresh:** Daily batch extracts
- **Format:** Exported to Parquet for processing

### 2. Raw Zone (Bronze Layer)
- **Storage:** AWS S3
- **Format:** Parquet (compressed with Snappy)
- **Partitioning:** By source_system and run_date
- **Retention:** 90 days (then archived to Glacier)

### 3. AWS Glue ETL Job
- **Compute:** Serverless PySpark (20 DPUs for 50M records)
- **Runtime:** Python 3.9, PySpark 3.3
- **Duration:** 2-3 hours for full run
- **Cost:** ~$11 per run ($0.44/DPU-hour × 20 DPUs × 2.5 hours)

### 4. Processing Stages

#### Stage 1: Ingestion
- Schema validation against expected format
- Reject malformed records to Dead Letter Queue (DLQ)
- Basic statistics collection

#### Stage 2: Preprocessing (src/preprocessing/)
- **Name standardization:** Remove titles, case normalization, parsing
- **Address standardization:** Abbreviation expansion, format normalization
- **Date parsing:** Multiple format support, ISO 8601 conversion
- **Phonetic encoding:** Soundex and Metaphone for fuzzy matching

#### Stage 3: Blocking (src/matching/blocking.py)
- **Purpose:** Reduce O(n²) comparison space
- **Method:** Multiple blocking passes with different keys
- **Result:** 99.996% comparison reduction (2.5T → 200M)
- **Output:** Candidate pairs for detailed comparison

#### Stage 4: Matching (src/matching/splink_matcher.py)
- **Algorithm:** Fellegi-Sunter probabilistic record linkage
- **Engine:** Splink library (UK gov, battle-tested)
- **Comparison:** Field-specific similarity functions
- **Scoring:** Bayesian m/u probability ratios
- **Output:** Match pairs with confidence scores

#### Stage 5: Clustering
- **Method:** Graph-based connected components
- **Input:** Match pairs (edges), records (nodes)
- **Output:** Entity clusters
- **Edge cases:** Transitive conflict resolution

#### Stage 6: Survivorship (src/survivorship/rules.py)
- **Purpose:** Select best value for each field from cluster
- **Strategies:** most_recent, most_common, source_trust, most_complete
- **Output:** One golden record per entity cluster

#### Stage 7: Validation
- **Framework:** Great Expectations
- **Checks:** Uniqueness, completeness, business rules
- **Action:** Fail pipeline or send alerts on violations

### 5. Curated Zone (Silver Layer)
- **Storage:** AWS S3 with Apache Iceberg table format
- **Format:** Parquet (Iceberg metadata)
- **Features:**
  - ACID transactions
  - Schema evolution
  - Time travel (historical queries)
  - Hidden partitioning
- **Tables:**
  - **golden_records:** Deduplicated entities
  - **match_pairs:** Audit trail of matches
  - **cluster_metadata:** Entity cluster info
  - **dq_metrics:** Data quality metrics per run

### 6. Query Layer
- **Athena:** Ad-hoc SQL queries, serverless
- **Redshift Spectrum:** BI tool integration, dashboards
- **Access:** JDBC/ODBC connections for downstream consumers

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Input volume | 50M records |
| Processing time | 2-3 hours |
| Throughput | ~300K records/min |
| Comparison reduction | 99.996% |
| Match rate | 60-65% |
| Precision | 95%+ |
| Recall | 92%+ |
| Cost per run | ~$11 |
| Cost per million | $0.54 |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Compute | AWS Glue (serverless Spark) |
| Processing | PySpark 3.3, Python 3.9 |
| Matching | Splink (Fellegi-Sunter) |
| Storage | AWS S3, Apache Iceberg |
| Format | Parquet (Snappy compression) |
| Query | Athena, Redshift Spectrum |
| Quality | Great Expectations |
| Orchestration | AWS Step Functions |
| IaC | Terraform |

## Data Flow Summary

```
Raw Records (50M)
    ↓ Validate & Standardize
Standardized Records (49.5M, 0.5M to DLQ)
    ↓ Multi-pass Blocking (99.996% reduction)
Candidate Pairs (200M comparisons)
    ↓ Probabilistic Matching (Fellegi-Sunter)
Matched Pairs (30M matches)
    ↓ Clustering (Connected Components)
Entity Clusters (18M clusters, avg 2.8 records/cluster)
    ↓ Survivorship Rules
Golden Records (18M unique entities)
    ↓ Validation & Output
Final Output: Iceberg Tables on S3
```

## Key Design Principles

1. **Configuration-driven:** Rules in YAML, not hardcoded
2. **Modular:** Each stage is independent, testable
3. **Observable:** Metrics at every stage
4. **Auditable:** Full lineage from source to golden record
5. **Scalable:** Designed for 50M→500M record growth
6. **Cost-optimized:** Serverless, pay-per-use
7. **Secure:** Encryption at rest and in transit, PII hashing

## Failure Handling

- **DLQ:** Invalid records quarantined for review
- **Checkpoints:** Resume from last successful stage
- **Idempotency:** Re-run safe (deterministic outputs)
- **Monitoring:** CloudWatch alerts on failures
- **Rollback:** Iceberg time travel for bad runs
