from enum import Enum


class Role(str, Enum):

    ADMIN = "ADMIN"
    INVESTIGATOR = "INVESTIGATOR"
    APPROVER = "APPROVER"


class WorkflowStatus(str, Enum):

    DRAFT = "DRAFT"
    READY = "READY"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BreakStatus(str, Enum):

    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class ApprovalStatus(str, Enum):

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"