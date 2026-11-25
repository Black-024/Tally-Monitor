"""Exportaciones a archivo (Excel, y luego PDF/PNG) a partir de lo guardado. Nunca llama a la API."""
from __future__ import annotations

import os
import tempfile
from datetime import datetime
from pathlib import Path

from ..core.errors import ExportError, SurveyNotFoundError
from ..core.clock import Clock
from ..core.language import pick as _t
from ..export.models import ExportOptions, ExportResult
from ..export import pdf_writer, xlsx_writer
from ..export.individual import AnswerItem, ResponseCard, build_cards  # noqa: F401
from ..storage.analytics_repo import AnalyticsRepository
from ..storage.surveys_repo import SurveysRepository
from ..sync.numbering import format_user_label
from .analysis_service import AnalysisService

__all__ = ["ExportService", "ExportOptions", "ExportResult", "ResponseCard", "AnswerItem", "safe_filename"]

EXTENSIONS = {"xlsx": ".xlsx", "pdf": ".pdf", "png": ".png"}


def safe_filename(name: str, fallback: str = "") -> str:
    """Nombre de archivo válido en Windows a partir del nombre de la encuesta."""
    cleaned = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in (name or "")).strip(" .")
    return (cleaned[:80] or fallback or _t("encuesta", "survey"))



