from pydantic import BaseModel


class ScheduleImportResult(BaseModel):
    created: int
    skipped: int
    removed: int = 0          # 重导时清除的上次课表占用数
    conflicts: list[str] = []
