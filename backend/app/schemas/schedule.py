from pydantic import BaseModel


class ScheduleImportResult(BaseModel):
    created: int
    skipped: int
    conflicts: list[str] = []
