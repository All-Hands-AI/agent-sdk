"""Trigger types for skills.

This module defines different trigger types that determine when a skill
should be activated.
"""

from abc import ABC
from typing import Literal

from pydantic import BaseModel


class BaseTrigger(BaseModel, ABC):
    """Base class for all trigger types."""

    pass


class RepoTrigger(BaseTrigger):
    """Trigger for repository-level skills.

    These skills are always active and provide repository-specific context.
    Loaded from `.openhands/skills/repo.md` or `.cursorrules` files.
    """

    type: Literal["repo"] = "repo"


class KeywordTrigger(BaseTrigger):
    """Trigger for keyword-based skills.

    These skills are activated when specific keywords appear in the user's query.
    """

    type: Literal["keyword"] = "keyword"
    keywords: list[str]


class TaskTrigger(BaseTrigger):
    """Trigger for task-specific skills.

    These skills are activated for specific task types and can modify prompts.
    """

    type: Literal["task"] = "task"
    triggers: list[str]
