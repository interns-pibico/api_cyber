from datetime import datetime, timezone
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.agent_command import AgentCommand


class AgentCommandRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, command_id: int) -> AgentCommand | None:
        result = await self.db.execute(select(AgentCommand).where(AgentCommand.id == command_id))
        return result.scalar_one_or_none()

    async def get_pending_for_agent(self, agent_id: int) -> list[AgentCommand]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(AgentCommand)
            .where(
                and_(
                    AgentCommand.agent_id == agent_id,
                    AgentCommand.status == "pending",
                    AgentCommand.expires_at > now,
                )
            )
            .order_by(AgentCommand.created_at.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def create(
        self,
        agent_id: int,
        execution_id: int | None,
        catalog_key: str,
        command: str,
        parameters: dict | None,
        timeout_seconds: int,
        expires_at: datetime,
    ) -> AgentCommand:
        cmd = AgentCommand(
            agent_id=agent_id,
            execution_id=execution_id,
            catalog_key=catalog_key,
            command=command,
            parameters=parameters,
            timeout_seconds=timeout_seconds,
            expires_at=expires_at,
        )
        self.db.add(cmd)
        await self.db.commit()
        await self.db.refresh(cmd)
        return cmd

    async def mark_delivered(self, commands: list[AgentCommand]) -> None:
        now = datetime.now(timezone.utc)
        for cmd in commands:
            cmd.status = "delivered"
            cmd.delivered_at = now
        await self.db.commit()

    async def update_status(self, command: AgentCommand, status: str) -> AgentCommand:
        command.status = status
        await self.db.commit()
        await self.db.refresh(command)
        return command

    async def expire_old_commands(self) -> int:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            update(AgentCommand)
            .where(
                and_(
                    AgentCommand.status == "pending",
                    AgentCommand.expires_at < now,
                )
            )
            .values(status="expired")
        )
        await self.db.commit()
        return result.rowcount
