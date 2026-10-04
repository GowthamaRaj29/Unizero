from pydantic import BaseModel, ConfigDict


class WorkflowCreate(BaseModel):

    name: str
    period: str
    number_of_sources: int = 2


class WorkflowUpdate(BaseModel):

    name: str | None = None
    period: str | None = None
    status: str | None = None


class WorkflowResponse(BaseModel):

    id: str
    name: str
    period: str
    status: str
    created_by: str

    model_config = ConfigDict(from_attributes=True)