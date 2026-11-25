"""Sincronización de solo lectura desde Tally hacia la copia local."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable

from ..api.client import MAX_PAGE_SIZE, TallyClient
from ..api.errors import ApiError, ApiUnexpectedError
from ..core.clock import Clock
from ..core.language import pick as _t
from ..core.errors import CredentialError, SyncCancelled
from ..core.secret import SecretStr
from ..security.credential_store import CredentialStore
from ..storage.state_repo import StateRepository
from ..storage.submissions_repo import SubmissionsRepository
from ..storage.surveys_repo import SurveysRepository
from ..sync import normalizer, sanitizer

log = logging.getLogger(__name__)
Progress = Callable[[str, int, int | None], None]     # (etapa, hechos, total)


@dataclass(frozen=True)
class SyncResult:
    form_id: str
    mode: str                         # initial | incremental | full | nochange
    new: int = 0
    updated: int = 0
    missing: int = 0
    remote_total: int | None = None
    local_total: int = 0
    warnings: tuple[str, ...] = field(default_factory=tuple)
    unknown_fields: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class FormsSyncResult:
    count: int
    unknown_fields: tuple[str, ...] = ()


class SyncService:
    def __init__(self, surveys: SurveysRepository, submissions: SubmissionsRepository, state: StateRepository,
                 store: CredentialStore, client: TallyClient, clock: Clock | None = None,
                 before_reconcile: Callable[[], object] | None = None) -> None:
        self._surveys, self._subs, self._state = surveys, submissions, state
        self._store, self._client = store, client
        self._clock = clock or Clock()
        self._before_reconcile = before_reconcile

    def _key(self, account_id: str) -> SecretStr:
        cred = self._store.load(account_id)
        if cred is None:
            raise CredentialError(_t("Esta cuenta no tiene API Key guardada. Reemplazala desde Cuentas.", "This account has no saved API Key. Replace it from Accounts."))
        return cred.api_key

    # ---------- lista de encuestas ----------
    def sync_forms(self, account_id: str, *, cancel: Callable[[], bool] | None = None,
                   progress: Progress | None = None) -> FormsSyncResult:
        key = self._key(account_id)
        items, unknown, page = [], [], 1
        while True:
            if cancel and cancel():
                raise SyncCancelled()
            data = self._client.list_forms(key, page=page)
            raw = data.get("items")
            if not isinstance(raw, list):
                raise ApiUnexpectedError()
            for f in raw:
                if isinstance(f, dict) and f.get("id"):
                    s = sanitizer.sanitize_form(f)
                    unknown += s.unknown_fields
                    items.append((normalizer.form_row(s.data), s.data))
            if progress:
                progress("encuestas", len(items), data.get("total") if isinstance(data.get("total"), int) else None)
            if not data.get("hasMore") or not raw or page >= 200:
                break
            page += 1
        self._surveys.save_summaries(account_id, items)
        return FormsSyncResult(len(items), tuple(dict.fromkeys(unknown)))

    # ---------- una encuesta ----------
    def sync_form(self, account_id: str, form_id: str, *, full: bool = False,
                  cancel: Callable[[], bool] | None = None, progress: Progress | None = None) -> SyncResult:
        try:
            return self._sync(account_id, form_id, full, cancel, progress)
        except SyncCancelled:
            raise
        except ApiError as exc:
            self._state.save_sync_error(account_id, form_id, exc.category)
            raise

    def _check(self, cancel) -> None:
        if cancel and cancel():
            raise SyncCancelled()

    def _sync(self, account_id, form_id, full, cancel, progress) -> SyncResult:
        key = self._key(account_id)
        warnings: list[str] = []
        unknown: list[str] = []

        # 1) estructura (preguntas y opciones)
        detail_s = sanitizer.sanitize_form(self._client.get_form(key, form_id))
        self._check(cancel)
        q_s = sanitizer.sanitize_questions(self._client.get_questions(key, form_id))
        unknown += detail_s.unknown_fields + q_s.unknown_fields
        previous = self._surveys.get_questions(account_id, form_id)
        qrows = normalizer.question_rows(detail_s.data, q_s.data)
        self._surveys.save_detail(account_id, normalizer.form_row(detail_s.data), detail_s.data, q_s.data, qrows)
        structure_changed = [(q.question_id, q.type, q.options, q.has_other_option) for q in previous] != \
                            [(q.question_id, q.type, q.options, q.has_other_option) for q in qrows]
        qmap = {q.question_id: q for q in qrows}
        self._check(cancel)

        # 2) sondeo barato: totales y envío más reciente
        probe = self._client.list_submissions(key, form_id, page=1, limit=1)
        totals = probe.get("totalNumberOfSubmissionsPerFilter")
        remote_total = totals.get("all") if isinstance(totals, dict) and isinstance(totals.get("all"), int) else None
        if remote_total is not None:
            self._surveys.set_reported(account_id, form_id, remote_total)
        local = self._subs.count_present(account_id, form_id)
        st = self._state.get_sync(account_id, form_id)
        marker = st.newest_submitted_at if st else None

        if full:
            mode = "full"
        elif marker is None:
            mode = "initial"
        elif remote_total is not None and remote_total < local:
            mode = "full"
        else:
            mode = "incremental"

        if mode == "incremental" and remote_total is not None and remote_total == local and not structure_changed:
            newest = self._probe_newest(probe)
            if newest is None or newest <= marker:
                self._subs.assign_numbers(account_id, form_id)
                self._state.save_sync_ok(account_id, form_id, newest_at=marker,
                                         newest_id=st.newest_submission_id if st else None, full=False)
                self._surveys.mark_synced(account_id, form_id,
                                          last_submission_at=self._subs.newest_submitted_at(account_id, form_id))
                return SyncResult(form_id, "nochange", remote_total=remote_total, local_total=local,
                                  unknown_fields=tuple(dict.fromkeys(unknown)))

        new = upd = 0
        seen: set[str] = set()
        missing = 0
        if mode == "full" and self._before_reconcile and local > 0:
            self._before_reconcile()
        new, upd, seen = self._download(key, account_id, form_id, qmap,
                                        None if mode in ("full", "initial") else marker,
                                        cancel, progress, unknown, remote_total)
        if mode == "full":
            missing = self._subs.mark_missing(account_id, form_id, seen)
        elif structure_changed:
            self._renormalize(account_id, form_id, qmap)

        # 3) verificación: si no coincide con el total de Tally, un recorrido completo (una sola vez)
        local_after = self._subs.count_present(account_id, form_id)
        if mode == "incremental" and remote_total is not None and local_after != remote_total:
            if self._before_reconcile:
                self._before_reconcile()
            n2, u2, seen = self._download(key, account_id, form_id, qmap, None, cancel, progress, unknown,
                                          remote_total)
            new, upd, missing, mode = new + n2, upd + u2, self._subs.mark_missing(account_id, form_id, seen), "full"
            local_after = self._subs.count_present(account_id, form_id)
        if remote_total is not None and local_after != remote_total:
            warnings.append("count_mismatch")

        self._subs.assign_numbers(account_id, form_id)
        newest = self._subs.newest_submitted_at(account_id, form_id)
        self._state.save_sync_ok(account_id, form_id, newest_at=newest, newest_id=None, full=(mode == "full"))
        self._surveys.mark_synced(account_id, form_id, last_submission_at=newest)
        return SyncResult(form_id, mode, new, upd, missing, remote_total, local_after, tuple(warnings),
                          tuple(dict.fromkeys(unknown)))

    @staticmethod
    def _probe_newest(probe: dict) -> str | None:
        subs = probe.get("submissions")
        if isinstance(subs, list) and subs and isinstance(subs[0], dict):
            v = subs[0].get("submittedAt") or subs[0].get("createdAt")
            return v if isinstance(v, str) else None
        return None

    def _download(self, key, account_id, form_id, qmap, start_date, cancel, progress, unknown, total):
        new = upd = 0
        seen: set[str] = set()
        page = 1
        while True:
            self._check(cancel)
            data = self._client.list_submissions(key, form_id, page=page, limit=MAX_PAGE_SIZE,
                                                 start_date=start_date)
            raw = data.get("submissions")
            if not isinstance(raw, list):
                raise ApiUnexpectedError()
            batch = []
            for sub in raw:
                if not isinstance(sub, dict) or not sub.get("id"):
                    continue
                s = sanitizer.sanitize_submission(sub)
                unknown += s.unknown_fields
                row = normalizer.submission_row(s.data, qmap)
                batch.append((row, s.data))
                seen.add(row.submission_id)
            n, u = self._subs.upsert_page(account_id, batch)
            new, upd = new + n, upd + u
            if progress:
                progress("respuestas", len(seen), total)
            if not data.get("hasMore") or not raw or page >= 1000:
                break
            page += 1
        return new, upd, seen

    def _renormalize(self, account_id, form_id, qmap) -> None:
        rows = [normalizer.submission_row(raw, qmap) for raw in self._subs.raw_submissions(account_id, form_id)]
        self._subs.rewrite_normalized(account_id, rows)
