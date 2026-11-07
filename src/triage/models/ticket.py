"""Incoming support ticket: a thread of messages from one customer."""

from typing import Literal, Self

from pydantic import AwareDatetime, BaseModel, Field, model_validator


class Message(BaseModel):
    author: Literal["customer", "agent"] = "customer"
    sent_at: AwareDatetime
    content: str = Field(min_length=1)


class Ticket(BaseModel):
    ticket_id: str
    customer_id: str
    messages: list[Message] = Field(min_length=1)

    @model_validator(mode="after")
    def _messages_in_chronological_order(self) -> Self:
        timestamps = [m.sent_at for m in self.messages]
        if timestamps != sorted(timestamps):
            raise ValueError("messages must be in chronological order")
        return self
