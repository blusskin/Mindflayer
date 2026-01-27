"""WebSocket SSH bridge for browser-based terminal access."""
import asyncio
import json
import logging
import secrets
from typing import Optional

import asyncssh
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from orange_nethack.database import get_db

logger = logging.getLogger(__name__)

terminal_router = APIRouter()

# Idle timeout in seconds (5 minutes)
IDLE_TIMEOUT = 300


class SSHBridge:
    """Bridges WebSocket to SSH connection."""

    def __init__(
        self,
        websocket: WebSocket,
        username: str,
        password: str,
        host: str = "localhost",
        port: int = 22,
    ):
        self.websocket = websocket
        self.username = username
        self.password = password
        self.host = host
        self.port = port
        self.conn: Optional[asyncssh.SSHClientConnection] = None
        self.process: Optional[asyncssh.SSHClientProcess] = None
        self.running = False
        self.last_activity = asyncio.get_event_loop().time()

    async def connect(self) -> bool:
        """Establish SSH connection."""
        try:
            self.conn = await asyncssh.connect(
                self.host,
                self.port,
                username=self.username,
                password=self.password,
                known_hosts=None,  # Accept any host key for localhost
            )

            # Request PTY and start shell
            self.process = await self.conn.create_process(
                term_type="xterm-256color",
                term_size=(80, 24),
            )

            self.running = True
            logger.info(f"SSH connection established for {self.username}")
            return True

        except asyncssh.PermissionDenied:
            logger.warning(f"SSH permission denied for {self.username}")
            return False
        except asyncssh.HostKeyNotVerifiable:
            logger.error("SSH host key verification failed")
            return False
        except Exception as e:
            logger.error(f"SSH connection failed for {self.username}: {e}")
            return False

    async def disconnect(self):
        """Close SSH connection."""
        self.running = False
        if self.process:
            try:
                # Send SIGHUP to trigger Nethack's emergency save
                # Nethack handles SIGHUP by saving the game before exiting
                try:
                    self.process.send_signal('HUP')
                    logger.info(f"Sent SIGHUP to process for {self.username}")
                except Exception as e:
                    logger.warning(f"Failed to send SIGHUP: {e}")

                # Wait for process to save and exit gracefully (up to 5 seconds)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=5.0)
                    logger.info(f"Process exited gracefully for {self.username}")
                except asyncio.TimeoutError:
                    # Try SIGTERM if SIGHUP didn't work
                    logger.info(f"Process didn't exit after SIGHUP, sending SIGTERM for {self.username}")
                    self.process.terminate()
                    try:
                        await asyncio.wait_for(self.process.wait(), timeout=2.0)
                    except asyncio.TimeoutError:
                        # Force kill as last resort
                        logger.warning(f"Force killing process for {self.username}")
                        self.process.kill()
                        try:
                            await asyncio.wait_for(self.process.wait(), timeout=1.0)
                        except asyncio.TimeoutError:
                            pass
            except Exception as e:
                logger.warning(f"Error terminating SSH process for {self.username}: {e}")
            finally:
                self.process.close()
        if self.conn:
            self.conn.close()
        logger.info(f"SSH connection closed for {self.username}")

    async def handle_websocket_input(self):
        """Forward WebSocket input to SSH."""
        try:
            while self.running:
                try:
                    message = await asyncio.wait_for(
                        self.websocket.receive_text(),
                        timeout=1.0,
                    )
                    self.last_activity = asyncio.get_event_loop().time()

                    # Parse message - could be raw text or JSON
                    try:
                        data = json.loads(message)
                        if data.get("type") == "resize" and self.process:
                            cols = data.get("cols", 80)
                            rows = data.get("rows", 24)
                            self.process.change_terminal_size(cols, rows)
                            continue
                        elif data.get("type") == "input":
                            message = data.get("data", "")
                    except json.JSONDecodeError:
                        pass  # Raw text input

                    if self.process and self.process.stdin:
                        self.process.stdin.write(message)

                except asyncio.TimeoutError:
                    # Check for idle timeout
                    if (
                        asyncio.get_event_loop().time() - self.last_activity
                        > IDLE_TIMEOUT
                    ):
                        logger.info(f"Idle timeout for {self.username}")
                        await self.websocket.send_text(
                            "\r\n\x1b[33m[Session timed out due to inactivity]\x1b[0m\r\n"
                        )
                        break
                    continue

        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for {self.username}")
        except Exception as e:
            logger.error(f"WebSocket input error: {e}")
        finally:
            self.running = False

    async def handle_ssh_output(self):
        """Forward SSH output to WebSocket."""
        try:
            while self.running and self.process:
                try:
                    data = await asyncio.wait_for(
                        self.process.stdout.read(4096),
                        timeout=1.0,
                    )
                    if not data:
                        break
                    await self.websocket.send_text(data)
                except asyncio.TimeoutError:
                    continue
                except asyncssh.TerminalSizeChanged:
                    continue

        except Exception as e:
            if self.running:
                logger.error(f"SSH output error: {e}")
        finally:
            self.running = False


@terminal_router.websocket("/ws/terminal/{session_id}")
async def websocket_terminal(websocket: WebSocket, session_id: int, token: str | None = None):
    """WebSocket endpoint for terminal access.

    Validates the session and access token, retrieves credentials, and bridges
    the WebSocket to an SSH connection.
    """
    await websocket.accept()

    # Validate session
    db = get_db()
    session = await db.get_session(session_id)

    if not session:
        await websocket.send_text(
            "\x1b[31mError: Session not found\x1b[0m\r\n"
        )
        await websocket.close(code=4004)
        return

    if session["status"] not in ("active", "playing"):
        await websocket.send_text(
            f"\x1b[31mError: Session is {session['status']}, not active\x1b[0m\r\n"
        )
        await websocket.close(code=4003)
        return

    # Validate access token (V6 security fix: constant-time comparison)
    if not secrets.compare_digest(
        session.get("access_token") or "",
        token or ""
    ):
        await websocket.send_text(
            "\x1b[31mError: Invalid access token\x1b[0m\r\n"
        )
        await websocket.close(code=4003)
        return

    username = session["username"]
    password = session["password"]

    if not username or not password:
        await websocket.send_text(
            "\x1b[31mError: Missing credentials\x1b[0m\r\n"
        )
        await websocket.close(code=4002)
        return

    # Create SSH bridge
    bridge = SSHBridge(websocket, username, password)

    if not await bridge.connect():
        await websocket.send_text(
            "\x1b[31mError: Failed to connect to SSH server\x1b[0m\r\n"
        )
        await websocket.close(code=4001)
        return

    # Run input and output handlers concurrently
    try:
        await asyncio.gather(
            bridge.handle_websocket_input(),
            bridge.handle_ssh_output(),
        )
    finally:
        await bridge.disconnect()
        try:
            await websocket.close()
        except Exception:
            pass
