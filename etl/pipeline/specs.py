"""Declarative spec per table: types, keys, canonical domains, uniqueness policies and lineage hints.

Types, NOT NULL columns, closed domains and ranges come from the organizer's
LATAM_Bank_Complete_Data_Dictionary; deviations the data forces (nullable registration_branch_id,
nullable employee_code after conflict resolution, transcript duration nulls) are listed in
docs/etl_rules.md. Everything else in the pipeline (SQL stages, Pandera contracts, tests) is generated
from these specs, so adding a rule means editing data here, not code.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CURRENCIES = ("MXN", "COP", "ARS", "USD")
COUNTRIES3 = ("Mexico", "Colombia", "Argentina")


@dataclass(frozen=True)
class BizKey:
    """A business key that must identify one row (docs/etl_rules.md, rules B2-B7).

    policy 'keep_first': the row with the lowest order_by keeps the value; later rows get NULL + flag.
    policy 'null_all':   every row sharing the value gets NULL + flag (no way to pick an owner).
    expr: SQL over the raw column used to compare (defaults to the column itself).
    """

    column: str
    policy: str  # keep_first | null_all
    flag: str
    order_by: str = ""  # required for keep_first; ties broken by the table's primary key
    expr: str = ""

    def group_expr(self) -> str:
        return self.expr or self.column


@dataclass(frozen=True)
class TableSpec:
    types: dict[str, str]  # column -> DuckDB type (raw column names, pre-rename)
    pk: tuple[str, ...]
    event: str | None = None  # business event timestamp; process_date is only the load watermark
    partitioned_raw: bool = True  # hive year=/month=/day= layout under data/raw/<table>/
    partitioned_silver: bool = False  # silver written as year=YYYY/month=MM parquet partitions
    dedup_order: str = ""  # column deciding the winner among PK duplicates (latest wins)
    not_null: tuple[str, ...] = ()
    standardize: dict[str, str] = field(default_factory=dict)  # column -> mappings.MAPPINGS key
    isin: dict[str, tuple[str, ...]] = field(default_factory=dict)  # post-standardization domains
    ranges: dict[str, tuple[float | None, float | None]] = field(default_factory=dict)
    business_keys: tuple[BizKey, ...] = ()
    drop: tuple[str, ...] = ()  # removed from silver (normalized into a dim, or PII)
    rename: dict[str, str] = field(default_factory=dict)
    content_dup_check: bool = True  # same content under a different PK -> quarantine
    depends_on: tuple[str, ...] = ()  # silver tables that must exist before this one runs


EMAIL_EXPR = "lower(trim({c}))"
PHONE_EXPR = "regexp_replace({c}, '[^0-9]', '', 'g')"

TABLES: dict[str, TableSpec] = {
    "branches": TableSpec(
        types={
            "branch_id": "VARCHAR", "branch_code": "VARCHAR", "branch_name": "VARCHAR",
            "branch_type": "VARCHAR", "address": "VARCHAR", "city": "VARCHAR", "state": "VARCHAR",
            "country": "VARCHAR", "postal_code": "VARCHAR", "geographic_zone": "VARCHAR",
            "phone": "VARCHAR", "email": "VARCHAR", "opening_time": "TIME", "closing_time": "TIME",
            "has_atms": "BOOLEAN", "atm_count": "BIGINT", "has_teller_windows": "BOOLEAN",
            "teller_window_count": "BIGINT", "latitude": "DOUBLE", "longitude": "DOUBLE",
            "branch_opening_date": "DATE", "branch_status": "VARCHAR",
        },
        pk=("branch_id",),
        partitioned_raw=False,
        not_null=("branch_id", "branch_code", "branch_name", "branch_type", "address", "city",
                  "country", "geographic_zone", "phone", "opening_time", "closing_time", "has_atms",
                  "has_teller_windows", "branch_opening_date", "branch_status"),
        standardize={"country": "country", "geographic_zone": "geographic_zone"},
        isin={
            "branch_type": ("Main", "Express", "Premium", "Corporate"),
            "geographic_zone": ("Urban", "Suburban", "Rural"),
            "country": COUNTRIES3,
            "branch_status": ("Active", "Temporarily Closed", "Closed"),
        },
        ranges={"atm_count": (0, None), "teller_window_count": (0, None)},
        business_keys=(BizKey("branch_code", "keep_first", "branch_code_conflict", "branch_opening_date"),),
        drop=("state",),  # 3NF: city -> state lives in dim_cities
    ),
    "service_agents": TableSpec(
        types={
            "agent_id": "VARCHAR", "employee_code": "VARCHAR", "first_name": "VARCHAR",
            "last_name": "VARCHAR", "email": "VARCHAR", "phone": "VARCHAR",
            "native_accent": "VARCHAR", "country_of_origin": "VARCHAR",
            "assigned_branch_id": "VARCHAR", "agent_type": "VARCHAR", "experience_level": "VARCHAR",
            "languages": "VARCHAR", "specialty": "VARCHAR", "hire_date": "DATE",
            "avg_csat": "DOUBLE", "total_monthly_interactions": "BIGINT",
            "agent_status": "VARCHAR", "work_shift": "VARCHAR",
        },
        pk=("agent_id",),
        partitioned_raw=False,
        # employee_code and email are NOT NULL + UNIQUE in the dictionary; conflict losers keep the
        # row but lose the value (rule B2/B6), so silver leaves them nullable and flags them.
        not_null=("agent_id", "first_name", "last_name", "native_accent", "country_of_origin",
                  "agent_type", "experience_level", "languages", "hire_date", "agent_status", "work_shift"),
        standardize={"country_of_origin": "country"},
        isin={
            "country_of_origin": COUNTRIES3,
            "agent_type": ("Phone", "In-Person", "Digital", "Hybrid"),
            "experience_level": ("Junior", "Mid-Senior", "Senior", "Specialist"),
            "agent_status": ("Active", "Vacation", "Leave", "Inactive"),
            "work_shift": ("Morning", "Afternoon", "Night", "Rotating"),
        },
        ranges={"avg_csat": (1, 5), "total_monthly_interactions": (0, None)},
        business_keys=(
            BizKey("employee_code", "keep_first", "employee_code_conflict", "hire_date"),
            BizKey("email", "keep_first", "email_conflict", "hire_date", expr=EMAIL_EXPR),
        ),
        depends_on=("branches",),  # assigned_branch_id resolution
    ),
    "customers": TableSpec(
        types={
            "customer_id": "VARCHAR", "document_number": "VARCHAR", "document_type": "VARCHAR",
            "first_name": "VARCHAR", "last_name": "VARCHAR", "date_of_birth": "DATE",
            "gender": "VARCHAR", "email": "VARCHAR", "mobile_phone": "VARCHAR",
            "landline_phone": "VARCHAR", "address": "VARCHAR", "city": "VARCHAR", "state": "VARCHAR",
            "country": "VARCHAR", "postal_code": "VARCHAR", "detected_accent": "VARCHAR",
            "segment": "VARCHAR", "credit_score": "BIGINT", "estimated_monthly_income": "DOUBLE",
            "occupation": "VARCHAR", "marital_status": "VARCHAR", "education_level": "VARCHAR",
            "registration_date": "TIMESTAMP", "registration_branch_id": "VARCHAR",
            "customer_status": "VARCHAR", "last_updated": "TIMESTAMP", "accepts_marketing": "BOOLEAN",
        },
        pk=("customer_id",),
        partitioned_raw=False,
        dedup_order="last_updated",
        # registration_branch_id is FK NOT NULL in the dictionary but ~100% unresolved (rule D4):
        # silver nulls it and flags branch_unresolved instead of dropping every customer.
        not_null=("customer_id", "document_number", "document_type", "first_name", "last_name",
                  "date_of_birth", "city", "country", "segment", "registration_date",
                  "customer_status", "last_updated", "accepts_marketing"),
        standardize={"document_type": "document_type", "country": "country"},
        isin={
            "document_type": ("DNI", "CURP", "CC", "CE", "Passport"),
            "gender": ("M", "F", "O"),
            "country": COUNTRIES3,
            "segment": ("Premium", "Plus", "Basic", "Student"),
            "customer_status": ("Active", "Inactive", "Suspended", "Closed"),
        },
        ranges={"credit_score": (300, 850)},
        business_keys=(
            BizKey("document_number", "keep_first", "document_conflict", "registration_date"),
            BizKey("email", "null_all", "email_shared", expr=EMAIL_EXPR),
            BizKey("mobile_phone", "null_all", "mobile_phone_shared", expr=PHONE_EXPR),
            BizKey("landline_phone", "null_all", "landline_phone_shared", expr=PHONE_EXPR),
        ),
        drop=("state",),
        depends_on=("branches", "service_agents"),  # branch resolution + agent-phone check
    ),
    "products": TableSpec(
        types={
            "product_id": "VARCHAR", "customer_id": "VARCHAR", "product_type": "VARCHAR",
            "product_number": "VARCHAR", "currency": "VARCHAR", "current_balance": "DOUBLE",
            "credit_limit": "DOUBLE", "interest_rate": "DOUBLE", "opening_date": "DATE",
            "expiration_date": "DATE", "opening_branch_id": "VARCHAR", "product_status": "VARCHAR",
            "opening_channel": "VARCHAR", "has_linked_app": "BOOLEAN", "days_past_due": "BIGINT",
            "last_transaction_date": "TIMESTAMP", "last_updated": "TIMESTAMP",
        },
        pk=("product_id",),
        partitioned_raw=False,
        dedup_order="last_updated",
        not_null=("product_id", "customer_id", "product_type", "currency", "current_balance",
                  "opening_date", "opening_branch_id", "product_status", "opening_channel",
                  "has_linked_app", "last_updated"),
        standardize={"product_type": "product_type"},
        isin={
            "product_type": ("Checking Account", "Savings Account", "Credit Card", "Debit Card",
                             "Personal Loan", "Mortgage", "Investment", "Insurance"),
            "currency": CURRENCIES,
            "product_status": ("Active", "Blocked", "Closed", "Suspended"),
            "opening_channel": ("Branch", "Web", "App", "Call Center"),
        },
        ranges={"days_past_due": (0, None)},
        business_keys=(BizKey("product_number", "keep_first", "product_number_conflict", "opening_date"),),
        drop=("product_number",),  # only card_last4 + card_brand survive (hard rule: no card numbers)
        depends_on=("customers",),
    ),
    "marketing_campaigns": TableSpec(
        types={
            "campaign_id": "VARCHAR", "campaign_name": "VARCHAR", "description": "VARCHAR",
            "campaign_type": "VARCHAR", "campaign_objective": "VARCHAR", "promoted_product": "VARCHAR",
            "target_segment": "VARCHAR", "target_country": "VARCHAR", "start_date": "DATE",
            "end_date": "DATE", "budget": "DOUBLE", "campaign_status": "VARCHAR",
            "expected_conversion_rate": "DOUBLE",
        },
        pk=("campaign_id",),
        partitioned_raw=False,
        not_null=("campaign_id", "campaign_name", "campaign_type", "campaign_objective",
                  "start_date", "end_date", "campaign_status"),
        standardize={"promoted_product": "product_type", "target_country": "country"},
        isin={
            "campaign_type": ("Email", "SMS", "Push", "WhatsApp", "Voice", "Mix"),
            "campaign_objective": ("Acquisition", "Retention", "Cross-sell", "Up-sell", "Reactivation"),
            "target_country": COUNTRIES3,
            "campaign_status": ("Planned", "Active", "Paused", "Completed"),
        },
    ),
    "daily_exchange_rates": TableSpec(
        types={
            "date": "DATE", "source_currency": "VARCHAR", "target_currency": "VARCHAR",
            "exchange_rate": "DOUBLE", "buy_rate": "DOUBLE", "sell_rate": "DOUBLE", "source": "VARCHAR",
        },
        pk=("date", "source_currency", "target_currency"),
        partitioned_raw=False,
        not_null=("date", "source_currency", "target_currency", "exchange_rate"),
        isin={"source_currency": CURRENCIES, "target_currency": CURRENCIES},
        ranges={"exchange_rate": (0, None)},
        rename={"date": "rate_date"},
        content_dup_check=False,  # natural key: equal rates on different days are legitimate
    ),
    "transactions": TableSpec(
        types={
            "transaction_id": "VARCHAR", "transaction_date": "TIMESTAMP", "process_date": "DATE",
            "product_id": "VARCHAR", "customer_id": "VARCHAR", "transaction_type": "VARCHAR",
            "transaction_category": "VARCHAR", "amount": "DOUBLE", "currency": "VARCHAR",
            "amount_usd": "DOUBLE", "channel": "VARCHAR", "branch_id": "VARCHAR",
            "merchant_name": "VARCHAR", "merchant_category": "VARCHAR",
            "transaction_country": "VARCHAR", "transaction_city": "VARCHAR",
            "transaction_status": "VARCHAR", "response_code": "VARCHAR", "is_fraud": "BOOLEAN",
            "fraud_score": "DOUBLE", "latitude": "DOUBLE", "longitude": "DOUBLE",
        },
        pk=("transaction_id",),
        event="transaction_date",
        partitioned_silver=True,
        dedup_order="process_date",
        not_null=("transaction_id", "transaction_date", "process_date", "product_id", "customer_id",
                  "transaction_type", "amount", "currency", "channel", "transaction_country",
                  "transaction_status", "is_fraud"),
        standardize={"transaction_country": "country"},
        isin={
            "transaction_type": ("Deposit", "Withdrawal", "Transfer", "Payment", "Purchase", "Adjustment"),
            "currency": CURRENCIES,
            "channel": ("ATM", "Branch", "Web", "App", "POS", "Transfer"),
            "transaction_status": ("Approved", "Declined", "Pending", "Reversed"),
        },
        ranges={"amount": (0, None), "fraud_score": (0, 100)},
        drop=("merchant_category",),  # 3NF: merchant_name -> category lives in dim_merchants
        depends_on=("customers", "products", "daily_exchange_rates"),
    ),
    "call_center_interactions": TableSpec(
        types={
            "interaction_id": "VARCHAR", "interaction_date": "TIMESTAMP", "process_date": "DATE",
            "customer_id": "VARCHAR", "agent_id": "VARCHAR", "interaction_type": "VARCHAR",
            "channel": "VARCHAR", "contact_reason": "VARCHAR", "reason_category": "VARCHAR",
            "duration_seconds": "DOUBLE", "wait_time_seconds": "DOUBLE", "was_resolved": "BOOLEAN",
            "requires_followup": "BOOLEAN", "detected_sentiment": "VARCHAR",
            "sentiment_score": "DOUBLE", "customer_detected_accent": "VARCHAR",
            "agent_used_accent": "VARCHAR", "was_escalated": "BOOLEAN",
            "mentioned_products": "VARCHAR", "has_transcript": "BOOLEAN", "has_recording": "BOOLEAN",
        },
        pk=("interaction_id",),
        event="interaction_date",
        dedup_order="process_date",
        not_null=("interaction_id", "interaction_date", "process_date", "customer_id",
                  "interaction_type", "channel", "reason_category", "requires_followup",
                  "was_escalated", "has_transcript", "has_recording"),
        standardize={"reason_category": "reason_category", "detected_sentiment": "sentiment"},
        isin={
            "interaction_type": ("Inbound Call", "Outbound Call", "Chat", "Email", "Video"),
            "channel": ("Phone", "Web Chat", "WhatsApp", "Email", "App", "Web"),  # Web: team extension
            "reason_category": ("Transactional", "Product", "Complaint", "Technical", "Commercial", "Retention"),
            "detected_sentiment": ("Very Positive", "Positive", "Neutral", "Negative", "Very Negative"),
        },
        ranges={"duration_seconds": (0, None), "wait_time_seconds": (0, None), "sentiment_score": (-1, 1)},
        drop=("contact_reason",),  # 3NF: byte-identical to reason_category in all 686k rows
    ),
    "call_transcripts": TableSpec(
        types={
            "transcript_id": "VARCHAR", "interaction_id": "VARCHAR", "process_date": "DATE",
            "customer_id": "VARCHAR", "agent_id": "VARCHAR", "full_text": "VARCHAR",
            "customer_text": "VARCHAR", "agent_text": "VARCHAR", "detected_language": "VARCHAR",
            "detected_accent": "VARCHAR", "accent_confidence": "DOUBLE",
            "detected_keywords": "VARCHAR", "mentioned_entities": "VARCHAR",
            "detected_intents": "VARCHAR", "main_topics": "VARCHAR", "transcription_model": "VARCHAR",
            "audio_quality": "VARCHAR", "duration_seconds": "DOUBLE",
        },
        pk=("transcript_id",),
        dedup_order="process_date",
        # duration_seconds is NOT NULL in the dictionary but null in 14% of rows: kept nullable and
        # reported as a dictionary violation in quality_findings rather than quarantining 24k rows.
        not_null=("transcript_id", "interaction_id", "process_date", "customer_id", "agent_id",
                  "full_text", "detected_language", "transcription_model"),
        standardize={"main_topics": "reason_category"},
        isin={"detected_language": ("es", "pt"), "audio_quality": ("High", "Medium", "Low")},
        ranges={"accent_confidence": (0, 1), "duration_seconds": (0, None)},
        depends_on=("call_center_interactions",),
    ),
    "satisfaction_surveys": TableSpec(
        types={
            "survey_id": "VARCHAR", "survey_date": "TIMESTAMP", "process_date": "DATE",
            "interaction_id": "VARCHAR", "customer_id": "VARCHAR", "agent_id": "VARCHAR",
            "survey_type": "VARCHAR", "send_channel": "VARCHAR", "main_score": "BIGINT",
            "nps_category": "VARCHAR", "question_1_text": "VARCHAR", "question_1_response": "BIGINT",
            "question_2_text": "VARCHAR", "question_2_response": "BIGINT",
            "question_3_text": "VARCHAR", "question_3_response": "BIGINT",
            "open_comments": "VARCHAR", "comment_sentiment": "VARCHAR",
            "response_time_hours": "DOUBLE", "campaign_response_rate": "DOUBLE",
        },
        pk=("survey_id",),
        event="survey_date",
        dedup_order="process_date",
        not_null=("survey_id", "survey_date", "process_date", "customer_id", "survey_type",
                  "send_channel", "main_score"),
        isin={
            "survey_type": ("CSAT", "NPS", "CES"),
            "send_channel": ("Email", "SMS", "IVR", "App", "Web"),
            "nps_category": ("Promoter", "Passive", "Detractor"),
            "comment_sentiment": ("Positive", "Neutral", "Negative"),
        },
        ranges={"main_score": (0, 10), "question_1_response": (1, 5), "question_2_response": (1, 5),
                "question_3_response": (1, 5), "response_time_hours": (0, None)},
        depends_on=("call_center_interactions",),
    ),
    "complaints": TableSpec(
        types={
            "complaint_id": "VARCHAR", "creation_date": "TIMESTAMP", "process_date": "DATE",
            "customer_id": "VARCHAR", "case_type": "VARCHAR", "category": "VARCHAR",
            "subcategory": "VARCHAR", "reception_channel": "VARCHAR",
            "affected_product_id": "VARCHAR", "related_branch_id": "VARCHAR",
            "origin_interaction_id": "VARCHAR", "description": "VARCHAR",
            "claimed_amount": "DOUBLE", "currency": "VARCHAR", "priority": "VARCHAR",
            "status": "VARCHAR", "assigned_agent_id": "VARCHAR", "assignment_date": "TIMESTAMP",
            "first_response_date": "TIMESTAMP", "resolution_date": "TIMESTAMP",
            "closing_date": "TIMESTAMP", "sla_breached": "BOOLEAN", "resolution_days": "BIGINT",
            "resolution": "VARCHAR", "compensation_granted": "DOUBLE",
            "resolution_satisfaction": "BIGINT", "is_repeat_complainer": "BOOLEAN",
        },
        pk=("complaint_id",),
        event="creation_date",
        dedup_order="process_date",
        not_null=("complaint_id", "creation_date", "process_date", "customer_id", "case_type",
                  "category", "reception_channel", "description", "priority", "status",
                  "sla_breached", "is_repeat_complainer"),
        isin={
            "case_type": ("Complaint", "Claim", "Request", "Suggestion"),
            "category": ("Transactions", "Fees", "Technical", "Service", "Branch"),
            "reception_channel": ("Call Center", "Email", "Web", "App", "Branch", "Regulator"),
            "currency": CURRENCIES,
            "priority": ("Low", "Medium", "High", "Critical"),
            "status": ("Open", "In Process", "Escalated", "Resolved", "Closed", "Rejected"),
        },
        ranges={"claimed_amount": (0, None), "resolution_days": (0, None),
                "compensation_granted": (0, None), "resolution_satisfaction": (1, 5)},
        drop=("subcategory",),  # 3NF: 1:1 with category, kept in dim_categories for display
    ),
    "campaign_sends": TableSpec(
        types={
            "send_id": "VARCHAR", "send_date": "TIMESTAMP", "process_date": "DATE",
            "campaign_id": "VARCHAR", "customer_id": "VARCHAR", "send_channel": "VARCHAR",
            "template_used": "VARCHAR", "subject": "VARCHAR", "send_status": "VARCHAR",
            "was_delivered": "BOOLEAN", "was_opened": "BOOLEAN", "open_date": "TIMESTAMP",
            "was_clicked": "BOOLEAN", "click_date": "TIMESTAMP", "click_count": "BIGINT",
            "had_conversion": "BOOLEAN", "conversion_date": "TIMESTAMP",
            "conversion_value": "DOUBLE", "open_device": "VARCHAR", "open_country": "VARCHAR",
            "failure_reason": "VARCHAR", "send_cost": "DOUBLE",
        },
        pk=("send_id",),
        event="send_date",
        dedup_order="process_date",
        not_null=("send_id", "send_date", "process_date", "campaign_id", "customer_id",
                  "send_channel", "send_status", "was_delivered", "had_conversion"),
        standardize={"open_country": "country"},
        isin={
            "send_channel": ("Email", "SMS", "Push", "WhatsApp", "Voice"),
            "send_status": ("Sent", "Failed", "Bounced", "Blocked"),
            "open_country": COUNTRIES3,
            "open_device": ("Desktop", "Mobile", "Tablet"),
        },
        ranges={"click_count": (0, None), "send_cost": (0, None)},
        depends_on=("marketing_campaigns",),
    ),
    "digital_events": TableSpec(
        types={
            "event_id": "VARCHAR", "event_date": "TIMESTAMP", "process_date": "DATE",
            "customer_id": "VARCHAR", "session_id": "VARCHAR", "event_type": "VARCHAR",
            "event_category": "VARCHAR", "channel": "VARCHAR", "platform": "VARCHAR",
            "browser": "VARCHAR", "app_version": "VARCHAR", "page_url": "VARCHAR",
            "page_title": "VARCHAR", "action": "VARCHAR", "element_id": "VARCHAR",
            "product_id": "VARCHAR", "event_value": "DOUBLE", "duration_seconds": "DOUBLE",
            "ip_address": "VARCHAR", "ip_country": "VARCHAR", "ip_city": "VARCHAR",
            "is_mobile": "BOOLEAN", "referrer": "VARCHAR", "utm_source": "VARCHAR",
            "utm_medium": "VARCHAR", "utm_campaign": "VARCHAR",
        },
        pk=("event_id",),
        event="event_date",
        partitioned_silver=True,
        dedup_order="process_date",
        not_null=("event_id", "event_date", "process_date", "session_id", "event_type",
                  "event_category", "channel", "is_mobile"),
        standardize={"ip_country": "country"},
        isin={
            "event_type": ("PageView", "Click", "FormSubmit", "Login", "Logout", "Error", "Purchase"),
            "event_category": ("Navigation", "Transaction", "Authentication", "Product"),
            "channel": ("Android App", "iOS App", "Desktop Web", "Mobile Web"),
            "ip_country": COUNTRIES3,
        },
        ranges={"duration_seconds": (0, None)},
    ),
}


def topo_order(names: list[str] | None = None) -> list[str]:
    """Tables in dependency order; with names, only those tables, still correctly ordered."""
    done: list[str] = []

    def visit(name: str, stack: tuple[str, ...]) -> None:
        if name in done:
            return
        if name in stack:
            raise ValueError(f"dependency cycle at {name}")
        for dep in TABLES[name].depends_on:
            visit(dep, stack + (name,))
        done.append(name)

    for n in TABLES:
        visit(n, ())
    return done if names is None else [n for n in done if n in set(names)]
