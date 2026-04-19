from pydantic import BaseModel, Field, field_validator


class ProjectCreate(BaseModel):
    title: str = Field(..., min_length=1)
    issuer: str = ""
    rfp_id: str = ""
    deadline: str = ""
    status: str = "draft"
    company_knowledge_data: str = Field(..., min_length=1)
    response_rfp: str = Field(..., min_length=1)

    @field_validator(
        "title",
        "issuer",
        "rfp_id",
        "deadline",
        "status",
        "company_knowledge_data",
        "response_rfp",
        mode="before",
    )
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        return value.strip() if isinstance(value, str) else value

    @field_validator("title", "company_knowledge_data", "response_rfp")
    @classmethod
    def reject_blank_required_fields(cls, value: str) -> str:
        if not value:
            raise ValueError("This field is required")
        return value
