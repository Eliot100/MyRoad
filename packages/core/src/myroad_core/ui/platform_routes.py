"""Platform catalog + path player (age-agnostic shell; content drives tone)."""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import quote

from fastapi import Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from myroad_core.content.loader import group_catalog, list_catalog_cards
from myroad_core.content.locale_rules import resolve_node_display
from myroad_core.content.schema import GROUPS, SUBJECTS
from myroad_core.ui.i18n import (
    COOKIE_LOCALE,
    COOKIE_USER,
    LOCALES,
    dir_for,
    html_lang,
    localize_path_chrome,
    locale_meta,
    normalize_locale,
    pick,
    subject_label,
    t,
)
from myroad_core.ui.cloudflare_gateway import (
    GatewayNotConfigured,
    GatewayRequestError,
    call_grok_chat,
    gateway_is_configured,
)

COOKIE_AUTHOR_SID = "myroad_author_sid"

ACTOR_LEARNER = "user_learner_poc"
