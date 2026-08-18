"""Give metrics a statement position and a parent, and seed the filing line items

The catalog held eleven metrics: five headline figures and six ratios. A filing
prints far more than that, and a line with no canonical code is dropped after
being read correctly — net interest income and paid-in capital were both read
out of a real filing and then discarded for having nowhere to go.

Two things are added. Each metric now says where it sits in a statement and
which line it rolls up into, which is what a breakdown question needs: asking
for a bank's liability composition means asking for the children of total
liabilities. And the balance sheet and income statement line items a Turkish
bank filing actually prints are seeded, so those lines have somewhere to land.

Revision ID: 035_metric_hierarchy_and_statement_lines
Revises: 034_grant_candidate_review_permissions
Create Date: 2026-08-18
"""

import sqlalchemy as sa
from alembic import op

revision = "035_metric_hierarchy_and_statement_lines"
down_revision = "034_grant_candidate_review_permissions"
branch_labels = None
depends_on = None

# (code, canonical name, section, parent, display order, normal balance, aggregation)
#
# Sections mirror how a filing is laid out, so a breakdown can be rendered in
# the order the reader expects rather than alphabetically.
ASSET = "BALANCE_SHEET_ASSETS"
LIABILITY = "BALANCE_SHEET_LIABILITIES"
EQUITY = "BALANCE_SHEET_EQUITY"
INCOME = "INCOME_STATEMENT"
RATIO = "RATIO"

POINT_IN_TIME = "POINT_IN_TIME"
PERIOD_TOTAL = "PERIOD_TOTAL"

NEW_METRICS = [
    # --- Assets -----------------------------------------------------------
    ("CASH_AND_CENTRAL_BANK", "Nakit ve Merkez Bankası", ASSET, "TOTAL_ASSETS", 10, "DEBIT", POINT_IN_TIME),
    ("BANKS_RECEIVABLES", "Bankalar", ASSET, "TOTAL_ASSETS", 20, "DEBIT", POINT_IN_TIME),
    ("SECURITIES_PORTFOLIO", "Menkul Değerler", ASSET, "TOTAL_ASSETS", 30, "DEBIT", POINT_IN_TIME),
    (
        "SUBSIDIARIES_AND_ASSOCIATES",
        "İştirakler ve Bağlı Ortaklıklar",
        ASSET,
        "TOTAL_ASSETS",
        50,
        "DEBIT",
        POINT_IN_TIME,
    ),
    ("TANGIBLE_ASSETS", "Maddi Duran Varlıklar", ASSET, "TOTAL_ASSETS", 60, "DEBIT", POINT_IN_TIME),
    ("INTANGIBLE_ASSETS", "Maddi Olmayan Duran Varlıklar", ASSET, "TOTAL_ASSETS", 70, "DEBIT", POINT_IN_TIME),
    ("OTHER_ASSETS", "Diğer Aktifler", ASSET, "TOTAL_ASSETS", 90, "DEBIT", POINT_IN_TIME),
    # --- Liabilities ------------------------------------------------------
    ("TOTAL_LIABILITIES", "Toplam Yükümlülükler", LIABILITY, None, 100, "CREDIT", POINT_IN_TIME),
    ("FUNDS_BORROWED", "Alınan Krediler", LIABILITY, "TOTAL_LIABILITIES", 120, "CREDIT", POINT_IN_TIME),
    ("MONEY_MARKET_FUNDING", "Para Piyasalarına Borçlar", LIABILITY, "TOTAL_LIABILITIES", 130, "CREDIT", POINT_IN_TIME),
    (
        "SECURITIES_ISSUED",
        "İhraç Edilen Menkul Kıymetler",
        LIABILITY,
        "TOTAL_LIABILITIES",
        140,
        "CREDIT",
        POINT_IN_TIME,
    ),
    (
        "LEASE_LIABILITIES",
        "Kiralama İşlemlerinden Yükümlülükler",
        LIABILITY,
        "TOTAL_LIABILITIES",
        150,
        "CREDIT",
        POINT_IN_TIME,
    ),
    ("PROVISIONS", "Karşılıklar", LIABILITY, "TOTAL_LIABILITIES", 160, "CREDIT", POINT_IN_TIME),
    (
        "SUBORDINATED_DEBT",
        "Sermaye Benzeri Borçlanma Araçları",
        LIABILITY,
        "TOTAL_LIABILITIES",
        170,
        "CREDIT",
        POINT_IN_TIME,
    ),
    ("OTHER_LIABILITIES", "Diğer Yükümlülükler", LIABILITY, "TOTAL_LIABILITIES", 190, "CREDIT", POINT_IN_TIME),
    # --- Equity -----------------------------------------------------------
    ("PAID_IN_CAPITAL", "Ödenmiş Sermaye", EQUITY, "TOTAL_EQUITY", 210, "CREDIT", POINT_IN_TIME),
    ("CAPITAL_RESERVES", "Sermaye Yedekleri", EQUITY, "TOTAL_EQUITY", 220, "CREDIT", POINT_IN_TIME),
    ("PROFIT_RESERVES", "Kâr Yedekleri", EQUITY, "TOTAL_EQUITY", 230, "CREDIT", POINT_IN_TIME),
    ("RETAINED_EARNINGS", "Geçmiş Yıllar Kâr veya Zararı", EQUITY, "TOTAL_EQUITY", 240, "CREDIT", POINT_IN_TIME),
    # --- Income statement -------------------------------------------------
    ("INTEREST_INCOME", "Faiz Gelirleri", INCOME, None, 300, "CREDIT", PERIOD_TOTAL),
    ("INTEREST_EXPENSE", "Faiz Giderleri", INCOME, None, 310, "DEBIT", PERIOD_TOTAL),
    ("NET_INTEREST_INCOME", "Net Faiz Geliri veya Gideri", INCOME, None, 320, "CREDIT", PERIOD_TOTAL),
    ("NET_FEE_COMMISSION_INCOME", "Net Ücret ve Komisyon Gelirleri", INCOME, None, 330, "CREDIT", PERIOD_TOTAL),
    ("TRADING_INCOME", "Ticari Kâr veya Zarar", INCOME, None, 340, "CREDIT", PERIOD_TOTAL),
    ("OPERATING_EXPENSES", "Faaliyet Giderleri", INCOME, None, 350, "DEBIT", PERIOD_TOTAL),
    ("EXPECTED_CREDIT_LOSS", "Beklenen Zarar Karşılıkları", INCOME, None, 360, "DEBIT", PERIOD_TOTAL),
    ("PROFIT_BEFORE_TAX", "Vergi Öncesi Kâr veya Zarar", INCOME, None, 370, "CREDIT", PERIOD_TOTAL),
    ("TAX_EXPENSE", "Vergi Karşılığı", INCOME, None, 380, "DEBIT", PERIOD_TOTAL),
]

