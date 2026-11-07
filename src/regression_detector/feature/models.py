"""Output contract of the email classifier (decision 1.1)."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class Category(StrEnum):
    """The seven support queues an email can be routed to."""

    DELIVERY = "delivery"
    CANCELLATION = "cancellation"
    RETURN_REFUND = "return_refund"
    PAYMENT = "payment"
    ACCOUNT = "account"
    TECHNICAL = "technical"
    GENERAL = "general"


class EmailClassification(BaseModel):
    """What the classifier returns for one email."""

    model_config = ConfigDict(extra="forbid")

    category: Category
    summary: str
