"""Domain entity models — patients, encounters, claims, denials, payers."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class Patient(BaseModel):
    patient_id: str
    first_name: str
    last_name: str
    dob: date
    gender: str
    address_line1: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    mrn: str
    primary_payer_id: Optional[str] = None
    secondary_payer_id: Optional[str] = None
    propensity_score: float = 0.5
    language_pref: str = "EN"
    created_at: Optional[datetime] = None


class Payer(BaseModel):
    payer_id: str
    payer_name: str
    payer_type: str
    payer_id_x12_fictional: str
    avg_days_to_pay: int
    denial_rate_baseline: float
    timely_filing_days: int
    fee_schedule_multiplier: float
    portal_mock_url: str


class Encounter(BaseModel):
    encounter_id: str
    patient_id: str
    provider_npi: str
    facility_npi: str
    encounter_type: str
    service_date: date
    discharge_date: Optional[date] = None
    place_of_service: str
    attending_physician: str
    chief_complaint: Optional[str] = None
    soap_note_text: Optional[str] = None
    scenario_id: Optional[str] = None
    auth_required: bool = False
    auth_status: Optional[str] = None
    charge_lag_days: int = 0
    status: str = "Scheduled"


class ClaimLine(BaseModel):
    line_id: str
    claim_id: str
    cpt_code: str
    icd10_primary: str
    icd10_secondary: Optional[str] = None
    modifier: Optional[str] = None
    units: int = 1
    charge_amount: Decimal
    allowed_amount: Optional[Decimal] = None
    revenue_code: Optional[str] = None
    ndc_code: Optional[str] = None
    coding_confidence: Optional[float] = None


class Claim(BaseModel):
    claim_id: str
    encounter_id: str
    claim_type: str
    payer_id: str
    total_billed: Decimal
    total_allowed: Optional[Decimal] = None
    total_paid: Optional[Decimal] = None
    patient_responsibility: Optional[Decimal] = None
    submission_date: Optional[date] = None
    adjudication_date: Optional[date] = None
    claim_status: str
    rejection_reason: Optional[str] = None
    timely_filing_deadline: Optional[date] = None
    scrub_score: Optional[float] = None
    appeal_id: Optional[str] = None
    era_posted: bool = False


class ClaimWithLines(Claim):
    lines: list[ClaimLine] = Field(default_factory=list)


class Denial(BaseModel):
    denial_id: str
    claim_id: str
    carc_code: str
    rarc_code: Optional[str] = None
    denial_category: str
    denial_date: date
    appeal_deadline: Optional[date] = None
    agent_root_cause: Optional[str] = None
    appeal_letter_text: Optional[str] = None
    appeal_submitted_at: Optional[datetime] = None
    overturn_date: Optional[date] = None
    overturn_flag: bool = False


class EligibilityResponse(BaseModel):
    eligibility_id: str
    patient_id: str
    payer_id: str
    verified_at: datetime
    copay: Decimal
    deductible_remaining: Decimal
    oop_remaining: Decimal
    in_network: bool
    plan_type: str
    response_json: Optional[str] = None