class ExportService:
    def __init__(self, analysis: AnalysisService, repo: AnalyticsRepository, surveys: SurveysRepository,
                 clock: Clock | None = None) -> None:
        self._analysis, self._repo, self._surveys = analysis, repo, surveys
        self._clock = clock or Clock()

    def suggested_name(self, account_id: str, form_id: str, fmt: str, scope: str = "summary") -> str:
        form = self._surveys.get_form(account_id, form_id)
        base = safe_filename(form.name if form else "")
        tag = _t(" - respuestas", " - responses") if scope == "individual" else ""
        return f"{base}{tag} - {self._clock.now().strftime('%Y-%m-%d')}{EXTENSIONS[fmt]}"

    @staticmethod
    def _check_target(path: str, fmt: str, overwrite: bool) -> Path:
        p = Path(path)
        if p.suffix.lower() != EXTENSIONS[fmt]:
            raise ExportError(_t(f"El archivo debe terminar en {EXTENSIONS[fmt]}.", f"The file name must end in {EXTENSIONS[fmt]}."))
        if not p.parent.is_dir():
            raise ExportError(_t("La carpeta elegida no existe.", "The selected folder does not exist."))
        if p.exists() and not overwrite:
            raise ExportError(_t("Ya existe un archivo con ese nombre. Elegí otro nombre o confirmá que se reemplace.", "A file with that name already exists. Choose another name or confirm replacing it."))
        return p

    def _atomic(self, target: Path, write) -> None:
        """Escribe a un temporal en la misma carpeta y lo renombra: nunca deja un archivo a medias."""
        try:
            fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".tally-", suffix=target.suffix)
            os.close(fd)
        except OSError as exc:
            raise ExportError(_t("No se pudo escribir en esa carpeta (¿sin permiso o protegida?).", "Could not write to that folder (no permission or protected?).")) from exc
        try:
            write(tmp)
            os.replace(tmp, target)
        except ExportError:
            raise
        except PermissionError as exc:
            raise ExportError(_t("No se pudo guardar: el archivo está abierto en otro programa o no hay permiso.", "Could not save: the file is open in another program or you lack permission.")) from exc
        except OSError as exc:
            raise ExportError(_t("No se pudo guardar el archivo (disco lleno o ruta no válida).", "Could not save the file (disk full or invalid path).")) from exc
        finally:
            try:
                os.remove(tmp)
            except OSError:
                pass

    def _prepare(self, account_id: str, form_id: str, path: str, fmt: str, options: ExportOptions, overwrite: bool):
        form = self._surveys.get_form(account_id, form_id)
        if form is None:
            raise SurveyNotFoundError()
        target = self._check_target(path, fmt, overwrite)
        analysis = self._analysis.analyze(account_id, form_id, options.kind,
                                          include_incomplete=options.include_incomplete,
                                          start_date=options.start_date, end_date=options.end_date)
        rows = self._repo.export_rows(account_id, form_id, start_iso=analysis.filter.start_iso,
                                      end_iso=analysis.filter.end_iso, include_incomplete=options.include_incomplete,
                                      include_text=options.include_text)
        if options.scope == "individual" and options.only_number is not None:
            rows = [r for r in rows if r.key == options.only_number]
            if not rows:
                raise ExportError(_t("No se encontró esa persona entre las respuestas del período elegido.", "That person was not found among the responses in the selected period."))
        tz = self._analysis._zone()
        now_local = self._clock.now().astimezone(tz).replace(tzinfo=None)
        return form, target, analysis, rows, tz, now_local

    def _result(self, target, fmt, rows, analysis, options) -> ExportResult:
        return ExportResult(str(target), fmt, len(rows), len(analysis.questions),
                            options.include_text, options.include_text and options.mask_personal)

    def export_xlsx(self, account_id: str, form_id: str, path: str, options: ExportOptions | None = None, *,
                    overwrite: bool = False) -> ExportResult:
        options = options or ExportOptions()
        form, target, analysis, rows, tz, now_local = self._prepare(account_id, form_id, path, "xlsx", options, overwrite)
        self._atomic(target, lambda tmp: xlsx_writer.write_xlsx(
            tmp, survey_name=form.name, analysis=analysis, rows=rows, label_for=format_user_label, tz=tz,
            options=options, generated_at_local=now_local))
        return self._result(target, "xlsx", rows, analysis, options)

    def export_pdf(self, account_id: str, form_id: str, path: str, options: ExportOptions | None = None, *,
                   overwrite: bool = False) -> ExportResult:
        options = options or ExportOptions()
        form, target, analysis, rows, tz, now_local = self._prepare(account_id, form_id, path, "pdf", options, overwrite)
        self._atomic(target, lambda tmp: pdf_writer.write_pdf(
            tmp, survey_name=form.name, analysis=analysis, rows=rows, tz=tz, options=options,
            generated_at_local=now_local, label_for=format_user_label))
        return self._result(target, "pdf", rows, analysis, options)

    def individual_cards(self, account_id: str, form_id: str, options: ExportOptions):
        """Fichas listas para dibujar (la interfaz las convierte en PNG). No escribe archivos."""
        options = options if options.scope == "individual" else ExportOptions(
            **{**options.__dict__, "scope": "individual"})
        form = self._surveys.get_form(account_id, form_id)
        if form is None:
            raise SurveyNotFoundError()
        analysis = self._analysis.analyze(account_id, form_id, options.kind, include_incomplete=options.include_incomplete,
                                          start_date=options.start_date, end_date=options.end_date)
        rows = self._repo.export_rows(account_id, form_id, start_iso=analysis.filter.start_iso,
                                      end_iso=analysis.filter.end_iso, include_incomplete=options.include_incomplete,
                                      include_text=options.include_text)
        if options.only_number is not None:
            rows = [r for r in rows if r.key == options.only_number]
            if not rows:
                raise ExportError(_t("No se encontró esa persona entre las respuestas del período elegido.", "That person was not found among the responses in the selected period."))
        cards = build_cards(analysis, rows, self._analysis._zone(), format_user_label,
                            include_text=options.include_text, mask=options.mask_personal)
        return form.name, analysis.filter.label, cards

    def save_png(self, path: str, data: bytes, *, overwrite: bool = False) -> ExportResult:
        """Guarda una imagen PNG ya dibujada por la interfaz (misma validación y escritura atómica)."""
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ExportError(_t("La imagen generada no es válida.", "The generated image is not valid."))
        target = self._check_target(path, "png", overwrite)

        def write(tmp: str) -> None:
            with open(tmp, "wb") as fh:
                fh.write(data)

        self._atomic(target, write)
        return ExportResult(str(target), "png", 0, 0, False, False)
