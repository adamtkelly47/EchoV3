"""No authentication/Identity domain exists yet — `user_id` is accepted
directly in the request body/query params, matching every other routes
module's documented convention for this phase.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from application.orchestrators.project_memory import ProjectMemoryOrchestrator
from apps.api.dependencies import (
    get_db_session,
    get_project_memory_orchestrator,
    get_project_service,
)
from apps.api.schemas.projects import (
    AddDocumentLinkRequest,
    BlockerResponse,
    CreateGoalRequest,
    CreateMilestoneRequest,
    CreateProjectRequest,
    DecisionResponse,
    GoalResponse,
    MilestoneResponse,
    ProjectResponse,
    ProjectStatusSummaryResponse,
    ProposeTaskRequest,
    RaiseBlockerRequest,
    RecordDecisionRequest,
    RecordStatusUpdateRequest,
    StatusUpdateResponse,
    TaskResponse,
    UpdateGoalStatusRequest,
    UpdateProjectStatusRequest,
)
from domains.projects.models import GoalStatus, ProjectStatus
from domains.projects.schemas import (
    Blocker,
    Decision,
    Goal,
    Milestone,
    Project,
    ProjectStatusSummary,
    StatusUpdate,
    Task,
)
from domains.projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["projects"])


def _to_project_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        project_id=project.project_id,
        user_id=project.user_id,
        name=project.name,
        description=project.description,
        status=project.status.value,
        document_links=project.document_links,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _to_goal_response(goal: Goal) -> GoalResponse:
    return GoalResponse(
        goal_id=goal.goal_id,
        project_id=goal.project_id,
        description=goal.description,
        status=goal.status.value,
        created_at=goal.created_at,
        updated_at=goal.updated_at,
    )


def _to_milestone_response(milestone: Milestone) -> MilestoneResponse:
    return MilestoneResponse(
        milestone_id=milestone.milestone_id,
        project_id=milestone.project_id,
        name=milestone.name,
        due_date=milestone.due_date,
        status=milestone.status.value,
        completed_at=milestone.completed_at,
        created_at=milestone.created_at,
    )


def _to_task_response(task: Task) -> TaskResponse:
    return TaskResponse(
        task_id=task.task_id,
        project_id=task.project_id,
        milestone_id=task.milestone_id,
        description=task.description,
        status=task.status.value,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _to_decision_response(decision: Decision, memory_id: str | None = None) -> DecisionResponse:
    return DecisionResponse(
        decision_id=decision.decision_id,
        project_id=decision.project_id,
        description=decision.description,
        rationale=decision.rationale,
        decided_at=decision.decided_at,
        source_context=decision.source_context,
        memory_id=memory_id,
    )


def _to_blocker_response(blocker: Blocker) -> BlockerResponse:
    return BlockerResponse(
        blocker_id=blocker.blocker_id,
        project_id=blocker.project_id,
        description=blocker.description,
        status=blocker.status.value,
        created_at=blocker.created_at,
        resolved_at=blocker.resolved_at,
    )


def _to_status_update_response(status_update: StatusUpdate) -> StatusUpdateResponse:
    return StatusUpdateResponse(
        status_update_id=status_update.status_update_id,
        project_id=status_update.project_id,
        summary=status_update.summary,
        created_at=status_update.created_at,
    )


def _to_summary_response(summary: ProjectStatusSummary) -> ProjectStatusSummaryResponse:
    return ProjectStatusSummaryResponse(
        project_id=summary.project_id,
        project_status=summary.project_status.value,
        total_tasks=summary.total_tasks,
        proposed_tasks=summary.proposed_tasks,
        committed_tasks=summary.committed_tasks,
        in_progress_tasks=summary.in_progress_tasks,
        done_tasks=summary.done_tasks,
        open_blockers=summary.open_blockers,
        next_milestone=(
            _to_milestone_response(summary.next_milestone)
            if summary.next_milestone is not None
            else None
        ),
        overdue_milestones=[_to_milestone_response(m) for m in summary.overdue_milestones],
        latest_status_update=(
            _to_status_update_response(summary.latest_status_update)
            if summary.latest_status_update is not None
            else None
        ),
        latest_decision=(
            _to_decision_response(summary.latest_decision)
            if summary.latest_decision is not None
            else None
        ),
        generated_at=summary.generated_at,
    )


@router.post("", response_model=ProjectResponse)
async def create_project(
    body: CreateProjectRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    project = await projects.create_project(body.user_id, body.name, body.description)
    await session.commit()
    return _to_project_response(project)


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    user_id: str, projects: ProjectService = Depends(get_project_service)
) -> list[ProjectResponse]:
    result = await projects.list_projects_for_user(user_id)
    return [_to_project_response(p) for p in result]


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> ProjectResponse:
    project = await projects.get_project(project_id)
    return _to_project_response(project)


@router.patch("/{project_id}/status", response_model=ProjectResponse)
async def update_project_status(
    project_id: str,
    body: UpdateProjectStatusRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    project = await projects.update_project_status(project_id, ProjectStatus(body.status))
    await session.commit()
    return _to_project_response(project)


@router.post("/{project_id}/document-links", response_model=ProjectResponse)
async def add_document_link(
    project_id: str,
    body: AddDocumentLinkRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> ProjectResponse:
    project = await projects.add_document_link(project_id, body.url)
    await session.commit()
    return _to_project_response(project)


@router.get("/{project_id}/status-summary", response_model=ProjectStatusSummaryResponse)
async def get_status_summary(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> ProjectStatusSummaryResponse:
    summary = await projects.get_project_status_summary(project_id)
    return _to_summary_response(summary)


@router.post("/{project_id}/goals", response_model=GoalResponse)
async def add_goal(
    project_id: str,
    body: CreateGoalRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> GoalResponse:
    goal = await projects.add_goal(project_id, body.description)
    await session.commit()
    return _to_goal_response(goal)


@router.get("/{project_id}/goals", response_model=list[GoalResponse])
async def list_goals(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> list[GoalResponse]:
    result = await projects.list_goals_for_project(project_id)
    return [_to_goal_response(g) for g in result]


@router.patch("/{project_id}/goals/{goal_id}/status", response_model=GoalResponse)
async def update_goal_status(
    project_id: str,
    goal_id: str,
    body: UpdateGoalStatusRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> GoalResponse:
    goal = await projects.update_goal_status(goal_id, GoalStatus(body.status), project_id)
    await session.commit()
    return _to_goal_response(goal)


@router.post("/{project_id}/milestones", response_model=MilestoneResponse)
async def add_milestone(
    project_id: str,
    body: CreateMilestoneRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> MilestoneResponse:
    milestone = await projects.add_milestone(project_id, body.name, body.due_date)
    await session.commit()
    return _to_milestone_response(milestone)


@router.get("/{project_id}/milestones", response_model=list[MilestoneResponse])
async def list_milestones(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> list[MilestoneResponse]:
    result = await projects.list_milestones_for_project(project_id)
    return [_to_milestone_response(m) for m in result]


@router.post("/milestones/{milestone_id}/complete", response_model=MilestoneResponse)
async def complete_milestone(
    milestone_id: str,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> MilestoneResponse:
    milestone = await projects.complete_milestone(milestone_id)
    await session.commit()
    return _to_milestone_response(milestone)


@router.post("/{project_id}/tasks", response_model=TaskResponse)
async def propose_task(
    project_id: str,
    body: ProposeTaskRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    task = await projects.propose_task(project_id, body.description, body.milestone_id)
    await session.commit()
    return _to_task_response(task)


@router.get("/{project_id}/tasks", response_model=list[TaskResponse])
async def list_tasks(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> list[TaskResponse]:
    result = await projects.list_tasks_for_project(project_id)
    return [_to_task_response(t) for t in result]


@router.post("/tasks/{task_id}/commit", response_model=TaskResponse)
async def commit_task(
    task_id: str,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    """PROMPT.md Phase 23 verification 3: the one explicit transition that
    turns a proposed suggestion into work the user is actually committed
    to."""
    task = await projects.commit_task(task_id)
    await session.commit()
    return _to_task_response(task)


@router.post("/tasks/{task_id}/start", response_model=TaskResponse)
async def start_task(
    task_id: str,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    task = await projects.start_task(task_id)
    await session.commit()
    return _to_task_response(task)


@router.post("/tasks/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    task = await projects.complete_task(task_id)
    await session.commit()
    return _to_task_response(task)


@router.post("/tasks/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task(
    task_id: str,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> TaskResponse:
    task = await projects.cancel_task(task_id)
    await session.commit()
    return _to_task_response(task)


@router.post("/{project_id}/decisions", response_model=DecisionResponse)
async def record_decision(
    project_id: str,
    body: RecordDecisionRequest,
    orchestrator: ProjectMemoryOrchestrator = Depends(get_project_memory_orchestrator),
    session: AsyncSession = Depends(get_db_session),
) -> DecisionResponse:
    """PROMPT.md Phase 23 implement item 9: "memory integration" — recording
    a decision also creates a linked, still-unconfirmed memory candidate
    (application/orchestrators/project_memory.py)."""
    decision, memory = await orchestrator.record_decision_with_memory(
        project_id, body.description, body.rationale, body.source_context
    )
    await session.commit()
    return _to_decision_response(decision, memory_id=memory.memory_id)


@router.get("/{project_id}/decisions", response_model=list[DecisionResponse])
async def list_decisions(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> list[DecisionResponse]:
    result = await projects.list_decisions_for_project(project_id)
    return [_to_decision_response(d) for d in result]


@router.post("/{project_id}/blockers", response_model=BlockerResponse)
async def raise_blocker(
    project_id: str,
    body: RaiseBlockerRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> BlockerResponse:
    blocker = await projects.raise_blocker(project_id, body.description)
    await session.commit()
    return _to_blocker_response(blocker)


@router.post("/blockers/{blocker_id}/resolve", response_model=BlockerResponse)
async def resolve_blocker(
    blocker_id: str,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> BlockerResponse:
    blocker = await projects.resolve_blocker(blocker_id)
    await session.commit()
    return _to_blocker_response(blocker)


@router.get("/{project_id}/blockers", response_model=list[BlockerResponse])
async def list_blockers(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> list[BlockerResponse]:
    result = await projects.list_blockers_for_project(project_id)
    return [_to_blocker_response(b) for b in result]


@router.post("/{project_id}/status-updates", response_model=StatusUpdateResponse)
async def record_status_update(
    project_id: str,
    body: RecordStatusUpdateRequest,
    projects: ProjectService = Depends(get_project_service),
    session: AsyncSession = Depends(get_db_session),
) -> StatusUpdateResponse:
    status_update = await projects.record_status_update(project_id, body.summary)
    await session.commit()
    return _to_status_update_response(status_update)


@router.get("/{project_id}/status-updates", response_model=list[StatusUpdateResponse])
async def list_status_updates(
    project_id: str, projects: ProjectService = Depends(get_project_service)
) -> list[StatusUpdateResponse]:
    result = await projects.list_status_updates_for_project(project_id)
    return [_to_status_update_response(s) for s in result]
