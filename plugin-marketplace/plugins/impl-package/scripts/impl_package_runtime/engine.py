"""Ticket-first Impl-Package state runtime (format 3.6, Journey acceptance).

The runtime has one state axis: Tickets.  A package whose state is not
formatVersion 3.6 is rejected.

This module is the stable facade: the implementation lives in the sibling
modules (state_core, attempt_store, spec_journey, plan_tickets,
journey_evidence, acceptance, validate_state, cmd_*) and is re-exported here so
command_groups, situation and tests keep addressing `engine.<name>`.
"""
# ruff: noqa: F401

from __future__ import annotations

import subprocess

from situation import (
    evidence_record_valid,
    terminal_coverage_fact,
)

from .state_core import (
    STATE_PATH,
    FORMAT_VERSION,
    TERMINAL_VERDICTS,
    VERDICTS,
    DISPOSITIONS,
    RETIRED_DISPATCH_FIELDS,
    StateError,
    git_query_scope,
    _run_git_result,
    _invalidate_working_tree_hash,
    _run_git,
    _repo_root,
    _load_json,
    _write_text,
    _write_json,
    _utc_timestamp,
    _validate_iso_timestamp,
    _validate_commit,
    _is_ancestor,
    _state_format_version,
    require_current_format,
)
from .attempt_store import (
    _gate_info,
    _lifecycle,
    _set_execution_record_status,
    _active_trail_rows,
    _same_event,
)
from .spec_journey import (
    _journey_spec_text,
    _journey_spec,
    _frozen_journey_spec,
    _journey_expected_surface,
    validate_spec_document,
)
from .plan_tickets import (
    _plan_info,
    _ticket_documents,
    _ticket_dependencies,
    _pending_amendments,
    command_check_spec,
)
from .journey_evidence import (
    _package_relative_artifact,
    _validate_journey_surface_evidence,
    _normalize_journey_evidence,
)
from .acceptance import (
    _v36_acceptance_status,
)
from .validate_state import (
    ready_tickets,
    _validate_state,
    _refresh_projections,
)
from .cmd_evidence import (
    _assert_mutable,
    _v36_record_valid,
    _validate_first_step_object_is_new,
    _validate_journey_step_order,
    command_evidence_add,
    command_evidence_invalidate,
    command_evidence_carry_forward,
    command_set_state,
    command_er_add,
)
from .cmd_package import (
    command_archive_attempt,
    command_init,
    command_validate,
    command_refresh_progress,
    command_amendment_add,
    command_amendment_confirm,
    command_amendment_supersede,
    command_amendment_withdraw,
    command_sync_predecessors,
)
from .cmd_trail import (
    command_lease_acquire,
    command_lease_release,
    _validate_trail_event,
    command_trail_append,
)
from .cmd_gate import (
    command_checkpoint,
    _owner_summary,
    command_gate,
)
