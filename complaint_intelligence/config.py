from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PRODUCTS = ["Checking or savings account", "Credit card",
            "Money transfer, virtual currency, or money service"]
PRODUCT_NAMES = {PRODUCTS[0]: "Accounts", PRODUCTS[1]: "Credit cards", PRODUCTS[2]: "Transfers"}
START = "2024-01-01"
END = "2024-12-30"  # Exclusive: exactly 52 complete Monday-to-Sunday weeks.
TRAIN_END = "2024-07-01"
VALID_END = "2024-09-30"
STATE = "NY"
SEED = 42
API = "https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/"
ARCHIVE_PAGE = "https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/"
