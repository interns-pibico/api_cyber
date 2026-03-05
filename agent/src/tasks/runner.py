import asyncio
import subprocess
from datetime import datetime, timezone
from typing import Any


class TaskRunner:
    """Execute scheduled tasks and report results."""

    async def run_command(
        self,
        command: str,
        task_name: str,
        task_type: str = "scheduled",
        timeout: int = 300,
    ) -> dict[str, Any]:
        """Run a shell command and return the result."""
        started_at = datetime.now(timezone.utc)
        result = {
            "task_name": task_name,
            "task_type": task_type,
            "started_at": started_at.isoformat(),
        }

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                finished_at = datetime.now(timezone.utc)

                result.update({
                    "status": "success" if proc.returncode == 0 else "failed",
                    "exit_code": proc.returncode,
                    "output": stdout.decode("utf-8", errors="replace")[:10000],
                    "error": stderr.decode("utf-8", errors="replace")[:5000] if stderr else None,
                    "finished_at": finished_at.isoformat(),
                    "duration_seconds": (finished_at - started_at).total_seconds(),
                })
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                finished_at = datetime.now(timezone.utc)
                result.update({
                    "status": "timeout",
                    "exit_code": -1,
                    "error": f"Task timed out after {timeout} seconds",
                    "finished_at": finished_at.isoformat(),
                    "duration_seconds": (finished_at - started_at).total_seconds(),
                })

        except Exception as e:
            finished_at = datetime.now(timezone.utc)
            result.update({
                "status": "failed",
                "exit_code": -1,
                "error": str(e),
                "finished_at": finished_at.isoformat(),
                "duration_seconds": (finished_at - started_at).total_seconds(),
            })

        return result
