"""Estado de trabalho da E1; candidatos só são aplicados após validação."""

from e_z.domain.document import EvidenceProject


class DocumentSession:
    def __init__(self) -> None:
        self.project: EvidenceProject | None = None
        self.dirty = False

    def replace(self, project: EvidenceProject) -> None:
        self.project = project
        self.dirty = True

    def mark_exported(self, project: EvidenceProject) -> None:
        if self.project is project:
            self.dirty = False
