from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class PreviewMode(str, Enum):
    LEGACY = "legacy"
    FULL = "full"


class RuntimeSourceKind(str, Enum):
    INSTALLED_CLIENT = "installed_client"
    ARCHIVE = "archive"


class RendererState(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    FAILED = "failed"


class RuntimeImportPhase(str, Enum):
    COMPARING = "comparing"
    COPYING = "copying"
    VERIFYING = "verifying"
    STARTING = "starting"
    ACTIVATING = "activating"
    CLEANING = "cleaning"
    DONE = "done"


class RuntimeImportDisposition(str, Enum):
    IMPORTED = "imported"
    REUSED = "reused"


@dataclass(frozen=True)
class PreviewDocument:
    """A single XML document declared by a CPC case manifest."""

    id: str
    code: str
    display_name: str
    relative_path: str


@dataclass(frozen=True)
class PreviewManifestResult:
    """The document list discovered from a case package before rendering."""

    documents: tuple[PreviewDocument, ...] = ()
    errors_by_document_id: dict[str, str] = field(default_factory=dict)
    passthrough_document_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class PreviewRenderResult:
    """Ordered render outcome. Maps use PreviewDocument.id instead of type code."""

    documents: tuple[PreviewDocument, ...] = ()
    pdf_by_document_id: dict[str, bytes] = field(default_factory=dict)
    errors_by_document_id: dict[str, str] = field(default_factory=dict)
    passthrough_document_ids: frozenset[str] = frozenset()
    cancelled: bool = False


@dataclass(frozen=True)
class RuntimeSourceInspection:
    source_kind: RuntimeSourceKind
    source_path: str
    missing_items: tuple[str, ...] = ()
    total_bytes: int = 0
    compatible: bool = False
    diagnostics: tuple[str, ...] = ()
    version: str = ""


@dataclass(frozen=True)
class ManagedRuntimeInfo:
    runtime_id: str
    private_root: str
    source_kind: RuntimeSourceKind
    source_path: str
    imported_at: str
    status: str
    content_fingerprint: str = ""
    diagnostics: tuple[str, ...] = ()
    cleanup_warning_path: str = ""
    machine_shared: bool = True


@dataclass(frozen=True)
class RendererStateInfo:
    state: RendererState
    runtime_id: str = ""
    base_url: str = ""
    detail: str = ""


@dataclass(frozen=True)
class RuntimeImportProgress:
    phase: RuntimeImportPhase
    completed_bytes: int = 0
    total_bytes: int = 0
    detail: str = ""
    elapsed_seconds: float = 0.0
    cancellable: bool = True


@dataclass(frozen=True)
class RuntimeCleanupReport:
    removed_paths: tuple[str, ...] = ()
    residual_paths: tuple[str, ...] = ()
    diagnostics: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuntimeImportResult:
    runtime: ManagedRuntimeInfo
    disposition: RuntimeImportDisposition
    cleanup: RuntimeCleanupReport = field(default_factory=RuntimeCleanupReport)
    renderer_ready: bool = False

    def __getattr__(self, name: str):
        """Keep existing runtime-info callers source-compatible during the result migration."""

        return getattr(self.runtime, name)


@dataclass(frozen=True)
class LegacyPreviewResult:
    preview_url: str
    render_result: PreviewRenderResult


__all__ = [
    "ManagedRuntimeInfo",
    "RendererState",
    "RendererStateInfo",
    "LegacyPreviewResult",
    "PreviewDocument",
    "PreviewManifestResult",
    "PreviewMode",
    "PreviewRenderResult",
    "RuntimeSourceInspection",
    "RuntimeSourceKind",
    "RuntimeImportDisposition",
    "RuntimeImportPhase",
    "RuntimeImportProgress",
    "RuntimeImportResult",
    "RuntimeCleanupReport",
]
