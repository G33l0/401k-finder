"""Form 5500 field schemas."""

from __future__ import annotations

from dataclasses import dataclass

from app.dol.layouts import FieldDefinition, Layout, available_years, get_layout

IDENTITY_FIELDS: dict[str, tuple[str, ...]] = {
    "F_5500": (
        "ACK_ID",
        "PLAN_NAME",
        "SPONS_DFE_PN",
        "SPONSOR_DFE_NAME",
        "SPONS_DFE_EIN",
        "FORM_PLAN_YEAR_BEGIN_DATE",
        "FORM_TAX_PRD",
    ),
    "F_5500_SF": (
        "ACK_ID",
        "SF_PLAN_NAME",
        "SF_PLAN_NUM",
        "SF_SPONSOR_NAME",
        "SF_SPONS_EIN",
        "SF_PLAN_YEAR_BEGIN_DATE",
        "SF_TAX_PRD",
    ),
    "F_SCH_DCG": (
        "ACK_ID",
        "DCG_PLAN_NAME",
        "DCG_PLAN_NUM",
        "DCG_SPONSOR_NAME",
        "DCG_SPONS_EIN",
    ),
}

SEARCH_FIELDS: dict[str, tuple[str, ...]] = {
    "F_5500": (
        "PLAN_NAME",
        "SPONSOR_DFE_NAME",
        "SPONS_DFE_DBA_NAME",
        "SPONS_DFE_EIN",
        "SPONS_DFE_PN",
        "SPONS_DFE_LOC_US_CITY",
        "SPONS_DFE_LOC_US_STATE",
        "SPONS_DFE_LOC_US_ZIP",
    ),
    "F_5500_SF": (
        "SF_PLAN_NAME",
        "SF_SPONSOR_NAME",
        "SF_SPONSOR_DFE_DBA_NAME",
        "SF_SPONS_EIN",
        "SF_PLAN_NUM",
        "SF_SPONS_LOC_US_CITY",
        "SF_SPONS_LOC_US_STATE",
        "SF_SPONS_LOC_US_ZIP",
    ),
}

SCHEDULE_ATTACHMENT_FIELDS: tuple[str, ...] = (
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


@dataclass(frozen=True, slots=True)
class Schema:
    """A dataset's published layout, plus what the application knows about it."""

    layout: Layout

    @property
    def form_year(self) -> int:
        return self.layout.form_year

    @property
    def dataset(self) -> str:
        return self.layout.dataset

    @property
    def fields(self) -> tuple[FieldDefinition, ...]:
        return self.layout.fields

    @property
    def field_names(self) -> tuple[str, ...]:
        return self.layout.field_names

    @property
    def identity_fields(self) -> tuple[str, ...]:
        return tuple(
            name for name in IDENTITY_FIELDS.get(self.dataset, ()) if self.layout.has(name)
        )

    @property
    def search_fields(self) -> tuple[str, ...]:
        return tuple(name for name in SEARCH_FIELDS.get(self.dataset, ()) if self.layout.has(name))

    @property
    def schedule_attachment_fields(self) -> tuple[str, ...]:
        return tuple(name for name in SCHEDULE_ATTACHMENT_FIELDS if self.layout.has(name))

    def get_field(self, name: str) -> FieldDefinition:
        field = self.layout.get(name)

        if field is None:
            raise KeyError(f"{self.dataset} {self.form_year} has no field named {name}.")

        return field

    def has_field(self, name: str) -> bool:
        return self.layout.has(name)

    def numeric_fields(self) -> tuple[str, ...]:
        return self.layout.numeric_names()


def get_schema(form_year: int, dataset: str = "F_5500") -> Schema:
    """Return a dataset's schema for a form year."""

    layout = get_layout(form_year, dataset)

    if layout is None:
        raise KeyError(f"DOL did not publish {dataset} for form year {form_year}.")

    return Schema(layout=layout)


def has_schema(form_year: int, dataset: str = "F_5500") -> bool:
    return get_layout(form_year, dataset) is not None


def supported_years() -> tuple[int, ...]:
    return available_years()


__all__ = (
    "IDENTITY_FIELDS",
    "SCHEDULE_ATTACHMENT_FIELDS",
    "SEARCH_FIELDS",
    "Schema",
    "get_schema",
    "has_schema",
    "supported_years",
)
