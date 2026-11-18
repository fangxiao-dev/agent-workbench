"""Ticket-first Impl-Package state runtime (format 3.6, Journey acceptance).

The runtime has one state axis: Tickets.  A package whose state is not
formatVersion 3.6 is rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
import zipfile
from contextvars import ContextVar
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from situation import (
    dispatch_admission,
    ValidationResult,
    FACT_KEYS,
    REVIEW_PHASES,
    REVIEW_PHASE_VALUES,
    REVIEW_TRACKS,
    REVIEW_TRACK_VALUES,
    describe_unknown_fact_keys,
    carried_forward_error,
    evidence_record_valid,
    evidence_revision_coverage,
    live_package_reference_fact,
    terminal_coverage_fact,
)

#<<FACADE>>
from .state_core import (
    STATE_PATH,
    ATTEMPT_ARCHIVE_PATH,
    PROGRESS_PATH,
    EXECUTION_PATH,
    ACTIVE_TRAIL_NAME,
    TRAIL_ARCHIVE_RE,
    GATE_PATH,
    FORMAT_VERSION,
    TICKET_STATES,
    TERMINAL_VERDICTS,
    VERDICTS,
    TIMINGS,
    CONCLUSIONS,
    DISPOSITIONS,
    TRAIL_APPEND_KINDS,
    RETIRED_DISPATCH_FIELDS,
    TRAIL_COMMON_FIELDS,
    FIXED_COMMIT_RE,
    LEASE_ID_RE,
    LEASE_FILE_RE,
    ATTEMPT_RE,
    COMPOSITION_RE,
    DECISION_RE,
    SPEC_RE,
    PLAN_RE,
    PREDECESSORS_RE,
    ACCEPTANCE_JOURNEY_RE,
    RELEASE_ORDER_RE,
    TICKET_ID_RE,
    PUBLICATION_RE,
    BATCH_ESTIMATE_RE,
    ARRIVAL_PATH_RE,
    DEPENDENCY_HEADING_RE,
    ARRIVAL_SEGMENT_RE,
    ER_ENTRY_RE,
    COMMIT_RE,
    PACKAGE_ID_RE,
    ATTEMPT_ID_RE,
    StateError,
    Lifecycle,
    _GitResult,
    _git_query_cache,
    git_query_scope,
    _cacheable_git_query,
    _hash_object_paths,
    _run_git_result,
    _invalidate_working_tree_hash,
    _run_git,
    _repo_root,
    _read,
    _load_json,
    _write_text,
    _write_json,
    _utc_timestamp,
    _validate_iso_timestamp,
    _repo_relative,
    _validate_commit,
    _is_ancestor,
    _state_format_version,
    require_current_format,
)
from .attempt_store import (
    _attempt_archive_path,
    _ticket_snapshot,
    _write_attempt_archive,
    _trail_path,
    _trail_identity,
    _trail_append_lock,
    _trail_next_seq,
    _append_trail,
    _best_effort_trail,
    _best_effort_result,
    _next_trail_archive,
    _rotate_trail,
    _best_effort_trail_rotation,
    _valid_successor,
    _gate_info,
    _lifecycle,
    _approve_ticket,
    _execution_record_path,
    _new_execution_record,
    _ensure_execution_record,
    _entry_field,
    _parse_execution_record,
    _set_execution_record_status,
    _trail_text_field,
    _active_trail_rows,
    _same_event,
)
from .spec_journey import (
    _markdown_section,
    _table_cells,
    _markdown_table,
    _chapter_headings,
    _chapter_references,
    _resolve_chapter_reference,
    _chapter_label,
    _spec_coverage_findings,
    _journey_spec_text,
    _journey_spec,
    _frozen_journey_spec,
    _journey_expected_surface,
    validate_spec_document,
    _coverage_list,
    _ticket_coverage,
    _journey_coverage_errors,
    _validate_journey_coverage,
)
from .plan_tickets import (
    _field,
    _predecessors_from_plan,
    _normalize_state_predecessors,
    _package_relative,
    HARNESS_PLAN_FORMATS,
    _harness_from_plan,
    _validate_first_visible_step,
    _plan_info,
    _arrival_paths,
    _ticket_documents,
    _batch_estimate_absent_findings,
    _append_ticket_document,
    _ticket_dependencies,
    _reject_cycles,
    _git_grep_symbol,
    PLAN_GATE_RE,
    CONTRACT_DOC_NAMES,
    _contains_ticket_id,
    _contract_doc_name_findings,
    _plan_prose_gate_findings,
    _arrival_path_absent_findings,
    _arrival_findings,
    _working_tree_blobs,
    _contract_baseline,
    _pending_amendments,
    _contract_amendment_findings,
    _post_gate_pending_findings,
    command_check_spec,
)
from .journey_evidence import (
    _package_relative_artifact,
    _trace_action_method,
    _trace_action_description,
    _playwright_trace_actions,
    _validate_journey_surface_evidence,
    _validate_journey_evidence_index,
    _evidence_field_error,
    _normalize_journey_evidence,
)
from .acceptance import (
    _escape,
    _format_aliases,
    _v36_acceptance_status,
    _journey_reaches,
    _render_progress,
    _validate_projections,
)
from .validate_state import (
    _validate_checkpoints,
    _attempt_history,
    ready_tickets,
    _ticket_released,
    _validate_acceptance_state,
    _validate_state,
    _refresh_projections,
    _public,
)
from .cmd_evidence import (
    _assert_mutable,
    _v36_record_valid,
    _ticket_owned_evidence_keys,
    _v36_ticket_satisfy_gaps,
    _validate_first_step_object_is_new,
    _validate_journey_step_order,
    command_evidence_add,
    command_evidence_invalidate,
    command_evidence_carry_forward,
    command_set_state,
    _add_judgment,
    command_er_add,
)
from .cmd_package import (
    command_archive_attempt,
    command_init,
    command_validate,
    command_refresh_progress,
    AMENDMENT_CONTRACT_FILES,
    _amendment_post_gate,
    _post_gate_spec_drift,
    command_amendment_add,
    command_amendment_confirm,
    _amendment_transition,
    command_amendment_supersede,
    command_amendment_withdraw,
    command_sync_predecessors,
)
from .cmd_trail import (
    validate_dispatch_receipt,
    _validate_resource_keys,
    _lease_directory,
    _lease_record_path,
    _read_lease_records,
    command_lease_acquire,
    command_lease_release,
    _validate_dispatch_lease,
    _validate_code_delta,
    _validate_review_pending,
    _validate_review_dispatch_fields,
    _merge_trail_named_fields,
    _validate_trail_event,
    _current_validation_result,
    _validate_actual_dispatch,
    _validate_worker_return,
    _validate_review_pending_against_return,
    command_trail_append,
)
from .cmd_gate import (
    command_checkpoint,
    _update_history,
    _v36_gate_gaps,
    _owner_summary,
    _best_effort_metrics_path,
    command_gate,
)
#<<END>>


