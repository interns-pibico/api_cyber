import hashlib
import secrets

from fastapi import APIRouter

from src.core.dependencies import DbSession, CurrentActiveUser, CurrentAdminUser, AgentAuth
from src.core.exceptions import NotFoundException
from src.services.agent import AgentService
from src.schemas.agent import AgentResponse, AgentCreate, AgentUpdate, AgentHeartbeat
from src.db.repositories.agent import AgentRepository
from src.db.repositories.agent_command import AgentCommandRepository

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/", response_model=list[AgentResponse])
async def get_agents(
    db: DbSession,
    current_user: CurrentActiveUser,
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    agent_type: str | None = None,
):
    agent_service = AgentService(db)
    return await agent_service.get_all(skip=skip, limit=limit, active_only=active_only, agent_type=agent_type)


@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(
    agent_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    agent_service = AgentService(db)
    return await agent_service.get_by_id(agent_id)


@router.post("/", response_model=AgentResponse)
async def create_agent(
    agent_in: AgentCreate,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    agent_service = AgentService(db)
    return await agent_service.create(agent_in)


@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(
    agent_id: int,
    agent_in: AgentUpdate,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    agent_service = AgentService(db)
    return await agent_service.update(agent_id, agent_in)


@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: int,
    db: DbSession,
    current_user: CurrentActiveUser,
):
    agent_service = AgentService(db)
    await agent_service.delete(agent_id)
    return {"message": "Agent deleted"}


@router.post("/{agent_id}/api-key")
async def generate_agent_api_key(
    agent_id: int,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    """Generate a new per-agent API key. Returns the plaintext key once — store it securely."""
    agent_repo = AgentRepository(db)
    agent = await agent_repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(detail="Agent not found")

    # Format: pak{db_id}_{32 random hex chars}
    raw_key = f"pak{agent.id}_{secrets.token_hex(16)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

    agent.api_key_hash = key_hash
    await db.commit()

    return {
        "agent_id": agent.agent_id,
        "api_key": raw_key,
        "note": "Store this key securely — it will not be shown again.",
    }


@router.delete("/{agent_id}/api-key")
async def revoke_agent_api_key(
    agent_id: int,
    db: DbSession,
    current_user: CurrentAdminUser,
):
    """Remove the per-agent API key, reverting to global AGENT_API_KEY."""
    agent_repo = AgentRepository(db)
    agent = await agent_repo.get_by_id(agent_id)
    if not agent:
        raise NotFoundException(detail="Agent not found")

    agent.api_key_hash = None
    await db.commit()
    return {"message": "Per-agent API key revoked"}


@router.post("/heartbeat")
async def agent_heartbeat(
    heartbeat: AgentHeartbeat,
    db: DbSession,
    _: AgentAuth,
):
    agent_service = AgentService(db)
    agent, created = await agent_service.heartbeat(heartbeat)

    # Check for pending commands
    cmd_repo = AgentCommandRepository(db)
    pending_commands = await cmd_repo.get_pending_for_agent(agent.id)

    commands_data = None
    if pending_commands:
        commands_data = [
            {
                "id": cmd.id,
                "command": cmd.command,
                "catalog_key": cmd.catalog_key,
                "parameters": cmd.parameters,
                "timeout_seconds": cmd.timeout_seconds,
            }
            for cmd in pending_commands
        ]
        await cmd_repo.mark_delivered(pending_commands)

    # Build response with agent data + pending commands
    response = {
        "id": agent.id,
        "hostname": agent.hostname,
        "agent_id": agent.agent_id,
        "agent_type": agent.agent_type,
        "os_type": agent.os_type,
        "os_version": agent.os_version,
        "ip_address": agent.ip_address,
        "agent_version": agent.agent_version,
        "description": agent.description,
        "is_active": agent.is_active,
        "last_seen": agent.last_seen.isoformat() if agent.last_seen else None,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
        "pending_commands": commands_data,
    }
    return response
