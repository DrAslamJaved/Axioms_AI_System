"""Single source of truth for implemented Axioms specialist capabilities."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from axioms.models import AgentName


@dataclass(frozen=True, slots=True)
class AgentProfile:
    agent: AgentName
    label: str
    purpose: str
    endpoint: str
    external_actions_blocked: bool = True
    human_approval_required: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


SPECIALIST_PROFILES: tuple[AgentProfile, ...] = (
    AgentProfile(AgentName.RESEARCH, "Research Agent", "Evidence-first research briefs.", "/research-briefs"),
    AgentProfile(AgentName.PORTFOLIO, "STEM AI Portfolio Agent", "Evidence-bound portfolio blueprints.", "/portfolio-packages"),
    AgentProfile(AgentName.LECTURE, "Lecture Design Agent", "Duration-accurate lecture plans.", "/lecture-plans"),
    AgentProfile(AgentName.ASSESSMENT, "Assessment Design Agent", "Source-bounded assessment blueprints.", "/assessment-blueprints"),
    AgentProfile(AgentName.CONTENT, "Content Creation Agent", "Reviewable educational content packages.", "/content-packages"),
    AgentProfile(AgentName.SOCIAL_MEDIA, "Social Media Agent", "Platform-native draft packages.", "/social-media-packages"),
    AgentProfile(AgentName.WRITING, "Writing and Communication Agent", "Evidence-aware writing drafts.", "/writing-drafts"),
    AgentProfile(AgentName.AUTOEVAL, "AutoEval Agent", "Deterministic deliverable review reports.", "/autoeval-reports"),
)


def specialist_profiles() -> tuple[AgentProfile, ...]:
    return SPECIALIST_PROFILES


def profile_for(agent: AgentName) -> AgentProfile:
    for profile in SPECIALIST_PROFILES:
        if profile.agent is agent:
            return profile
    raise KeyError(f"No specialist profile is registered for {agent.value}.")
