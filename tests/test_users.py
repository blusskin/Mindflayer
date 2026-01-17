"""Tests for user management."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from orange_nethack.users.manager import UserManager, UserManagerError


@pytest.fixture
def user_manager():
    with patch("orange_nethack.users.manager.get_settings") as mock_settings:
        mock_settings.return_value.nethack_user_prefix = "nh_"
        mock_settings.return_value.nethack_group = "games"
        manager = UserManager()
        return manager


class TestUserManager:
    @pytest.mark.asyncio
    async def test_user_exists_true(self, user_manager):
        with patch.object(user_manager, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "", "")

            exists = await user_manager.user_exists("nh_testuser")

            assert exists is True
            mock_run.assert_called_once_with("id", "nh_testuser")

    @pytest.mark.asyncio
    async def test_user_exists_false(self, user_manager):
        with patch.object(user_manager, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "no such user")

            exists = await user_manager.user_exists("nh_nonexistent")

            assert exists is False

    @pytest.mark.asyncio
    async def test_create_user_invalid_prefix(self, user_manager):
        with pytest.raises(UserManagerError, match="Invalid username prefix"):
            await user_manager.create_user("baduser", "password123")

    @pytest.mark.asyncio
    async def test_create_user_already_exists(self, user_manager):
        with patch.object(user_manager, "user_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True

            # Should return without error
            await user_manager.create_user("nh_existing", "password123")

            mock_exists.assert_called_once_with("nh_existing")

    @pytest.mark.asyncio
    async def test_create_user_success(self, user_manager):
        with patch.object(user_manager, "user_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            with patch.object(
                user_manager, "_run_command", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = (0, "", "")

                with patch("asyncio.create_subprocess_exec") as mock_subprocess:
                    mock_process = AsyncMock()
                    mock_process.returncode = 0
                    mock_process.communicate.return_value = (b"", b"")
                    mock_subprocess.return_value = mock_process

                    await user_manager.create_user("nh_newuser", "password123")

                    # Check useradd was called
                    mock_run.assert_called()
                    useradd_call = mock_run.call_args_list[0]
                    assert useradd_call[0][0] == "useradd"
                    assert "nh_newuser" in useradd_call[0]

    @pytest.mark.asyncio
    async def test_create_user_useradd_fails(self, user_manager):
        with patch.object(user_manager, "user_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            with patch.object(
                user_manager, "_run_command", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = (1, "", "useradd: error")

                with pytest.raises(UserManagerError, match="Failed to create user"):
                    await user_manager.create_user("nh_newuser", "password123")

    @pytest.mark.asyncio
    async def test_delete_user_invalid_prefix(self, user_manager):
        with pytest.raises(UserManagerError, match="Invalid username prefix"):
            await user_manager.delete_user("baduser")

    @pytest.mark.asyncio
    async def test_delete_user_not_exists(self, user_manager):
        with patch.object(user_manager, "user_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = False

            # Should return without error
            await user_manager.delete_user("nh_nonexistent")

    @pytest.mark.asyncio
    async def test_delete_user_success(self, user_manager):
        with patch.object(user_manager, "user_exists", new_callable=AsyncMock) as mock_exists:
            mock_exists.return_value = True

            with patch.object(
                user_manager, "_run_command", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = (0, "", "")

                with patch("asyncio.sleep", new_callable=AsyncMock):
                    await user_manager.delete_user("nh_olduser")

                    # Check pkill and userdel were called
                    calls = mock_run.call_args_list
                    assert any("pkill" in str(c) for c in calls)
                    assert any("userdel" in str(c) for c in calls)

    @pytest.mark.asyncio
    async def test_get_user_processes(self, user_manager):
        with patch.object(user_manager, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (0, "1234\n5678\n", "")

            pids = await user_manager.get_user_processes("nh_testuser")

            assert pids == [1234, 5678]

    @pytest.mark.asyncio
    async def test_get_user_processes_none(self, user_manager):
        with patch.object(user_manager, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = (1, "", "")

            pids = await user_manager.get_user_processes("nh_testuser")

            assert pids == []

    @pytest.mark.asyncio
    async def test_is_user_playing_true(self, user_manager):
        with patch.object(
            user_manager, "get_user_processes", new_callable=AsyncMock
        ) as mock_processes:
            mock_processes.return_value = [1234]

            with patch.object(
                user_manager, "_run_command", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = (0, "nethack", "")

                is_playing = await user_manager.is_user_playing("nh_testuser")

                assert is_playing is True

    @pytest.mark.asyncio
    async def test_is_user_playing_false_no_processes(self, user_manager):
        with patch.object(
            user_manager, "get_user_processes", new_callable=AsyncMock
        ) as mock_processes:
            mock_processes.return_value = []

            is_playing = await user_manager.is_user_playing("nh_testuser")

            assert is_playing is False

    @pytest.mark.asyncio
    async def test_is_user_playing_false_different_process(self, user_manager):
        with patch.object(
            user_manager, "get_user_processes", new_callable=AsyncMock
        ) as mock_processes:
            mock_processes.return_value = [1234]

            with patch.object(
                user_manager, "_run_command", new_callable=AsyncMock
            ) as mock_run:
                mock_run.return_value = (0, "bash", "")

                is_playing = await user_manager.is_user_playing("nh_testuser")

                assert is_playing is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_users(self, user_manager):
        with patch.object(
            user_manager, "delete_user", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.return_value = None

            count = await user_manager.cleanup_expired_users(
                ["nh_user1", "nh_user2", "nh_user3"]
            )

            assert count == 3
            assert mock_delete.call_count == 3

    @pytest.mark.asyncio
    async def test_cleanup_expired_users_partial_failure(self, user_manager):
        with patch.object(
            user_manager, "delete_user", new_callable=AsyncMock
        ) as mock_delete:
            mock_delete.side_effect = [None, UserManagerError("Failed"), None]

            count = await user_manager.cleanup_expired_users(
                ["nh_user1", "nh_user2", "nh_user3"]
            )

            assert count == 2
