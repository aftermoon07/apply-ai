"""Outreach and Contact ORM models."""

from __future__ import annotations

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from applyai.models.base import Base, utcnow


class Contact(Base):
    """A professional contact — potential referral or outreach target."""

    __tablename__ = "contacts"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    company: Mapped[str | None] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(255))
    linkedin_url: Mapped[str | None] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(String(255))
    is_referral: Mapped[int] = mapped_column(Integer, default=0)  # 0/1 boolean
    source: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    outreach_records: Mapped[list["Outreach"]] = relationship(
        "Outreach", back_populates="contact", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Contact name={self.name!r} company={self.company!r}>"


class Outreach(Base):
    """
    An outreach message prepared or sent to a contact.

    V1: records are created in "draft" status only.
    V3: "sent" status requires explicit human approval.
    """

    __tablename__ = "outreach"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("jobs.id", ondelete="SET NULL")
    )
    contact_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("contacts.id", ondelete="SET NULL")
    )
    channel: Mapped[str | None] = mapped_column(
        String(30)
    )  # "email" | "linkedin" | "telegram"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    # "draft" | "prepared" | "sent" | "replied" | "no_reply"
    # NOTE: "sent" requires explicit human approval (V3+)
    subject: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    sent_at: Mapped[str | None] = mapped_column(String(30))
    replied_at: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(
        String(30), default=lambda: utcnow().isoformat()
    )

    contact: Mapped["Contact | None"] = relationship("Contact", back_populates="outreach_records")

    def __repr__(self) -> str:
        return f"<Outreach channel={self.channel!r} status={self.status!r}>"
