"""
Generate synthetic test data for entity resolution testing.

Creates 1,000 records with intentional duplicates representing:
- Exact duplicates (same person, identical data)
- Near duplicates (same person, slight variations)
- Non-matches (different people with similar names)
"""

import pandas as pd
import random
from datetime import datetime, timedelta
import hashlib
import uuid

# Set seed for reproducibility
random.seed(42)

# Sample data pools
FIRST_NAMES = [
    "Robert", "Bob", "Bobby", "Rob",
    "Jennifer", "Jen", "Jenny", "Jennifer",
    "Michael", "Mike", "Michael", "Mikey",
    "Elizabeth", "Liz", "Beth", "Lizzy",
    "William", "Bill", "Will", "Billy",
    "Mary", "Marie", "Maria",
    "James", "Jim", "Jimmy", "James",
    "Patricia", "Pat", "Patty", "Patricia",
    "John", "Jon", "Johnny",
    "Linda", "Lynn", "Lynda"
]

LAST_NAMES = [
    "Johnson", "Jonson", "Johnston",
    "Smith", "Smyth", "Smithe",
    "Williams", "Willams", "Williamson",
    "Brown", "Browne", "Browning",
    "Jones", "Jonas", "Jone",
    "Garcia", "Garsia", "Garcea",
    "Miller", "Millar", "Mills",
    "Davis", "Davies", "Davids",
    "Rodriguez", "Rodriquez", "Rodrigues",
    "Martinez", "Martines", "Martinz"
]

STREETS = [
    "Main St", "Main Street", "MAIN ST",
    "Oak Ave", "Oak Avenue", "OAK AVE",
    "Elm Street", "Elm St", "ELM STREET",
    "Maple Dr", "Maple Drive", "MAPLE DR",
    "Pine Rd", "Pine Road", "PINE RD"
]

CITIES = ["Baltimore", "Silver Spring", "Bethesda", "Rockville", "Annapolis"]
STATES = ["MD", "Maryland", "MD"]
ZIP_CODES = ["21201", "20910", "20814", "20850", "21401"]

SOURCE_SYSTEMS = ["enrollment", "claims", "case_management", "provider_portal", "edi_files"]


