#!/usr/bin/env python3
"""
Generate synthetic DOL-shaped CSV files for testing.

Every file has the exact column set of the real published layout for its
dataset and year, so the import pipeline can be exercised end to end without
downloading gigabytes from DOL. Values are invented; only the structure is real.

    python -m scripts.make_test_data --year 2023 --plans 50
"""

from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.dol.layouts import get_layout  # noqa: E402

DEFAULT_OUTPUT = REPO_ROOT / "test_data"

SPONSORS = [
    ("ACME MANUFACTURING INC", "Springfield", "IL", "627010000", "339900"),
    ("BLUE RIDGE HEALTHCARE LLC", "Asheville", "NC", "288010000", "621111"),
    ("CASCADE SOFTWARE CORP", "Portland", "OR", "972010000", "541511"),
    ("DELTA LOGISTICS PARTNERS LP", "Memphis", "TN", "381030000", "484121"),
    ("EVERGREEN ACADEMY", "Seattle", "WA", "981010000", "611110"),
    ("FIRST HARBOR BANCORP", "Boston", "MA", "021080000", "522110"),
    ("GRANITE STATE ENGINEERING PC", "Concord", "NH", "033010000", "541330"),
    ("HARVEST FOODS COOPERATIVE", "Des Moines", "IA", "503090000", "445110"),
]

PLAN_SUFFIXES = [
    "401(K) PROFIT SHARING PLAN",
    "RETIREMENT SAVINGS PLAN",
    "EMPLOYEES PENSION PLAN",
    "403(B) RETIREMENT PLAN",
    "457(B) DEFERRED COMPENSATION PLAN",
    "EMPLOYEE STOCK OWNERSHIP PLAN",
]

# (pension codes, expected category) pairs covering the classifier's branches.
PENSION_CODE_SETS = ["2E2G2J", "2J2K2S", "2E2F2G", "1A1I", "2L2M", "2N", "2O2P", "2C", "2G2J2W"]

RECORDKEEPERS = [
    "FIDELITY INVESTMENTS INSTITUTIONAL OPERAT",
    "EMPOWER ANNUITY INSURANCE COMPANY OF AMER",
    "VANGUARD FIDUCIARY TRUST COMPANY",
    "PRINCIPAL LIFE INSURANCE COMPANY",
    "VOYA RETIREMENT INSURANCE AND ANNUITY CO",
    "ASCENSUS LLC",
    "GUIDELINE INC",
    "PAYCHEX RETIREMENT SERVICES",
]

TRUSTEES = [
    "MATRIX TRUST COMPANY",
    "RELIANCE TRUST COMPANY",
    "CHARLES SCHWAB BANK",
    "MID ATLANTIC TRUST COMPANY",
    "WELLS FARGO BANK NA",
]

INSURERS = [
    "JOHN HANCOCK LIFE INSURANCE COMPANY USA",
    "NATIONWIDE LIFE INSURANCE COMPANY",
    "TRANSAMERICA LIFE INSURANCE COMPANY",
    "LINCOLN NATIONAL LIFE INSURANCE CO",
]

ACCOUNTANTS = [
    "CLIFTONLARSONALLEN LLP",
    "RSM US LLP",
    "PLANTE MORAN PLLC",
    "CROWE LLP",
]

# Placeholder values the extractor must reject rather than store as providers.
PLACEHOLDERS = ["N/A", "NONE", "SAME AS ABOVE", "-", "0"]


