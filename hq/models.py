"""Pydantic models for request/response validation."""
from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class IncidentCreate(BaseModel):
    message_id: str = Field(..., min_length=1, max_length=100)
    beacon_id: str = Field(..., min_length=1, max_length=100)
    status: str = Field(..., pattern=r"^(trapped|injured|evacuation|safe)$")
    people: int = Field(1, ge=1, le=999)
    injured: int = Field(0, ge=0, le=999)
    special_needs: str = Field("", max_length=200)
    victim_name: str = Field("", max_length=100)
    victim_phone: str = Field("", max_length=30)
    landmark: str = Field(..., min_length=1, max_length=300)
    notes: str = Field("", max_length=500)
    beacon_lat: Optional[float] = None
    beacon_lon: Optional[float] = None
    created_at: int = Field(...)
    hops: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def injured_le_people(self):
        if self.injured > self.people:
            raise ValueError("injured cannot exceed people count")
        return self


class AssignRequest(BaseModel):
    team: str = Field(..., min_length=1, max_length=100)
    eta: str = Field("", max_length=50)


class CallRequest(BaseModel):
    phone: Optional[str] = None   # override notify number for this call
