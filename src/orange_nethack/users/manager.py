import asyncio
import logging
import shutil
from pathlib import Path

from orange_nethack.config import get_settings

logger = logging.getLogger(__name__)


class UserManagerError(Exception):
    """Exception raised for user management errors."""

    pass


class UserManager:
    def __init__(self):
        self.settings = get_settings()
        self.shell_path = Path("/usr/local/bin/orange-shell.sh")

    async def _run_command(self, *args: str) -> tuple[int, str, str]:
        """Run a command and return (returncode, stdout, stderr)."""
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(), stderr.decode()

    async def user_exists(self, username: str) -> bool:
        """Check if a Linux user exists."""
        returncode, _, _ = await self._run_command("id", username)
        return returncode == 0

    async def create_user(self, username: str, password: str) -> None:
        """Create a Linux user with the given username and password.

        The user will:
        - Be in the games group (for nethack access)
        - Have the custom orange-shell as login shell
        - Have a home directory
        """
        # Validate username (should already be safe from our generator, but double-check)
        if not username.startswith(self.settings.nethack_user_prefix):
            raise UserManagerError(f"Invalid username prefix: {username}")

        if await self.user_exists(username):
            logger.warning(f"User {username} already exists")
            return

        # Create user with games group and custom shell
        returncode, stdout, stderr = await self._run_command(
            "useradd",
            "-m",  # Create home directory
            "-g",
            self.settings.nethack_group,  # Primary group
            "-s",
            str(self.shell_path),  # Login shell
            "-c",
            "Orange Nethack Player",  # Comment
            username,
        )

        if returncode != 0:
            raise UserManagerError(f"Failed to create user {username}: {stderr}")

        # Set password
        returncode, stdout, stderr = await self._run_command(
            "chpasswd",
        )
        # chpasswd reads from stdin, so we need a different approach
        process = await asyncio.create_subprocess_exec(
            "chpasswd",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        password_input = f"{username}:{password}\n".encode()
        stdout, stderr = await process.communicate(input=password_input)

        if process.returncode != 0:
            # Try to clean up the user we just created
            await self.delete_user(username)
            raise UserManagerError(f"Failed to set password for {username}: {stderr.decode()}")

        logger.info(f"Created user {username}")

    async def delete_user(self, username: str) -> None:
        """Delete a Linux user and their home directory."""
        # Validate username prefix for safety
        if not username.startswith(self.settings.nethack_user_prefix):
            raise UserManagerError(f"Invalid username prefix: {username}")

        if not await self.user_exists(username):
            logger.warning(f"User {username} does not exist")
            return

        # Kill any processes owned by the user
        await self._run_command("pkill", "-u", username)

        # Wait a moment for processes to die
        await asyncio.sleep(0.5)

        # Delete user and home directory
        returncode, stdout, stderr = await self._run_command(
            "userdel",
            "-r",  # Remove home directory
            username,
        )

        if returncode != 0:
            # userdel might fail if home dir is already gone, etc.
            # Try without -r as fallback
            returncode2, _, stderr2 = await self._run_command("userdel", username)
            if returncode2 != 0:
                raise UserManagerError(f"Failed to delete user {username}: {stderr} / {stderr2}")

        logger.info(f"Deleted user {username}")

    async def cleanup_expired_users(self, usernames: list[str]) -> int:
        """Delete multiple users. Returns count of successfully deleted users."""
        deleted = 0
        for username in usernames:
            try:
                await self.delete_user(username)
                deleted += 1
            except UserManagerError as e:
                logger.error(f"Failed to cleanup user {username}: {e}")
        return deleted

    async def set_shell(self, username: str, shell_path: str) -> None:
        """Change user's login shell."""
        if not await self.user_exists(username):
            raise UserManagerError(f"User {username} does not exist")

        returncode, stdout, stderr = await self._run_command(
            "chsh", "-s", shell_path, username
        )

        if returncode != 0:
            raise UserManagerError(f"Failed to change shell for {username}: {stderr}")

    async def get_user_processes(self, username: str) -> list[int]:
        """Get list of PIDs for processes owned by user."""
        returncode, stdout, stderr = await self._run_command(
            "pgrep", "-u", username
        )

        if returncode != 0:
            return []

        pids = []
        for line in stdout.strip().split("\n"):
            if line:
                try:
                    pids.append(int(line))
                except ValueError:
                    pass
        return pids

    async def is_user_playing(self, username: str) -> bool:
        """Check if user has nethack process running."""
        pids = await self.get_user_processes(username)
        if not pids:
            return False

        # Check if any process is nethack
        for pid in pids:
            try:
                returncode, stdout, _ = await self._run_command(
                    "ps", "-p", str(pid), "-o", "comm="
                )
                if returncode == 0 and "nethack" in stdout.lower():
                    return True
            except Exception:
                pass

        return False
