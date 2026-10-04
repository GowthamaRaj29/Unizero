from pydantic import BaseModel, ConfigDict


class AuditResponse(BaseModel):

    id: str
    user_id: str | None
    action: str
    workflow_id: str | None
    old_value: str | None
    new_value: str | None
    reason: str | None

    model_config = ConfigDict(from_attributes=True)