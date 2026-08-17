"""
Trace a person's retirement accounts from their work history.

Form 5500 names employers, plans, and the firms holding the money — but no
participants. So this answers "which plan would my old job's 401(k) be in, and
who do I write to", not "is there an account in my name". The second question is
answered by the registries in :mod:`app.trace.resources`, which hold
participant-level data this application has no access to.

    from app.trace import AccountTracer, WorkHistory

    history = WorkHistory()
    history.add("Acme Manufacturing", state="OH", start_year=2008, end_year=2012)

    report = AccountTracer(session).trace(history)
"""

from app.trace.history import Employment, WorkHistory, looks_like_ssn, redact
from app.trace.matcher import AccountTracer, Holder, JobTrace, PlanMatch, TraceReport
from app.trace.resources import RESOURCES, Audience, Resource, for_audience

__all__ = (
    "RESOURCES",
    "AccountTracer",
    "Audience",
    "Employment",
    "Holder",
    "JobTrace",
    "PlanMatch",
    "Resource",
    "TraceReport",
    "WorkHistory",
    "for_audience",
    "looks_like_ssn",
    "redact",
)