def _write(path: Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def _columns(year: int, dataset: str) -> tuple[str, ...]:
    layout = get_layout(year, dataset)
    if layout is None:
        raise SystemExit(f"No vendored layout for {dataset} {year}.")
    return layout.field_names


def generate(year: int, plan_count: int, output: Path, seed: int = 7) -> dict[str, Path]:
    random.seed(seed)
    output.mkdir(parents=True, exist_ok=True)

    written: dict[str, Path] = {}

    main_rows: list[dict[str, str]] = []
    sf_rows: list[dict[str, str]] = []
    sch_a: list[dict[str, str]] = []
    sch_c2: list[dict[str, str]] = []
    sch_h: list[dict[str, str]] = []
    sch_i: list[dict[str, str]] = []
    sch_r: list[dict[str, str]] = []
    sch_d1: list[dict[str, str]] = []

    for index in range(plan_count):
        sponsor, city, state, postal, business = SPONSORS[index % len(SPONSORS)]
        ein = f"{10_000_000 + index * 137:09d}"
        plan_number = f"{(index % 3) + 1:03d}"
        plan_name = f"{sponsor.split()[0]} {PLAN_SUFFIXES[index % len(PLAN_SUFFIXES)]}"
        codes = PENSION_CODE_SETS[index % len(PENSION_CODE_SETS)]
        large_plan = index % 3 == 0
        ack = f"2023{index:08d}NAL{index:07d}001"

        participants = 120 + index * 37 if large_plan else 12 + index * 3
        assets = float((participants * 41_500) + index * 1_000)

        common = {
            "ACK_ID": ack,
            "FILING_STATUS": "1",
            "DATE_RECEIVED": f"{year + 1}-07-{(index % 28) + 1:02d}",
        }

        if large_plan:
            main_rows.append(
                {
                    **common,
                    "FORM_PLAN_YEAR_BEGIN_DATE": f"{year}-01-01",
                    "FORM_TAX_PRD": f"{year}-12-31",
                    "TYPE_PLAN_ENTITY_CD": "2",
                    "INITIAL_FILING_IND": "0",
                    "AMENDED_IND": "0",
                    "FINAL_FILING_IND": "0",
                    "PLAN_NAME": plan_name,
                    "SPONS_DFE_PN": plan_number,
                    "PLAN_EFF_DATE": f"{1990 + (index % 30)}-01-01",
                    "SPONSOR_DFE_NAME": sponsor,
                    "SPONS_DFE_LOC_US_CITY": city,
                    "SPONS_DFE_LOC_US_STATE": state,
                    "SPONS_DFE_LOC_US_ZIP": postal,
                    "SPONS_DFE_EIN": ein,
                    "SPONS_DFE_PHONE_NUM": f"555{index:07d}"[:10],
                    "BUSINESS_CODE": business,
                    "ADMIN_NAME": sponsor if index % 4 else PLACEHOLDERS[index % len(PLACEHOLDERS)],
                    "ADMIN_EIN": ein,
                    "TOT_PARTCP_BOY_CNT": str(participants),
                    "TOT_ACTIVE_PARTCP_CNT": str(int(participants * 0.8)),
                    "PARTCP_ACCOUNT_BAL_CNT": str(int(participants * 0.95)),
                    "TYPE_PENSION_BNFT_CODE": codes,
                    "SCH_H_ATTACHED_IND": "1",
                    "SCH_A_ATTACHED_IND": "1" if index % 2 else "0",
                    "SCH_C_ATTACHED_IND": "1",
                    "SCH_R_ATTACHED_IND": "1",
                    "PREPARER_FIRM_NAME": ACCOUNTANTS[index % len(ACCOUNTANTS)],
                }
            )

            sch_h.append(
                {
                    **common,
                    "SCH_H_PLAN_YEAR_BEGIN_DATE": f"{year}-01-01",
                    "SCH_H_TAX_PRD": f"{year}-12-31",
                    "SCH_H_PN": plan_number,
                    "SCH_H_EIN": ein,
                    "TOT_ASSETS_BOY_AMT": f"{assets * 0.92:.2f}",
                    "TOT_ASSETS_EOY_AMT": f"{assets:.2f}",
                    "NET_ASSETS_EOY_AMT": f"{assets * 0.99:.2f}",
                    "EMPLR_CONTRIB_INCOME_AMT": f"{assets * 0.05:.2f}",
                    "PARTICIPANT_CONTRIB_AMT": f"{assets * 0.08:.2f}",
                    "ACCOUNTANT_FIRM_NAME": ACCOUNTANTS[index % len(ACCOUNTANTS)],
                    "ACCOUNTANT_FIRM_EIN": f"{20_000_000 + index:09d}",
                    "FDCRY_TRUSTEE_CUST_NAME": TRUSTEES[index % len(TRUSTEES)],
                    "FDCRY_TRUST_NAME": f"{sponsor} RETIREMENT TRUST",
                    "FDCRY_TRUST_EIN": ein,
                    "ACCTNT_OPINION_TYPE_CD": "1",
                }
            )

            # Two Schedule C providers per large plan, with distinct service codes.
            for order, (name, service_codes) in enumerate(
                (
                    (RECORDKEEPERS[index % len(RECORDKEEPERS)], "1537645038"),
                    (TRUSTEES[index % len(TRUSTEES)], "2119"),
                ),
                start=1,
            ):
                sch_c2.append(
                    {
                        "ACK_ID": ack,
                        "ROW_ORDER": str(order),
                        "PROVIDER_OTHER_NAME": name,
                        "PROVIDER_OTHER_EIN": f"{30_000_000 + index * 7 + order:09d}",
                        "PROVIDER_OTHER_US_CITY": city,
                        "PROVIDER_OTHER_US_STATE": state,
                        "PROVIDER_OTHER_US_ZIP": postal,
                        "PROVIDER_OTHER_SRVC_CODES": service_codes,
                        "PROVIDER_OTHER_RELATION": "NONE" if order == 1 else "AFFILIATE",
                        "PROVIDER_OTHER_DIRECT_COMP_AMT": f"{12_500 + index * 90:.2f}",
                        "PROV_OTHER_TOT_IND_COMP_AMT": f"{3_100 + index * 15:.2f}",
                    }
                )

            # A placeholder row the extractor must discard.
            sch_c2.append(
                {
                    "ACK_ID": ack,
                    "ROW_ORDER": "9",
                    "PROVIDER_OTHER_NAME": PLACEHOLDERS[index % len(PLACEHOLDERS)],
                    "PROVIDER_OTHER_SRVC_CODES": "49",
                }
            )

            sch_d1.append(
                {
                    "ACK_ID": ack,
                    "ROW_ORDER": "1",
                    "DFE_P1_ENTITY_NAME": f"{RECORDKEEPERS[index % len(RECORDKEEPERS)]} CIT",
                    "DFE_P1_SPONS_NAME": RECORDKEEPERS[index % len(RECORDKEEPERS)],
                    "DFE_P1_PLAN_EIN": f"{40_000_000 + index:09d}",
                    "DFE_P1_PLAN_PN": "333",
                    "DFE_P1_ENTITY_CODE": "C",
                    "DFE_P1_PLAN_INT_EOY_AMT": f"{assets * 0.6:.2f}",
                }
            )
        else:
            sf_rows.append(
                {
                    **common,
                    "SF_PLAN_YEAR_BEGIN_DATE": f"{year}-01-01",
                    "SF_TAX_PRD": f"{year}-12-31",
                    "SF_PLAN_ENTITY_CD": "2",
                    "SF_PLAN_NAME": plan_name,
                    "SF_PLAN_NUM": plan_number,
                    "SF_PLAN_EFF_DATE": f"{1995 + (index % 25)}-01-01",
                    "SF_SPONSOR_NAME": sponsor,
                    "SF_SPONS_LOC_US_CITY": city,
                    "SF_SPONS_LOC_US_STATE": state,
                    "SF_SPONS_LOC_US_ZIP": postal,
                    "SF_SPONS_EIN": ein,
                    "SF_BUSINESS_CODE": business,
                    "SF_ADMIN_NAME": sponsor,
                    "SF_ADMIN_EIN": ein,
                    "SF_TOT_PARTCP_BOY_CNT": str(participants),
                    "SF_TOT_ACT_PARTCP_BOY_CNT": str(int(participants * 0.85)),
                    "SF_PARTCP_ACCOUNT_BAL_CNT": str(participants),
                    "SF_TOT_ASSETS_BOY_AMT": f"{assets * 0.9:.2f}",
                    "SF_TOT_ASSETS_EOY_AMT": f"{assets:.2f}",
                    "SF_NET_ASSETS_EOY_AMT": f"{assets:.2f}",
                    "SF_EMPLR_CONTRIB_INCOME_AMT": f"{assets * 0.06:.2f}",
                    "SF_PARTICIP_CONTRIB_INCOME_AMT": f"{assets * 0.09:.2f}",
                    "SF_TYPE_PENSION_BNFT_CODE": codes,
                    "SF_FDCRY_TRUSTE_CUST_NAME": TRUSTEES[index % len(TRUSTEES)],
                    "SF_FDCRY_TRUST_NAME": f"{sponsor} SAVINGS TRUST",
                    "SF_FDCRY_TRUST_EIN": ein,
                    "SF_401K_PLAN_IND": "1" if "2J" in codes else "0",
                    "SF_PREPARER_FIRM_NAME": ACCOUNTANTS[index % len(ACCOUNTANTS)],
                }
            )

            sch_i.append(
                {
                    **common,
                    "SCH_I_PLAN_YEAR_BEGIN_DATE": f"{year}-01-01",
                    "SCH_I_TAX_PRD": f"{year}-12-31",
                    "SCH_I_PLAN_NUM": plan_number,
                    "SCH_I_EIN": ein,
                    "SMALL_TOT_ASSETS_EOY_AMT": f"{assets:.2f}",
                    "SMALL_NET_ASSETS_EOY_AMT": f"{assets:.2f}",
                    "FDCRY_TRUSTEE_CUST_NAME": TRUSTEES[index % len(TRUSTEES)],
                    "FDCRY_TRUST_NAME": f"{sponsor} SAVINGS TRUST",
                    "FDCRY_TRUST_EIN": ein,
                }
            )

        if index % 2:
            sch_a.append(
                {
                    "ACK_ID": ack,
                    "SCH_A_PLAN_YEAR_BEGIN_DATE": f"{year}-01-01",
                    "SCH_A_PLAN_YEAR_END_DATE": f"{year}-12-31",
                    "SCH_A_PLAN_NUM": plan_number,
                    "SCH_A_EIN": ein,
                    "INS_CARRIER_NAME": INSURERS[index % len(INSURERS)],
                    "INS_CARRIER_EIN": f"{50_000_000 + index:09d}",
                    "INS_CONTRACT_NUM": f"GA-{index:06d}",
                    "INS_PRSN_COVERED_EOY_CNT": str(participants),
                    "PENSION_EOY_GEN_ACCT_AMT": f"{assets * 0.3:.2f}",
                }
            )

        sch_r.append(
            {
                "ACK_ID": ack,
                "SCH_R_PLAN_YEAR_BEGIN_DATE": f"{year}-01-01",
                "SCH_R_TAX_PRD": f"{year}-12-31",
                "SCH_R_PN": plan_number,
                "SCH_R_EIN": ein,
                "F_401K_PLAN_IND": "1" if "2J" in codes else "0",
                "ESOP_PREF_IND": "1" if "2O" in codes or "2P" in codes else "",
                "PEN_STOCK_PRCNT": "60",
            }
        )

    datasets = (
        ("F_5500", main_rows),
        ("F_5500_SF", sf_rows),
        ("F_SCH_A", sch_a),
        ("F_SCH_C_PART1_ITEM2", sch_c2),
        ("F_SCH_D_PART1", sch_d1),
        ("F_SCH_H", sch_h),
        ("F_SCH_I", sch_i),
        ("F_SCH_R", sch_r),
    )

    for dataset, rows in datasets:
        if not rows:
            continue
        path = output / f"{dataset}_{year}_Latest.csv"
        _write(path, _columns(year, dataset), rows)
        written[dataset] = path
        print(f"  {path.name}: {len(rows)} rows x {len(_columns(year, dataset))} columns")

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2023)
    parser.add_argument("--plans", type=int, default=48)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    print(f"Generating synthetic {args.year} DOL files in {args.output}")
    generate(args.year, args.plans, args.output, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
