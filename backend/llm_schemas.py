from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, RootModel, ValidationError, model_validator


class _BaseSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")


class CriterionSchema(_BaseSchema):
    id: str
    name: str
    max_points: float | int
    checklist_signals: list[str] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)
    description: str | None = None


class GateSchema(_BaseSchema):
    gate_id: str
    name: str
    type: str
    max_points: float | int | None = None
    advancement_threshold: float | int | str | None = None
    criteria: list[CriterionSchema] = Field(default_factory=list)


class PoisonPillClauseSchema(_BaseSchema):
    id: str
    clause_text: str
    page_number: int | float | str
    trigger_condition: str
    severity: str


class RFPExtractionSchema(_BaseSchema):
    rfp_id: str = ""
    issuer: str = ""
    gates: list[GateSchema] = Field(default_factory=list)
    poison_pill_clauses: list[PoisonPillClauseSchema] = Field(default_factory=list)
    submission_rules: list[str] = Field(default_factory=list)
    wps_formula: str = ""


class PoisonPillSweepSchema(_BaseSchema):
    found: bool
    clause_text: str | None = None
    reason: str | None = None
    severity: str | None = None

    @model_validator(mode="after")
    def validate_found_payload(self) -> "PoisonPillSweepSchema":
        if self.found and not (self.clause_text or "").strip():
            raise ValueError("clause_text is required when found=true")
        return self


class BatchCriterionBooleanSchema(_BaseSchema):
    """
    Boolean-per-signal schema for criterion scoring.

    The LLM returns one explicit true/false per checklist signal rather than a
    list of matched strings.  This decouples LLM *reasoning* from Python
    *math*: the LLM decides what evidence it sees (boolean facts); Python
    derives matched_signals / gap_signals deterministically from those booleans
    — no fuzzy string normalisation required.

    Example LLM output for one criterion:
      {
        "c1": {
          "signals": {
            "Provides detailed project timeline": true,
            "Budget breakdown included":         false,
            "Risk management plan attached":     true
          }
        }
      }
    """
    signals: dict[str, bool] = Field(default_factory=dict)
    # key   = checklist signal text (echoed verbatim from the prompt)
    # value = True if the retrieved excerpts explicitly evidence the signal


class BatchCriterionBooleansSchema(RootModel[dict[str, BatchCriterionBooleanSchema]]):
    pass


class ParsedPoisonPillSchema(_BaseSchema):
    clause_text: str
    page_number: int
    severity: Literal["CRITICAL", "HIGH", "MEDIUM"]
    reason: str
    source: Literal["parser", "sweep"]


def _raise_validation_error(label: str, exc: ValidationError) -> None:
    raise ValueError(f"Invalid {label} payload: {exc}") from exc


def validate_rfp_extraction_payload(data: dict) -> RFPExtractionSchema:
    try:
        return RFPExtractionSchema.model_validate(data)
    except ValidationError as exc:
        _raise_validation_error("RFP extraction", exc)


def validate_poison_pill_sweep_payload(data: dict) -> PoisonPillSweepSchema:
    try:
        return PoisonPillSweepSchema.model_validate(data)
    except ValidationError as exc:
        _raise_validation_error("poison pill sweep", exc)


def validate_batch_criterion_payload(data: dict) -> BatchCriterionBooleansSchema:
    try:
        return BatchCriterionBooleansSchema.model_validate(data)
    except ValidationError as exc:
        _raise_validation_error("criterion batch", exc)
