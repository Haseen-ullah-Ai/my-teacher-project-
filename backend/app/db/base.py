"""Declarative SQLAlchemy base class."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base model class for all future ORM models."""


__all__ = ["Base"]
