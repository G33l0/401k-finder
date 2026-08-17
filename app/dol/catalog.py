"""
The catalog of downloadable DOL Form 5500 datasets.

EBSA publishes one ZIP per dataset per form year at a stable URL::

    https://askebsa.dol.gov/FOIA Files/<year>/<release>/<dataset>_<year>_<release>.zip
    https://askebsa.dol.gov/FOIA Files/<year>/<release>/<dataset>_<year>_<release>_layout.txt

``release`` is ``Latest`` (one row per plan year, superseded filings removed)
or ``All`` (every filing received, including amendments and duplicates).

Which datasets exist varies by year — Schedule DCG and Schedule MEP only start
in 2023, for example — so availability is read from the vendored layouts rather
than assumed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import quote

from app.core.constants import DOL_FILE_BASE_URL, FormType, ProviderRole
from app.dol.layouts import available_datasets, available_years, get_layout


class Release(StrEnum):
    """Which DOL release of a form year to work with."""

    LATEST = "Latest"
    ALL = "All"


class DatasetKind(StrEnum):
    """How the importer should treat a dataset."""

    #: Carries plan identity; creates plans and filings.
    FILING = "FILING"
    #: Attaches to a filing by ACK_ID; one row per filing.
    SCHEDULE = "SCHEDULE"
    #: Attaches to a filing by ACK_ID; many rows per filing (ROW_ORDER).
    SCHEDULE_DETAIL = "SCHEDULE_DETAIL"


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """A single downloadable DOL dataset, independent of form year."""

    name: str
    title: str
    kind: DatasetKind
    schedule_code: str
    #: Roles this dataset can contribute; used to plan a provider-focused sync.
    provider_roles: tuple[ProviderRole, ...] = ()
    form_type: FormType | None = None
    #: Rough share of a year's total download volume, for progress weighting.
    weight: int = 1

    @property
    def is_filing(self) -> bool:
        return self.kind is DatasetKind.FILING


#: Every dataset published on the EBSA Form 5500 dataset page.
DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        "F_5500",
        "Form 5500 (main form)",
        DatasetKind.FILING,
        "5500",
        (ProviderRole.ADMINISTRATOR, ProviderRole.PREPARER),
        FormType.FORM_5500,
        weight=10,
    ),
    DatasetSpec(
        "F_5500_SF",
        "Form 5500-SF (short form)",
        DatasetKind.FILING,
        "5500-SF",
        (
            ProviderRole.ADMINISTRATOR,
            ProviderRole.PREPARER,
            ProviderRole.TRUST,
            ProviderRole.TRUSTEE,
        ),
        FormType.FORM_5500_SF,
        weight=12,
    ),
    DatasetSpec(
        "F_SCH_DCG",
        "Schedule DCG (defined contribution group)",
        DatasetKind.FILING,
        "DCG",
        (ProviderRole.ADMINISTRATOR, ProviderRole.ACCOUNTANT),
        FormType.FORM_5500_DCG,
        weight=3,
    ),
    DatasetSpec(
        "F_SCH_A",
        "Schedule A (insurance information)",
        DatasetKind.SCHEDULE_DETAIL,
        "A",
        (ProviderRole.INSURER,),
        weight=8,
    ),
    DatasetSpec(
        "F_SCH_A_PART1",
        "Schedule A Part 1 (insurance brokers)",
        DatasetKind.SCHEDULE_DETAIL,
        "A-1",
        (ProviderRole.BROKER,),
        weight=4,
    ),
    DatasetSpec("F_SCH_C", "Schedule C (service providers)", DatasetKind.SCHEDULE, "C", weight=1),
    DatasetSpec(
        "F_SCH_C_PART1_ITEM1",
        "Schedule C Part 1 Item 1 (eligible indirect compensation)",
        DatasetKind.SCHEDULE_DETAIL,
        "C-1-1",
        (ProviderRole.SERVICE_PROVIDER,),
        weight=2,
    ),
    DatasetSpec(
        "F_SCH_C_PART1_ITEM2",
        "Schedule C Part 1 Item 2 (service providers and compensation)",
        DatasetKind.SCHEDULE_DETAIL,
        "C-1-2",
        (
            ProviderRole.RECORDKEEPER,
            ProviderRole.TRUSTEE,
            ProviderRole.CUSTODIAN,
            ProviderRole.INVESTMENT_MANAGER,
            ProviderRole.INVESTMENT_ADVISOR,
            ProviderRole.THIRD_PARTY_ADMIN,
            ProviderRole.ACCOUNTANT,
            ProviderRole.ACTUARY,
            ProviderRole.BROKER,
            ProviderRole.CONSULTANT,
        ),
        weight=6,
    ),
    DatasetSpec(
        "F_SCH_C_PART1_ITEM3",
        "Schedule C Part 1 Item 3 (indirect compensation detail)",
        DatasetKind.SCHEDULE_DETAIL,
        "C-1-3",
        (ProviderRole.PAYOR, ProviderRole.SERVICE_PROVIDER),
        weight=2,
    ),
    DatasetSpec(
        "F_SCH_C_PART2",
        "Schedule C Part 2 (providers that failed to supply information)",
        DatasetKind.SCHEDULE_DETAIL,
        "C-2",
        (ProviderRole.SERVICE_PROVIDER,),
    ),
    DatasetSpec(
        "F_SCH_C_PART3",
        "Schedule C Part 3 (terminated accountants and actuaries)",
        DatasetKind.SCHEDULE_DETAIL,
        "C-3",
        (ProviderRole.TERMINATED_ACCOUNTANT,),
    ),
    DatasetSpec("F_SCH_D", "Schedule D (DFE/participating plan information)", DatasetKind.SCHEDULE, "D"),
    DatasetSpec(
        "F_SCH_D_PART1",
        "Schedule D Part 1 (interests in DFEs held by the plan)",
        DatasetKind.SCHEDULE_DETAIL,
        "D-1",
        (ProviderRole.INVESTMENT_VEHICLE,),
        weight=4,
    ),
    DatasetSpec(
        "F_SCH_D_PART2",
        "Schedule D Part 2 (plans participating in this DFE)",
        DatasetKind.SCHEDULE_DETAIL,
        "D-2",
        weight=3,
    ),
    DatasetSpec("F_SCH_G", "Schedule G (financial transaction schedules)", DatasetKind.SCHEDULE, "G"),
    DatasetSpec("F_SCH_G_PART1", "Schedule G Part 1 (loans or fixed income in default)", DatasetKind.SCHEDULE_DETAIL, "G-1"),
    DatasetSpec("F_SCH_G_PART2", "Schedule G Part 2 (leases in default)", DatasetKind.SCHEDULE_DETAIL, "G-2"),
    DatasetSpec("F_SCH_G_PART3", "Schedule G Part 3 (non-exempt transactions)", DatasetKind.SCHEDULE_DETAIL, "G-3"),
    DatasetSpec(
        "F_SCH_H",
        "Schedule H (large plan financial information)",
        DatasetKind.SCHEDULE,
        "H",
        (ProviderRole.ACCOUNTANT, ProviderRole.TRUST, ProviderRole.TRUSTEE),
        weight=8,
    ),
    DatasetSpec("F_SCH_H_PART1", "Schedule H Part 1 (transfers to other plans)", DatasetKind.SCHEDULE_DETAIL, "H-1"),
    DatasetSpec(
        "F_SCH_I",
        "Schedule I (small plan financial information)",
        DatasetKind.SCHEDULE,
        "I",
        (ProviderRole.TRUST, ProviderRole.TRUSTEE),
        weight=4,
    ),
    DatasetSpec(
        "F_SCH_R",
        "Schedule R (retirement plan information)",
        DatasetKind.SCHEDULE,
        "R",
        weight=5,
    ),
    DatasetSpec("F_SCH_R_PART1", "Schedule R Part 1 (contributing employers)", DatasetKind.SCHEDULE_DETAIL, "R-1"),
    DatasetSpec("F_SCH_MB", "Schedule MB (multiemployer actuarial information)", DatasetKind.SCHEDULE, "MB"),
    DatasetSpec("F_SCH_MB_PART1", "Schedule MB Part 1 (withdrawn employer detail)", DatasetKind.SCHEDULE_DETAIL, "MB-1"),
    DatasetSpec("F_SCH_SB", "Schedule SB (single-employer actuarial information)", DatasetKind.SCHEDULE, "SB"),
    DatasetSpec("F_SCH_SB_PART1", "Schedule SB Part 1 (amortization bases)", DatasetKind.SCHEDULE_DETAIL, "SB-1"),
    DatasetSpec(
        "F_SCH_MEP",
        "Schedule MEP (multiple-employer plan information)",
        DatasetKind.SCHEDULE,
        "MEP",
        (ProviderRole.POOLED_PLAN_PROVIDER,),
    ),
)

DATASETS_BY_NAME: dict[str, DatasetSpec] = {spec.name: spec for spec in DATASETS}

#: The minimum set that answers "who holds this retirement account". Downloading
#: these gives a complete provider picture at roughly a third of the volume of a
#: full year.
CORE_DATASET_NAMES: tuple[str, ...] = (
    "F_5500",
    "F_5500_SF",
    "F_SCH_A",
    "F_SCH_C_PART1_ITEM2",
    "F_SCH_D_PART1",
    "F_SCH_H",
    # Small, and the only source for where a wound-up plan's assets went.
    "F_SCH_H_PART1",
    "F_SCH_I",
    "F_SCH_R",
    "F_SCH_DCG",
    "F_SCH_MEP",
)


#: The smallest set that still answers "which plan did my employer run".
#:
#: The two filing forms carry sponsor name, EIN, plan number, plan name and
#: location — everything the employer match needs. They are a small fraction of
#: a full year, which is what makes it practical to index every published year
#: on an ordinary machine rather than importing one year and hoping it is the
#: right one.
#:
#: What an index-only year cannot do is name a provider: every asset holder
#: lives on a schedule, and schedules are what the size is.
INDEX_DATASET_NAMES: tuple[str, ...] = (
    "F_5500",
    "F_5500_SF",
)


@dataclass(frozen=True, slots=True)
class DatasetRelease:
    """A dataset bound to a specific form year and release."""

    spec: DatasetSpec
    form_year: int
    release: Release

    @property
    def stem(self) -> str:
        return f"{self.spec.name}_{self.form_year}_{self.release.value}"

    @property
    def archive_name(self) -> str:
        return f"{self.stem}.zip"

    @property
    def layout_name(self) -> str:
        return f"{self.stem}_layout.txt"

    @property
    def base_url(self) -> str:
        return f"{DOL_FILE_BASE_URL}/{self.form_year}/{quote(self.release.value)}"

    @property
    def archive_url(self) -> str:
        return f"{self.base_url}/{self.archive_name}"

    @property
    def layout_url(self) -> str:
        return f"{self.base_url}/{self.layout_name}"

    @property
    def name(self) -> str:
        return self.spec.name

    def layout(self):  # -> Layout | None
        """Return the vendored layout for this dataset and year."""

        return get_layout(self.form_year, self.spec.name)


def dataset_names_for_year(form_year: int) -> tuple[str, ...]:
    """Return the datasets DOL actually published for a form year."""

    published = set(available_datasets(form_year))
    return tuple(spec.name for spec in DATASETS if spec.name in published)


def is_available(form_year: int, dataset: str) -> bool:
    return dataset.upper() in set(available_datasets(form_year))


def resolve(
    form_year: int,
    dataset: str,
    release: Release = Release.LATEST,
) -> DatasetRelease:
    """Resolve one dataset for one year, raising if the pairing is unknown."""

    spec = DATASETS_BY_NAME.get(dataset.upper())
    if spec is None:
        raise KeyError(f"Unknown DOL dataset: {dataset}")

    if not is_available(form_year, spec.name):
        raise KeyError(f"DOL did not publish {spec.name} for form year {form_year}.")

    return DatasetRelease(spec=spec, form_year=form_year, release=release)


def plan_sync(
    form_year: int,
    release: Release = Release.LATEST,
    datasets: tuple[str, ...] | None = None,
    core_only: bool = False,
    index_only: bool = False,
) -> tuple[DatasetRelease, ...]:
    """
    Build the ordered list of datasets to fetch for a form year.

    Filing datasets are ordered first: schedules attach to filings by ACK_ID, so
    importing them first means every schedule row finds its parent.

    ``index_only`` narrows this to the two filing forms — enough to match an
    employer to a plan, and small enough to do for every published year.
    """

    if datasets is not None:
        wanted = {name.upper() for name in datasets}
    elif index_only:
        wanted = set(INDEX_DATASET_NAMES)
    elif core_only:
        wanted = set(CORE_DATASET_NAMES)
    else:
        wanted = {spec.name for spec in DATASETS}

    available = set(dataset_names_for_year(form_year))
    selected = [
        DatasetRelease(spec=spec, form_year=form_year, release=release)
        for spec in DATASETS
        if spec.name in wanted and spec.name in available
    ]

    selected.sort(key=lambda item: (not item.spec.is_filing, item.spec.name))
    return tuple(selected)


def supported_years() -> tuple[int, ...]:
    """Return every form year this installation can work with offline."""

    return available_years()
