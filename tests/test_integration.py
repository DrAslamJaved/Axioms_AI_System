from axioms.agent_registry import profile_for, specialist_profiles
from axioms.integration import IntegrationState, build_system_readiness_report
from axioms.models import AgentName


def test_registry_contains_every_specialist_and_blocks_external_actions() -> None:
    profiles = specialist_profiles()
    assert len(profiles) == 8
    assert {profile.agent for profile in profiles} == {
        AgentName.RESEARCH,
        AgentName.PORTFOLIO,
        AgentName.LECTURE,
        AgentName.ASSESSMENT,
        AgentName.CONTENT,
        AgentName.SOCIAL_MEDIA,
        AgentName.WRITING,
        AgentName.AUTOEVAL,
    }
    assert all(profile.external_actions_blocked for profile in profiles)
    assert profile_for(AgentName.CONTENT).endpoint == "/content-packages"


def test_readiness_report_exposes_deferred_infrastructure_truthfully() -> None:
    report = build_system_readiness_report()
    assert report.specialist_agent_count == 8
    assert not report.external_actions_enabled
    assert any(item.state is IntegrationState.DEFERRED for item in report.components)
    assert any(item.name == "Redis Streams dispatch" for item in report.components)
