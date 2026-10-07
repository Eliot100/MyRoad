"""Agent path builder: goal -> outline -> per-topic fill -> draft -> publish."""
from myroad_core.agent_builder.builder import (
    AGENT_ID_DEMO,
    AGENT_ID_GATEWAY,
    AgentPathBuilder,
    TopicResult,
    assemble_document,
    list_user_agent_drafts,
)
from myroad_core.agent_builder.completeness import CompletenessReport, check_path_completeness
from myroad_core.agent_builder.fake import FakePathGenerator
from myroad_core.agent_builder.generator import (
    GatewayPathGenerator,
    GenerationError,
    PathGenerator,
)
from myroad_core.agent_builder.models import (
    MIN_STAGES,
    MIN_TOPICS,
    FilledTopic,
    GoalSpec,
    OutlineStage,
    OutlineTopic,
    PathOutline,
)
from myroad_core.agent_builder.parsing import ReplyParseError, extract_json_object, parse_reply

__all__ = [
    "AGENT_ID_DEMO",
    "AGENT_ID_GATEWAY",
    "AgentPathBuilder",
    "CompletenessReport",
    "FakePathGenerator",
    "FilledTopic",
    "GatewayPathGenerator",
    "GenerationError",
    "GoalSpec",
    "MIN_STAGES",
    "MIN_TOPICS",
    "OutlineStage",
    "OutlineTopic",
    "PathGenerator",
    "PathOutline",
    "ReplyParseError",
    "TopicResult",
    "assemble_document",
    "check_path_completeness",
    "extract_json_object",
    "list_user_agent_drafts",
    "parse_reply",
]