def generate_base_person():
    """Generate a base person record."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    dob = datetime(
        random.randint(1950, 2005),
        random.randint(1, 12),
        random.randint(1, 28)
    )

    street_num = random.randint(100, 9999)
    street = random.choice(STREETS)
    apt_num = random.choice([None, None, None, f"Apt {random.randint(1, 99)}", f"#{random.randint(1, 99)}"])

    city_idx = random.randint(0, len(CITIES) - 1)
    city = CITIES[city_idx]
    state = random.choice(STATES)
    zip_code = ZIP_CODES[city_idx]

    ssn = f"{random.randint(100, 999)}-{random.randint(10, 99)}-{random.randint(1000, 9999)}"

    return {
        "first_name": first_name,
        "last_name": last_name,
        "dob": dob,
        "street_num": street_num,
        "street": street,
        "apt_num": apt_num,
        "city": city,
        "state": state,
        "zip_code": zip_code,
        "ssn": ssn,
        "phone": f"({random.randint(200, 999)}) {random.randint(100, 999)}-{random.randint(1000, 9999)}",
        "email": f"{first_name.lower()}.{last_name.lower()}@example.com"
    }


def create_variation(person, variation_type):
    """Create a variation of a person record."""
    record = person.copy()

    if variation_type == "exact":
        # Exact duplicate - no changes
        pass

    elif variation_type == "name_case":
        # Change case
        record["first_name"] = record["first_name"].upper()
        record["last_name"] = record["last_name"].upper()

    elif variation_type == "name_nickname":
        # Use nickname
        name_map = {
            "Robert": "Bob", "Jennifer": "Jen", "Michael": "Mike",
            "Elizabeth": "Liz", "William": "Bill", "James": "Jim",
            "Patricia": "Pat", "John": "Jon"
        }
        if record["first_name"] in name_map:
            record["first_name"] = name_map[record["first_name"]]

    elif variation_type == "address_format":
        # Change address format
        if "Street" in record["street"]:
            record["street"] = record["street"].replace("Street", "St")
        elif "St" in record["street"]:
            record["street"] = record["street"].replace("St", "Street")

        if record["apt_num"] and "Apt" in record["apt_num"]:
            record["apt_num"] = record["apt_num"].replace("Apt", "#")

    elif variation_type == "address_minor":
        # Move to different apartment
        if record["apt_num"]:
            # Extract number from either "Apt 5" or "#5" format
            num_str = record["apt_num"].split()[-1].replace("#", "")
            try:
                apt_num = int(num_str)
                record["apt_num"] = f"Apt {apt_num + 1}"
            except ValueError:
                # If can't parse, just change format
                record["apt_num"] = f"#{random.randint(1, 99)}"

    elif variation_type == "typo":
        # Introduce typo in last name
        name = record["last_name"]
        if len(name) > 4:
            pos = random.randint(1, len(name) - 2)
            name_list = list(name)
            # Swap two adjacent characters
            name_list[pos], name_list[pos + 1] = name_list[pos + 1], name_list[pos]
            record["last_name"] = "".join(name_list)

    elif variation_type == "date_format":
        # Keep same date, just mark as different source
        pass

    return record


def create_record(person, source_system, record_id):
    """Create a full record with metadata."""
    # Hash SSN for privacy
    ssn_hash = hashlib.sha256(person["ssn"].encode()).hexdigest()
    ssn_last4 = person["ssn"][-4:]

    # Build address
    address_line1 = f"{person['street_num']} {person['street']}"
    address_line2 = person["apt_num"] if person["apt_num"] else ""

    # Create timestamps
    base_date = datetime(2024, 1, 1)
    created_offset = timedelta(days=random.randint(0, 365))
    updated_offset = timedelta(days=random.randint(0, 30))

    return {
        "source_system_id": source_system,
        "source_record_id": f"{source_system}_{record_id}",
        "first_name": person["first_name"],
        "middle_name": random.choice(["", "", "A", "J", "M", "L"]),
        "last_name": person["last_name"],
        "dob": person["dob"].strftime("%Y-%m-%d"),
        "ssn_hash": ssn_hash,
        "ssn_last4": ssn_last4,
        "address_line1": address_line1,
        "address_line2": address_line2,
        "city": person["city"],
        "state": person["state"],
        "zip_code": person["zip_code"],
        "phone": person["phone"],
        "email": person["email"],
        "created_date": (base_date + created_offset).isoformat(),
        "updated_date": (base_date + created_offset + updated_offset).isoformat(),
        "ingestion_timestamp": datetime.now().isoformat()
    }


def generate_dataset(num_entities=250):
    """
    Generate a dataset with intentional duplicates.

    Strategy:
    - 250 unique entities
    - Each entity has 2-5 records across different source systems
    - Total ~1000 records
    - Mix of exact duplicates, near duplicates, and variations
    """
    records = []
    record_id = 1

    for entity_id in range(num_entities):
        # Generate base person
        base_person = generate_base_person()

        # Determine how many duplicates (2-5)
        num_duplicates = random.randint(2, 5)

        # Variation types for this entity
        variation_types = random.sample(
            ["exact", "name_case", "name_nickname", "address_format",
             "address_minor", "typo", "date_format"],
            min(num_duplicates, 7)
        )

        # Create records for this entity
        for i in range(num_duplicates):
            # Select source system (different for each record)
            source_system = random.choice(SOURCE_SYSTEMS)

            # Create variation
            if i == 0:
                # First record is close to original
                person = base_person
            else:
                variation_type = variation_types[i % len(variation_types)]
                person = create_variation(base_person, variation_type)

            # Create full record
            record = create_record(person, source_system, record_id)
            records.append(record)
            record_id += 1

    return pd.DataFrame(records)


if __name__ == "__main__":
    print("Generating sample dataset...")
    df = generate_dataset(num_entities=250)

    print(f"Generated {len(df)} records representing ~250 unique entities")
    print(f"Average records per entity: {len(df) / 250:.1f}")

    # Save to CSV and Parquet (if pyarrow available)
    csv_path = "tests/data/sample_input.csv"
    df.to_csv(csv_path, index=False)
    print(f"\nSaved to CSV: {csv_path}")

    try:
        parquet_path = "tests/data/sample_input.parquet"
        df.to_parquet(parquet_path, index=False)
        print(f"Saved to Parquet: {parquet_path}")
    except ImportError:
        print("Note: Parquet export skipped (pyarrow not installed)")
        print("Install with: pip install pyarrow")

    # Print sample
    print("\n=== Sample Records ===")
    print(df[["source_system_id", "first_name", "last_name", "dob", "address_line1"]].head(10))

    # Print statistics
    print("\n=== Dataset Statistics ===")
    print(f"Total records: {len(df)}")
    print(f"Source systems: {df['source_system_id'].value_counts().to_dict()}")
    print(f"Unique names: {df['first_name'].nunique()} first names, {df['last_name'].nunique()} last names")
    print(f"Date range: {df['dob'].min()} to {df['dob'].max()}")
