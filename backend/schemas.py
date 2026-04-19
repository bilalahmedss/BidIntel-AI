from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1)
    issuer: str = ""
    rfp_id: str = ""
    deadline: str = ""
    status: str = "draft"

    @field_validator("title", "issuer", "rfp_id", "deadline", "status", mode="before")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("title")
    @classmethod
    def reject_blank_required_fields(cls, value: str) -> str:
        if not value:
            raise ValueError("This field is required")
        return value