# Where the metrics that already existed belong.
EXISTING_PLACEMENT = [
    ("TOTAL_ASSETS", ASSET, None, 1),
    ("TOTAL_LOANS", ASSET, "TOTAL_ASSETS", 40),
    ("NON_PERFORMING_LOANS", ASSET, "TOTAL_LOANS", 45),
    ("TOTAL_DEPOSITS", LIABILITY, "TOTAL_LIABILITIES", 110),
    ("TOTAL_EQUITY", EQUITY, None, 200),
    ("NET_INCOME", INCOME, None, 390),
    ("CAPITAL_ADEQUACY_RATIO", RATIO, None, 400),
    ("LOAN_TO_DEPOSIT_RATIO", RATIO, None, 410),
    ("NET_INTEREST_MARGIN", RATIO, None, 420),
    ("RETURN_ON_ASSETS", RATIO, None, 430),
    ("RETURN_ON_EQUITY", RATIO, None, 440),
]


def upgrade() -> None:
    op.add_column("metric_definitions", sa.Column("parent_metric_code", sa.String(100), nullable=True))
    op.add_column(
        "metric_definitions",
        sa.Column("statement_section", sa.String(50), nullable=False, server_default="UNCLASSIFIED"),
    )
    op.add_column(
        "metric_definitions",
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="1000"),
    )

    # A parent must be a metric that exists, and a metric may not be its own
    # parent: a cycle here would make a breakdown query walk forever.
    op.create_foreign_key(
        "fk_metric_definitions_parent_metric_code",
        "metric_definitions",
        "metric_definitions",
        ["parent_metric_code"],
        ["metric_code"],
        ondelete="RESTRICT",
    )
    op.create_check_constraint(
        "ck_metric_definitions_parent_is_not_self",
        "metric_definitions",
        "parent_metric_code IS NULL OR parent_metric_code <> metric_code",
    )
    op.create_index(
        "ix_metric_definitions_section_order",
        "metric_definitions",
        ["statement_section", "display_order"],
    )

    connection = op.get_bind()

    # The primary key is generated by the application, not by the column, so a
    # migration inserting rows has to supply one itself.
    def insert(row: tuple) -> None:
        code, name, section, parent, order, balance, aggregation = row
        connection.execute(
            sa.text("""
                INSERT INTO public.metric_definitions (
                    id, metric_code, canonical_name, value_type,
                    default_currency_behavior, default_unit, normal_balance,
                    aggregation_behavior, formula_type, formula_version, status,
                    parent_metric_code, statement_section, display_order
                ) VALUES (
                    gen_random_uuid(), :code, :name, 'CURRENCY',
                    'SAME_AS_SOURCE', 'TRY', :balance,
                    :aggregation, 'SOURCE_REPORTED', '1.0.0', 'ACTIVE',
                    :parent, :section, :order
                )
            """),
            {
                "code": code,
                "name": name,
                "balance": balance,
                "aggregation": aggregation,
                "parent": parent,
                "section": section,
                "order": order,
            },
        )

    # The foreign key means a row cannot name a parent that is not there yet.
    # Roots first, then the existing metrics they adopt, then the children.
    for row in NEW_METRICS:
        if row[3] is None:
            insert(row)

    for code, section, parent, order in EXISTING_PLACEMENT:
        connection.execute(
            sa.text("""
                UPDATE public.metric_definitions
                   SET statement_section = :section,
                       parent_metric_code = :parent,
                       display_order = :order
                 WHERE metric_code = :code
            """),
            {"code": code, "section": section, "parent": parent, "order": order},
        )

    for row in NEW_METRICS:
        if row[3] is not None:
            insert(row)


def downgrade() -> None:
    connection = op.get_bind()
    codes = tuple(row[0] for row in NEW_METRICS)
    connection.execute(
        sa.text("DELETE FROM public.metric_definitions WHERE metric_code = ANY(:codes)"),
        {"codes": list(codes)},
    )
    op.drop_index("ix_metric_definitions_section_order", table_name="metric_definitions")
    op.drop_constraint("ck_metric_definitions_parent_is_not_self", "metric_definitions", type_="check")
    op.drop_constraint("fk_metric_definitions_parent_metric_code", "metric_definitions", type_="foreignkey")
    op.drop_column("metric_definitions", "display_order")
    op.drop_column("metric_definitions", "statement_section")
    op.drop_column("metric_definitions", "parent_metric_code")
