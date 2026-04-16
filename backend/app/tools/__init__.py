"""Agent tools — thin wrappers around DuckDB + mock payer that agents invoke."""

from app.tools.patient_tools import (
    get_patient_demographics,
    get_patient_insurance,
    get_patient_contact_preferences,
    get_patient_propensity,
)
from app.tools.eligibility_tools import (
    query_payer_eligibility,
    write_eligibility_result,
    flag_missing_info,
)
from app.tools.coding_tools import (
    get_encounter_note,
    get_patient_history,
    search_cpt_codes,
    search_icd10_codes,
    validate_code_combination,
    write_coding_suggestion,
)
from app.tools.claim_tools import (
    get_claim_with_lines,
    get_payer_edit_rules,
    check_lcd_ncd,
    check_bundling_rules,
    get_prior_auth_status,
    predict_rejection_probability,
    write_scrub_result,
    get_submitted_claims,
    query_payer_claim_status,
    get_contract_allowable,
    flag_underpayment,
    flag_timely_filing_risk,
    update_claim_status,
)
from app.tools.era_tools import (
    get_unposted_eras,
    get_claim_by_service_info,
    post_payment,
    create_patient_statement,
    route_exception,
)
from app.tools.denial_tools import (
    get_denial_detail,
    get_claim_detail,
    get_prior_auth_record,
    get_clinical_documentation,
    classify_denial_root_cause,
    calculate_appeal_deadline,
    get_appeal_template,
    render_appeal_letter,
    submit_appeal,
)
from app.tools.collections_tools import (
    get_patient_balances,
    check_charity_care_eligibility,
    generate_statement,
    generate_payment_plan,
    send_outreach,
)
from app.tools.analytics_tools import (
    get_ar_aging_snapshot,
    get_kpi_timeseries,
    get_denial_rate_by_payer,
    get_first_pass_rate,
    get_days_in_ar_by_payer,
    compute_cash_forecast,
    write_analytics_alert,
)

__all__: list[str] = []
