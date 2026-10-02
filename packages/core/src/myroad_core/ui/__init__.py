"""Thin MyRoad learner UI (FastAPI + Jinja). Never auto-publishes."""

from myroad_core.ui.app import create_learner_app

__all__ = ["create_learner_app"]
