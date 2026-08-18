"""DOL / IRS code tables used to interpret Form 5500 filings."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.constants import PlanCategory, PlanFeature, ProviderRole


@dataclass(frozen=True, slots=True)
class PlanCharacteristic:
    code: str
    description: str
    category: PlanCategory
    features: tuple[PlanFeature, ...] = ()
    since: int | None = None


def _dc(
    code: str,
    description: str,
    *features: PlanFeature,
    since: int | None = None,
) -> PlanCharacteristic:
    return PlanCharacteristic(
        code, description, PlanCategory.DEFINED_CONTRIBUTION, features, since
    )


def _db(code: str, description: str, *features: PlanFeature) -> PlanCharacteristic:
    return PlanCharacteristic(code, description, PlanCategory.DEFINED_BENEFIT, features)


PLAN_CHARACTERISTICS: dict[str, PlanCharacteristic] = {
    entry.code: entry
    for entry in (
        _db("1A", "Benefits are primarily pay related.", PlanFeature.PENSION_DB),
        _db(
            "1B",
            "Benefits are primarily flat dollar (includes dollars per year of service).",
            PlanFeature.PENSION_DB,
        ),
        _db(
            "1C",
            "Cash balance or similar plan.",
            PlanFeature.PENSION_DB,
            PlanFeature.CASH_BALANCE,
        ),
        _db(
            "1D",
            "Floor-offset plan, offset for benefits provided by an employer-sponsored "
            "defined contribution plan.",
            PlanFeature.PENSION_DB,
        ),
        _db(
            "1E",
            "Code section 401(h) arrangement providing employee health benefits.",
            PlanFeature.PENSION_DB,
        ),
        _db(
            "1F",
            "Code section 414(k) arrangement; benefits partly based on a separate "
            "participant account.",
            PlanFeature.PENSION_DB,
        ),
        _db(
            "1H",
            "Plan covered by PBGC that was terminated and closed out for PBGC purposes.",
            PlanFeature.PENSION_DB,
        ),
        _db("1I", "Frozen plan; no participant receives new benefit accrual.", PlanFeature.PENSION_DB),
        _dc(
            "2A",
            "Age/service weighted or new comparability or similar allocation.",
            PlanFeature.PROFIT_SHARING,
        ),
        _dc("2B", "Target benefit plan.", PlanFeature.TARGET_BENEFIT),
        _dc("2C", "Money purchase (other than target benefit) plan.", PlanFeature.MONEY_PURCHASE),
        _dc("2D", "Offset plan; benefits offset by another plan of the employer."),
        _dc("2E", "Profit-sharing plan.", PlanFeature.PROFIT_SHARING),
        _dc("2F", "ERISA section 404(c) plan.", PlanFeature.ERISA_404C),
        _dc(
            "2G",
            "Total participant-directed account plan.",
            PlanFeature.PARTICIPANT_DIRECTED,
        ),
        _dc(
            "2H",
            "Partial participant-directed account plan.",
            PlanFeature.PARTICIPANT_DIRECTED,
        ),
        _dc("2I", "Stock bonus.", PlanFeature.STOCK_BONUS),
        _dc("2J", "Code section 401(k) feature (cash or deferred arrangement).", PlanFeature.K401),
        _dc("2K", "Code section 401(m) arrangement (employee/matching contributions)."),
        _dc(
            "2L",
            "Annuity contract purchased by a 501(c)(3) organization or public school "
            "as described in Code section 403(b)(1).",
            PlanFeature.B403,
        ),
        _dc(
            "2M",
            "Custodial accounts for regulated investment company stock as described "
            "in Code section 403(b)(7).",
            PlanFeature.B403,
        ),
        _dc(
            "2N",
            "Code section 408 accounts and annuities (IRA-funded pension plan).",
            PlanFeature.SEP_SIMPLE_408,
        ),
        _dc("2O", "ESOP other than a leveraged ESOP.", PlanFeature.ESOP),
        _dc("2P", "Leveraged ESOP.", PlanFeature.ESOP),
        _dc("2Q", "The employer maintaining this ESOP is an S corporation.", PlanFeature.ESOP),
        _dc("2R", "Participant-directed brokerage accounts provided as an investment option."),
        _dc("2S", "401(k) or 403(b) plan that provides for automatic enrollment."),
        _dc(
            "2T",
            "Total or partial participant-directed account plan using a default "
            "investment account.",
            PlanFeature.PARTICIPANT_DIRECTED,
        ),
        _dc(
            "2U",
            "Multiple-employer pension plan sponsored by a bona fide group or "
            "association (Association Retirement Plan).",
            PlanFeature.MULTIPLE_EMPLOYER,
            since=2022,
        ),
        _dc(
            "2V",
            "Multiple-employer pension plan that is a Professional Employer "
            "Organization (PEO) plan.",
            PlanFeature.MULTIPLE_EMPLOYER,
            since=2022,
        ),
        _dc(
            "2W",
            "Multiple-employer pension plan that is a pooled employer plan under "
            "ERISA section 3(43).",
            PlanFeature.MULTIPLE_EMPLOYER,
            PlanFeature.POOLED_EMPLOYER,
            since=2022,
        ),
        _dc(
            "2X",
            "Multiple-employer defined contribution pension plan not described by "
            "codes 2U, 2V or 2W.",
            PlanFeature.MULTIPLE_EMPLOYER,
            since=2022,
        ),
        PlanCharacteristic(
            "3B", "Plan covered self-employed individuals in the return year.", PlanCategory.UNKNOWN
        ),
        PlanCharacteristic(
            "3C",
            "Plan not intended to be qualified under Code sections 401, 403 or 408.",
            PlanCategory.UNKNOWN,
        ),
        PlanCharacteristic(
            "3D",
            "Pre-approved pension plan subject to a favorable IRS opinion letter.",
            PlanCategory.UNKNOWN,
        ),
        PlanCharacteristic(
            "3F",
            "Plan sponsor received services of leased employees under Code section 414(n).",
            PlanCategory.UNKNOWN,
        ),
        PlanCharacteristic(
            "3H",
            "Plan sponsor is a member of a controlled or affiliated service group.",
            PlanCategory.UNKNOWN,
        ),
        PlanCharacteristic(
            "3I",
            "Plan requires employer contributions to be held in employer securities.",
            PlanCategory.UNKNOWN,
        ),
        PlanCharacteristic(
            "3J",
            "U.S.-based plan covering residents of Puerto Rico qualified under Code "
            "section 401 and Puerto Rico section 1165.",
            PlanCategory.UNKNOWN,
        ),
        *(
            PlanCharacteristic(code, description, PlanCategory.WELFARE)
            for code, description in (
                ("4A", "Health (other than vision or dental)."),
                ("4B", "Life insurance."),
                ("4C", "Supplemental unemployment."),
                ("4D", "Dental."),
                ("4E", "Vision."),
                ("4F", "Temporary disability (accident and sickness)."),
                ("4G", "Prepaid legal."),
                ("4H", "Long-term disability."),
                ("4I", "Severance pay."),
                ("4J", "Apprenticeship and training."),
                ("4K", "Scholarship (funded)."),
                ("4L", "Death benefits (including travel accident, not life insurance)."),
                ("4P", "Taft-Hartley financial assistance for employee housing expenses."),
                ("4Q", "Other."),
                (
                    "4R",
                    "Unfunded, fully insured or combination welfare plan that will not "
                    "file an annual report next plan year.",
                ),
                (
                    "4S",
                    "Unfunded, fully insured or combination welfare plan that stopped "
                    "filing annual reports in an earlier plan year.",
                ),
                ("4T", "10-or-more-employer plan under Code section 419A(f)(6)."),
                (
                    "4U",
                    "Collectively bargained welfare benefit arrangement under Code "
                    "section 419A(f)(5).",
                ),
            )
        ),
    )
}


@dataclass(frozen=True, slots=True)
class ServiceCode:
    code: str
    description: str
    role: ProviderRole | None = None
    is_compensation_code: bool = False


def _svc(code: str, description: str, role: ProviderRole | None = None) -> ServiceCode:
    return ServiceCode(code, description, role, False)


def _comp(code: str, description: str, role: ProviderRole | None = None) -> ServiceCode:
    return ServiceCode(code, description, role, True)


SERVICE_CODES: dict[str, ServiceCode] = {
    entry.code: entry
    for entry in (
        _svc("10", "Accounting (including auditing)", ProviderRole.ACCOUNTANT),
        _svc("11", "Actuarial", ProviderRole.ACTUARY),
        _svc("12", "Claims processing", ProviderRole.SERVICE_PROVIDER),
        _svc("13", "Contract Administrator", ProviderRole.THIRD_PARTY_ADMIN),
        _svc("14", "Plan Administrator", ProviderRole.ADMINISTRATOR),
        _svc(
            "15",
            "Recordkeeping and information management (computing, tabulating, "
            "data processing, etc.)",
            ProviderRole.RECORDKEEPER,
        ),
        _svc("16", "Consulting (general)", ProviderRole.CONSULTANT),
        _svc("17", "Consulting (pension)", ProviderRole.CONSULTANT),
        _svc("18", "Custodial (other than securities)", ProviderRole.CUSTODIAN),
        _svc("19", "Custodial (securities)", ProviderRole.CUSTODIAN),
        _svc("20", "Trustee (individual)", ProviderRole.TRUSTEE),
        _svc(
            "21",
            "Trustee (bank, trust company, or similar financial institution)",
            ProviderRole.TRUSTEE,
        ),
        _svc("22", "Insurance agents and brokers", ProviderRole.BROKER),
        _svc("23", "Insurance services", ProviderRole.INSURER),
        _svc("24", "Trustee (discretionary)", ProviderRole.TRUSTEE),
        _svc("25", "Trustee (directed)", ProviderRole.TRUSTEE),
        _svc("26", "Investment advisory (participants)", ProviderRole.INVESTMENT_ADVISOR),
        _svc("27", "Investment advisory (plan)", ProviderRole.INVESTMENT_ADVISOR),
        _svc("28", "Investment management", ProviderRole.INVESTMENT_MANAGER),
        _svc("29", "Legal", ProviderRole.ATTORNEY),
        _svc("30", "Employee (plan)", None),
        _svc("31", "Named fiduciary", ProviderRole.TRUSTEE),
        _svc("32", "Real estate brokerage", ProviderRole.BROKER),
        _svc("33", "Securities brokerage", ProviderRole.BROKER),
        _svc("34", "Valuation (appraisals, etc.)", ProviderRole.SERVICE_PROVIDER),
        _svc("35", "Employee (plan sponsor)", None),
        _svc("36", "Copying and duplicating", ProviderRole.SERVICE_PROVIDER),
        _svc("37", "Participant loan processing", ProviderRole.RECORDKEEPER),
        _svc("38", "Participant communication", ProviderRole.SERVICE_PROVIDER),
        _svc(
            "40",
            "Foreign entity (agent, broker, bank, insurance company, etc. not "
            "operating within the United States)",
            ProviderRole.SERVICE_PROVIDER,
        ),
        _svc("49", "Other services", ProviderRole.SERVICE_PROVIDER),
        _comp("50", "Direct payment from the plan"),
        _comp("51", "Investment management fees paid directly by plan", ProviderRole.INVESTMENT_MANAGER),
        _comp("52", "Investment management fees paid indirectly by plan", ProviderRole.INVESTMENT_MANAGER),
        _comp("53", "Insurance brokerage commissions and fees", ProviderRole.BROKER),
        _comp("54", "Sales loads (front end and deferred)"),
        _comp("55", "Other commissions"),
        _comp("56", "Non-monetary compensation"),
        _comp("57", "Redemption fees"),
        _comp("58", "Product termination fees (surrender charges, etc.)"),
        _comp("59", "Shareholder servicing fees"),
        _comp("60", "Sub-transfer agency fees"),
        _comp("61", "Finders' fees/placement fees"),
        _comp("62", "Float revenue"),
        _comp("63", "Distribution (12b-1) fees"),
        _comp("64", "Recordkeeping fees", ProviderRole.RECORDKEEPER),
        _comp("65", "Account maintenance fees"),
        _comp("66", "Insurance mortality and expense charge", ProviderRole.INSURER),
        _comp("67", "Other insurance wrap fees", ProviderRole.INSURER),
        _comp("68", "'Soft dollars' commissions"),
        _comp("70", "Consulting fees", ProviderRole.CONSULTANT),
        _comp("71", "Securities brokerage commissions and fees", ProviderRole.BROKER),
        _comp("72", "Other investment fees and expenses"),
        _comp("73", "Other insurance fees and expenses", ProviderRole.INSURER),
        _comp("99", "Other fees"),
    )
}


PLAN_ENTITY_CODES: dict[str, str] = {
    "1": "Multiemployer plan",
    "2": "Single-employer plan",
    "3": "Multiple-employer plan",
    "4": "Direct filing entity (DFE)",
}

MULTIEMPLOYER_ENTITY_CODE = "1"
SINGLE_EMPLOYER_ENTITY_CODE = "2"
MULTIPLE_EMPLOYER_ENTITY_CODE = "3"
DFE_ENTITY_CODE = "4"

DFE_ENTITY_CODES: dict[str, str] = {
    "M": "Master trust investment account (MTIA)",
    "C": "Common/collective trust (CCT)",
    "P": "Pooled separate account (PSA)",
    "E": "103-12 investment entity (103-12 IE)",
    "G": "Group insurance arrangement (GIA)",
}

ACCOUNTANT_OPINION_CODES: dict[str, str] = {
    "1": "Unqualified",
    "2": "Qualified",
    "3": "Disclaimer",
    "4": "Adverse",
}

FILING_STATUS_DESCRIPTIONS: dict[str, str] = {
    "1": "Filing received",
    "2": "Processing stopped",
    "3": "Filing error",
    "FILING_RECEIVED": "Filing received",
    "PROCESSING_STOPPED": "Processing stopped",
    "FILING_ERROR": "Filing error",
}


def describe_characteristic(code: str) -> str:
    entry = PLAN_CHARACTERISTICS.get(code.strip().upper())
    return entry.description if entry else f"Unrecognised plan characteristic code {code}"


def describe_service_code(code: str) -> str:
    entry = SERVICE_CODES.get(code.strip().zfill(2))
    return entry.description if entry else f"Unrecognised Schedule C service code {code}"


def role_for_service_code(code: str) -> ProviderRole | None:
    entry = SERVICE_CODES.get(code.strip().zfill(2))
    return entry.role if entry else None
