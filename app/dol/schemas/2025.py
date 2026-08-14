from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FieldType = Literal["TEXT", "NUMERIC"]


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    position: int
    name: str
    field_type: FieldType
    size: int | None = None


FORM_YEAR = 2025
FORM_TYPE = "5500"


FIELDS: tuple[FieldDefinition, ...] = (
    FieldDefinition(1, "ACK_ID", "TEXT", 30),
    FieldDefinition(2, "FORM_PLAN_YEAR_BEGIN_DATE", "TEXT", 10),
    FieldDefinition(3, "FORM_TAX_PRD", "TEXT", 10),
    FieldDefinition(4, "TYPE_PLAN_ENTITY_CD", "TEXT", 1),
    FieldDefinition(5, "TYPE_DFE_PLAN_ENTITY_CD", "TEXT", 1),
    FieldDefinition(6, "INITIAL_FILING_IND", "TEXT", 1),
    FieldDefinition(7, "AMENDED_IND", "TEXT", 1),
    FieldDefinition(8, "FINAL_FILING_IND", "TEXT", 1),
    FieldDefinition(9, "SHORT_PLAN_YR_IND", "TEXT", 1),
    FieldDefinition(10, "COLLECTIVE_BARGAIN_IND", "TEXT", 1),
    FieldDefinition(11, "F5558_APPLICATION_FILED_IND", "TEXT", 1),
    FieldDefinition(12, "EXT_AUTOMATIC_IND", "TEXT", 1),
    FieldDefinition(13, "DFVC_PROGRAM_IND", "TEXT", 1),
    FieldDefinition(14, "EXT_SPECIAL_IND", "TEXT", 1),
    FieldDefinition(15, "EXT_SPECIAL_TEXT", "TEXT", 35),
    FieldDefinition(16, "PLAN_NAME", "TEXT", 140),
    FieldDefinition(17, "SPONS_DFE_PN", "TEXT", 3),
    FieldDefinition(18, "PLAN_EFF_DATE", "TEXT", 10),
    FieldDefinition(19, "SPONSOR_DFE_NAME", "TEXT", 70),
    FieldDefinition(20, "SPONS_DFE_DBA_NAME", "TEXT", 70),
    FieldDefinition(21, "SPONS_DFE_CARE_OF_NAME", "TEXT", 70),
    FieldDefinition(22, "SPONS_DFE_MAIL_US_ADDRESS1", "TEXT", 35),
    FieldDefinition(23, "SPONS_DFE_MAIL_US_ADDRESS2", "TEXT", 35),
    FieldDefinition(24, "SPONS_DFE_MAIL_US_CITY", "TEXT", 22),
    FieldDefinition(25, "SPONS_DFE_MAIL_US_STATE", "TEXT", 2),
    FieldDefinition(26, "SPONS_DFE_MAIL_US_ZIP", "TEXT", 12),
    FieldDefinition(27, "SPONS_DFE_MAIL_FOREIGN_ADDR1", "TEXT", 35),
    FieldDefinition(28, "SPONS_DFE_MAIL_FOREIGN_ADDR2", "TEXT", 35),
    FieldDefinition(29, "SPONS_DFE_MAIL_FOREIGN_CITY", "TEXT", 22),
    FieldDefinition(30, "SPONS_DFE_MAIL_FORGN_PROV_ST", "TEXT", 22),
    FieldDefinition(31, "SPONS_DFE_MAIL_FOREIGN_CNTRY", "TEXT", 2),
    FieldDefinition(32, "SPONS_DFE_MAIL_FORGN_POSTAL_CD", "TEXT", 22),
    FieldDefinition(33, "SPONS_DFE_LOC_US_ADDRESS1", "TEXT", 35),
    FieldDefinition(34, "SPONS_DFE_LOC_US_ADDRESS2", "TEXT", 35),
    FieldDefinition(35, "SPONS_DFE_LOC_US_CITY", "TEXT", 22),
    FieldDefinition(36, "SPONS_DFE_LOC_US_STATE", "TEXT", 2),
    FieldDefinition(37, "SPONS_DFE_LOC_US_ZIP", "TEXT", 12),
    FieldDefinition(38, "SPONS_DFE_LOC_FOREIGN_ADDRESS1", "TEXT", 35),
    FieldDefinition(39, "SPONS_DFE_LOC_FOREIGN_ADDRESS2", "TEXT", 35),
    FieldDefinition(40, "SPONS_DFE_LOC_FOREIGN_CITY", "TEXT", 22),
    FieldDefinition(41, "SPONS_DFE_LOC_FORGN_PROV_ST", "TEXT", 22),
    FieldDefinition(42, "SPONS_DFE_LOC_FOREIGN_CNTRY", "TEXT", 2),
    FieldDefinition(43, "SPONS_DFE_LOC_FORGN_POSTAL_CD", "TEXT", 22),
    FieldDefinition(44, "SPONS_DFE_EIN", "TEXT", 9),
    FieldDefinition(45, "SPONS_DFE_PHONE_NUM", "TEXT", 10),
    FieldDefinition(46, "BUSINESS_CODE", "TEXT", 6),
    FieldDefinition(47, "ADMIN_NAME", "TEXT", 70),
    FieldDefinition(48, "ADMIN_CARE_OF_NAME", "TEXT", 70),
    FieldDefinition(49, "ADMIN_US_ADDRESS1", "TEXT", 35),
    FieldDefinition(50, "ADMIN_US_ADDRESS2", "TEXT", 35),
    FieldDefinition(51, "ADMIN_US_CITY", "TEXT", 22),
    FieldDefinition(52, "ADMIN_US_STATE", "TEXT", 2),
    FieldDefinition(53, "ADMIN_US_ZIP", "TEXT", 12),
    FieldDefinition(54, "ADMIN_FOREIGN_ADDRESS1", "TEXT", 35),
    FieldDefinition(55, "ADMIN_FOREIGN_ADDRESS2", "TEXT", 35),
    FieldDefinition(56, "ADMIN_FOREIGN_CITY", "TEXT", 22),
    FieldDefinition(57, "ADMIN_FOREIGN_PROV_STATE", "TEXT", 22),
    FieldDefinition(58, "ADMIN_FOREIGN_CNTRY", "TEXT", 2),
    FieldDefinition(59, "ADMIN_FOREIGN_POSTAL_CD", "TEXT", 22),
    FieldDefinition(60, "ADMIN_EIN", "TEXT", 9),
    FieldDefinition(61, "ADMIN_PHONE_NUM", "TEXT", 10),
    FieldDefinition(62, "LAST_RPT_SPONS_NAME", "TEXT", 70),
    FieldDefinition(63, "LAST_RPT_SPONS_EIN", "TEXT", 9),
    FieldDefinition(64, "LAST_RPT_PLAN_NUM", "TEXT", 3),
    FieldDefinition(65, "ADMIN_SIGNED_DATE", "TEXT", 30),
    FieldDefinition(66, "ADMIN_SIGNED_NAME", "TEXT", 35),
    FieldDefinition(67, "SPONS_SIGNED_DATE", "TEXT", 30),
    FieldDefinition(68, "SPONS_SIGNED_NAME", "TEXT", 35),
    FieldDefinition(69, "DFE_SIGNED_DATE", "TEXT", 30),
    FieldDefinition(70, "DFE_SIGNED_NAME", "TEXT", 35),
    FieldDefinition(71, "TOT_PARTCP_BOY_CNT", "NUMERIC"),
    FieldDefinition(72, "TOT_ACTIVE_PARTCP_CNT", "NUMERIC"),
    FieldDefinition(73, "RTD_SEP_PARTCP_RCVG_CNT", "NUMERIC"),
    FieldDefinition(74, "RTD_SEP_PARTCP_FUT_CNT", "NUMERIC"),
    FieldDefinition(75, "SUBTL_ACT_RTD_SEP_CNT", "NUMERIC"),
    FieldDefinition(76, "BENEF_RCVG_BNFT_CNT", "NUMERIC"),
    FieldDefinition(77, "TOT_ACT_RTD_SEP_BENEF_CNT", "NUMERIC"),
    FieldDefinition(78, "PARTCP_ACCOUNT_BAL_CNT", "NUMERIC"),
    FieldDefinition(79, "SEP_PARTCP_PARTL_VSTD_CNT", "NUMERIC"),
    FieldDefinition(80, "CONTRIB_EMPLRS_CNT", "NUMERIC"),
    FieldDefinition(81, "TYPE_PENSION_BNFT_CODE", "TEXT", 40),
    FieldDefinition(82, "TYPE_WELFARE_BNFT_CODE", "TEXT", 40),
    FieldDefinition(83, "FUNDING_INSURANCE_IND", "TEXT", 1),
    FieldDefinition(84, "FUNDING_SEC412_IND", "TEXT", 1),
    FieldDefinition(85, "FUNDING_TRUST_IND", "TEXT", 1),
    FieldDefinition(86, "FUNDING_GEN_ASSET_IND", "TEXT", 1),
    FieldDefinition(87, "BENEFIT_INSURANCE_IND", "TEXT", 1),
    FieldDefinition(88, "BENEFIT_SEC412_IND", "TEXT", 1),
    FieldDefinition(89, "BENEFIT_TRUST_IND", "TEXT", 1),
    FieldDefinition(90, "BENEFIT_GEN_ASSET_IND", "TEXT", 1),
    FieldDefinition(91, "SCH_R_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(92, "SCH_MB_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(93, "SCH_SB_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(94, "SCH_H_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(95, "SCH_I_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(96, "SCH_A_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(97, "NUM_SCH_A_ATTACHED_CNT", "TEXT", 4),
    FieldDefinition(98, "SCH_C_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(99, "SCH_D_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(100, "SCH_G_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(101, "FILING_STATUS", "TEXT", 50),
    FieldDefinition(102, "DATE_RECEIVED", "TEXT", 10),
    FieldDefinition(103, "VALID_ADMIN_SIGNATURE", "TEXT", 54),
    FieldDefinition(104, "VALID_DFE_SIGNATURE", "TEXT", 54),
    FieldDefinition(105, "VALID_SPONSOR_SIGNATURE", "TEXT", 54),
    FieldDefinition(106, "ADMIN_PHONE_NUM_FOREIGN", "TEXT", 30),
    FieldDefinition(107, "SPONS_DFE_PHONE_NUM_FOREIGN", "TEXT", 30),
    FieldDefinition(108, "ADMIN_NAME_SAME_SPON_IND", "TEXT", 1),
    FieldDefinition(109, "ADMIN_ADDRESS_SAME_SPON_IND", "TEXT", 1),
    FieldDefinition(110, "PREPARER_NAME", "TEXT", 35),
    FieldDefinition(111, "PREPARER_FIRM_NAME", "TEXT", 35),
    FieldDefinition(112, "PREPARER_US_ADDRESS1", "TEXT", 35),
    FieldDefinition(113, "PREPARER_US_ADDRESS2", "TEXT", 35),
    FieldDefinition(114, "PREPARER_US_CITY", "TEXT", 22),
    FieldDefinition(115, "PREPARER_US_STATE", "TEXT", 2),
    FieldDefinition(116, "PREPARER_US_ZIP", "TEXT", 12),
    FieldDefinition(117, "PREPARER_FOREIGN_ADDRESS1", "TEXT", 35),
    FieldDefinition(118, "PREPARER_FOREIGN_ADDRESS2", "TEXT", 35),
    FieldDefinition(119, "PREPARER_FOREIGN_CITY", "TEXT", 22),
    FieldDefinition(120, "PREPARER_FOREIGN_PROV_STATE", "TEXT", 22),
    FieldDefinition(121, "PREPARER_FOREIGN_CNTRY", "TEXT", 2),
    FieldDefinition(122, "PREPARER_FOREIGN_POSTAL_CD", "TEXT", 22),
    FieldDefinition(123, "PREPARER_PHONE_NUM", "TEXT", 10),
    FieldDefinition(124, "PREPARER_PHONE_NUM_FOREIGN", "TEXT", 30),
    FieldDefinition(125, "TOT_ACT_PARTCP_BOY_CNT", "NUMERIC"),
    FieldDefinition(126, "SUBJ_M1_FILING_REQ_IND", "TEXT", 1),
    FieldDefinition(127, "COMPLIANCE_M1_FILING_REQ_IND", "TEXT", 1),
    FieldDefinition(128, "M1_RECEIPT_CONFIRMATION_CODE", "TEXT", 12),
    FieldDefinition(129, "ADMIN_MANUAL_SIGNED_DATE", "TEXT", 30),
    FieldDefinition(130, "ADMIN_MANUAL_SIGNED_NAME", "TEXT", 35),
    FieldDefinition(131, "LAST_RPT_PLAN_NAME", "TEXT", 140),
    FieldDefinition(132, "SPONS_MANUAL_SIGNED_DATE", "TEXT", 30),
    FieldDefinition(133, "SPONS_MANUAL_SIGNED_NAME", "TEXT", 35),
    FieldDefinition(134, "DFE_MANUAL_SIGNED_DATE", "TEXT", 30),
    FieldDefinition(135, "DFE_MANUAL_SIGNED_NAME", "TEXT", 35),
    FieldDefinition(136, "ADOPTED_PLAN_PERM_SEC_ACT", "TEXT", 1),
    FieldDefinition(137, "PARTCP_ACCOUNT_BAL_CNT_BOY", "NUMERIC"),
    FieldDefinition(138, "SCH_DCG_ATTACHED_IND", "TEXT", 1),
    FieldDefinition(139, "NUM_SCH_DCG_ATTACHED_CNT", "NUMERIC"),
    FieldDefinition(140, "SCH_MEP_ATTACHED_IND", "TEXT", 1),
)


FIELD_BY_NAME: dict[str, FieldDefinition] = {
    field.name: field
    for field in FIELDS
}


FIELD_BY_POSITION: dict[int, FieldDefinition] = {
    field.position: field
    for field in FIELDS
}


IDENTITY_FIELDS = (
    "ACK_ID",
    "PLAN_NAME",
    "SPONS_DFE_PN",
    "SPONSOR_DFE_NAME",
    "SPONS_DFE_EIN",
    "FORM_PLAN_YEAR_BEGIN_DATE",
    "FORM_TAX_PRD",
)


SCHEDULE_ATTACHMENT_FIELDS = (
    "SCH_R_ATTACHED_IND",
    "SCH_MB_ATTACHED_IND",
    "SCH_SB_ATTACHED_IND",
    "SCH_H_ATTACHED_IND",
    "SCH_I_ATTACHED_IND",
    "SCH_A_ATTACHED_IND",
    "SCH_C_ATTACHED_IND",
    "SCH_D_ATTACHED_IND",
    "SCH_G_ATTACHED_IND",
    "SCH_DCG_ATTACHED_IND",
    "SCH_MEP_ATTACHED_IND",
)


PLAN_SEARCH_FIELDS = (
    "PLAN_NAME",
    "SPONSOR_DFE_NAME",
    "SPONS_DFE_DBA_NAME",
    "SPONS_DFE_EIN",
    "SPONS_DFE_PN",
    "SPONS_DFE_LOC_US_CITY",
    "SPONS_DFE_LOC_US_STATE",
    "SPONS_DFE_LOC_US_ZIP",
)


def get_field(name: str) -> FieldDefinition:
    """Return a field definition by exact field name."""

    try:
        return FIELD_BY_NAME[name]
    except KeyError as exc:
        raise KeyError(
            f"Unknown 2025 Form 5500 field: {name}"
        ) from exc


def validate_schema() -> None:
    """Validate the 2025 Form 5500 schema."""

    if len(FIELDS) != 140:
        raise ValueError(
            f"Expected 140 fields, found {len(FIELDS)}."
        )

    positions = [field.position for field in FIELDS]

    if positions != list(range(1, 141)):
        raise ValueError(
            "Field positions must contain every position "
            "from 1 through 140 exactly once."
        )

    names = [field.name for field in FIELDS]

    if len(names) != len(set(names)):
        raise ValueError("Duplicate field names detected.")

    for field in FIELDS:
        if field.field_type == "TEXT":
            if field.size is None or field.size <= 0:
                raise ValueError(
                    f"Invalid text size for {field.name}."
                )
        elif field.field_type == "NUMERIC":
            if field.size is not None:
                raise ValueError(
                    f"Numeric field {field.name} must not have a text size."
                )
        else:
            raise ValueError(
                f"Unsupported field type: {field.field_type}"
            )


validate_schema()