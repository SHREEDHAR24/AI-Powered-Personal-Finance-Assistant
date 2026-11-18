"""Fixed lists the rest of the app is allowed to use."""

EXPENSE_CATEGORIES = [
    "Food and Dining",
    "Groceries",
    "Transportation",
    "Rent",
    "Utilities",
    "Shopping",
    "Entertainment",
    "Healthcare",
    "Education",
    "Travel",
    "Subscriptions",
    "EMI and Loan Payments",
    "Personal Care",
    "Other",
]

INCOME_CATEGORIES = [
    "Salary",
    "Freelancing",
    "Business Income",
    "Scholarship",
    "Interest",
    "Investment Returns",
    "Other",
]

PAYMENT_METHODS = [
    "UPI",
    "Cash",
    "Debit Card",
    "Credit Card",
    "Net Banking",
    "Wallet",
    "Other",
]

CURRENCIES = ["INR", "USD", "EUR", "GBP"]

# Keyword layer for Indian bank narrations. First match wins.
# Each entry is (category name, transaction type, keywords).
KEYWORD_RULES: list[tuple[str, str, list[str]]] = [
    ("Food and Dining", "expense", [
        "swiggy", "zomato", "dominos", "domino", "mcdonald", "kfc", "starbucks",
        "restaurant", "cafe", "pizza", "burger", "foodpanda", "eatsure", "dineout",
    ]),
    ("Groceries", "expense", [
        "blinkit", "zepto", "bigbasket", "dmart", "d-mart", "grocery", "grofers",
        "reliance fresh", "more supermarket", "jiomart", "nature's basket",
    ]),
    ("Transportation", "expense", [
        "uber", "ola", "rapido", "irctc", "metro", "petrol", "fuel", "fastag",
        "indian oil", "hpcl", "bharat petroleum", "namma metro",
    ]),
    ("Rent", "expense", ["rent", "landlord", "house rent", "pg rent"]),
    ("Utilities", "expense", [
        "bescom", "electricity", "electric", "airtel", "jio", "vodafone", "bsnl",
        "water bill", "gas bill", "indane", "act fibernet", "broadband", "tata power",
    ]),
    ("Shopping", "expense", [
        "amazon", "flipkart", "myntra", "ajio", "meesho", "nykaa fashion", "ikea",
        "decathlon", "croma", "reliancedigital",
    ]),
    ("Entertainment", "expense", [
        "pvr", "inox", "bookmyshow", "movie", "steam", "playstation",
    ]),
    ("Healthcare", "expense", [
        "apollo", "pharmeasy", "1mg", "netmeds", "hospital", "pharmacy", "clinic",
        "diagnostic", "practo",
    ]),
    ("Education", "expense", [
        "udemy", "coursera", "college", "tuition", "unacademy", "byju", "school fee",
    ]),
    ("Travel", "expense", [
        "makemytrip", "goibibo", "air india", "indigo", "vistara", "hotel", "airbnb",
        "irctc hotel", "oyo",
    ]),
    ("Subscriptions", "expense", [
        "netflix", "spotify", "hotstar", "disney", "youtube premium", "prime video",
        "amazon prime",
        "apple.com/bill", "icloud", "google one", "chatgpt", "linkedin premium",
    ]),
    ("EMI and Loan Payments", "expense", [
        "emi", "loan", "bajaj finance", "home loan", "car loan",
    ]),
    ("Personal Care", "expense", ["nykaa", "salon", "urban company", "barber"]),
    ("Salary", "income", ["salary", "payroll", "stipend credit"]),
    ("Freelancing", "income", ["freelance", "upwork", "fiverr", "consulting fee"]),
    ("Business Income", "income", ["business income", "client payment", "invoice paid"]),
    ("Scholarship", "income", ["scholarship"]),
    ("Interest", "income", ["interest credit", "savings interest"]),
    ("Investment Returns", "income", ["dividend", "mutual fund redemption", "redemption"]),
]
