import pytest
import json
import sys
from unittest.mock import patch, MagicMock

# Setup common mocks
from test.common.test_mocks import setup_common_mocks, patch_minio_client_initialization

# Initialize common mocks
mocks = setup_common_mocks()

# Mock database modules before importing config_utils
database_client_mock = MagicMock()
database_client_mock.get_db_session = MagicMock()

database_models_mock = MagicMock()
database_models_mock.TenantConfig = MagicMock()

database_tenant_config_db_mock = MagicMock()
database_tenant_config_db_mock.get_all_configs_by_tenant_id = MagicMock()
database_tenant_config_db_mock.get_single_config_info = MagicMock()
database_tenant_config_db_mock.insert_config = MagicMock()
database_tenant_config_db_mock.delete_config_by_tenant_config_id = MagicMock()
database_tenant_config_db_mock.update_config_by_tenant_config_id_and_data = MagicMock()

database_model_management_db_mock = MagicMock()
database_model_management_db_mock.get_model_by_model_id = MagicMock()

# Mock sqlalchemy
sqlalchemy_mock = MagicMock()
sqlalchemy_exc_mock = MagicMock()
sqlalchemy_exc_mock.SQLAlchemyError = Exception
sqlalchemy_sql_mock = MagicMock()
sqlalchemy_sql_mock.func = MagicMock()

sqlalchemy_mock.exc = sqlalchemy_exc_mock
sqlalchemy_mock.sql = sqlalchemy_sql_mock

# Mock consts
consts_mock = MagicMock()

# Set up sys.modules mocks
sys.modules['database.client'] = database_client_mock
sys.modules['database.db_models'] = database_models_mock
sys.modules['database.tenant_config_db'] = database_tenant_config_db_mock
sys.modules['database.model_management_db'] = database_model_management_db_mock
sys.modules['sqlalchemy'] = sqlalchemy_mock
sys.modules['sqlalchemy.exc'] = sqlalchemy_exc_mock
sys.modules['sqlalchemy.sql'] = sqlalchemy_sql_mock
sys.modules['consts.const'] = consts_mock

# Patch storage factory before importing
with patch_minio_client_initialization():
    from backend.utils.config_utils import (
        safe_value,
        safe_list,
        get_env_key,
        get_model_name_from_config,
        TenantConfigManager
    )


class TestSafeValue:
    """Test safe_value function"""

    def test_safe_value_with_none(self):
        """Test with None value"""
        assert safe_value(None) == ""

    def test_safe_value_with_string(self):
        """Test with string value"""
        assert safe_value("test") == "test"


class TestSafeList:
    """Test safe_list function"""

    def test_safe_list_with_none(self):
        """Test with None value"""
        assert safe_list(None) == "[]"

    def test_safe_list_with_list(self):
        """Test with list value"""
        test_list = [1, 2, 3]
        result = safe_list(test_list)
        assert result == "[1, 2, 3]"
        assert json.loads(result) == test_list


class TestGetEnvKey:
    """Test get_env_key function"""

    def test_get_env_key_camel_case(self):
        """Test camelCase to SNAKE_CASE conversion"""
        assert get_env_key("camelCase") == "CAMEL_CASE"

    def test_get_env_key_with_numbers(self):
        """Test conversion with numbers"""
        assert get_env_key("user123Name") == "USER123_NAME"


class TestGetModelNameFromConfig:
    """Test get_model_name_from_config function"""

    def test_get_model_name_from_config_with_model_repo(self):
        """Test with model repository"""
        config = {"model_repo": "openai", "model_name": "gpt-4"}
        assert get_model_name_from_config(config) == "openai/gpt-4"

    def test_get_model_name_from_config_without_model_repo(self):
        """Test without model repository"""
        config = {"model_repo": "", "model_name": "gpt-4"}
        assert get_model_name_from_config(config) == "gpt-4"


class TestTenantConfigManager:
    """Test TenantConfigManager class"""

    @pytest.fixture
    def config_manager(self):
        """Create config manager instance"""
        return TenantConfigManager()

    @pytest.fixture
    def mock_configs(self):
        """Mock config data"""
        return [
            {
                "config_key": "model_config",
                "config_value": "123",
                "tenant_config_id": 1
            },
            {
                "config_key": "app_setting",
                "config_value": "test_value",
                "tenant_config_id": 2
            }
        ]

    def test_init(self, config_manager):
        """Test initialization"""
        # Manager no longer exposes in-process caches; just ensure instance constructs
        assert isinstance(config_manager, TenantConfigManager)

    def test_get_cache_key(self, config_manager):
        """Test cache key generation"""
        # _get_cache_key removed with cache removal; ensure attribute not present
        assert not hasattr(config_manager, "_get_cache_key")

    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_load_config_success(self, mock_get_configs, config_manager, mock_configs):
        """Test successful config loading"""
        mock_get_configs.return_value = mock_configs

        result = config_manager.load_config("tenant1")

        assert result == {
            "model_config": "123",
            "app_setting": "test_value"
        }
        # No in-process cache expected
        assert not hasattr(config_manager, "config_cache")

    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_load_config_no_configs(self, mock_get_configs, config_manager):
        """Test loading with no configs"""
        mock_get_configs.return_value = []

        result = config_manager.load_config("tenant1")

        assert result == {}
        assert not hasattr(config_manager, "config_cache")

    def test_load_config_invalid_tenant_id(self, config_manager):
        """Test loading with invalid tenant ID"""
        result = config_manager.load_config("")
        assert result == {}

    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_load_config_cache_hit(self, mock_get_configs, config_manager, mock_configs):
        """Test cache hit"""
        mock_get_configs.return_value = mock_configs

        # First load
        config_manager.load_config("tenant1")
        # Second load should NOT use an in-process cache (DB called again)
        result = config_manager.load_config("tenant1")

        # Verify two database queries (no cache)
        assert mock_get_configs.call_count == 2
        assert result == {
            "model_config": "123",
            "app_setting": "test_value"
        }

    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_load_config_force_reload(self, mock_get_configs, config_manager, mock_configs):
        """Test force reload"""
        mock_get_configs.return_value = mock_configs

        # First load
        config_manager.load_config("tenant1")
        # Force reload
        result = config_manager.load_config("tenant1", force_reload=True)

        # Verify two database queries
        assert mock_get_configs.call_count == 2
        assert result == {
            "model_config": "123",
            "app_setting": "test_value"
        }

    @patch('backend.utils.config_utils.get_model_by_model_id')
    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_get_model_config_success(self, mock_get_configs, mock_get_model, config_manager):
        """Test successful model config retrieval"""
        mock_get_configs.return_value = [
            {"config_key": "model_config", "config_value": "123"}]
        mock_get_model.return_value = {
            "model_id": 123, "model_name": "test_model"}

        result = config_manager.get_model_config("model_config", {}, "tenant1")

        assert result == {"model_id": 123, "model_name": "test_model"}

    @patch('backend.utils.config_utils.get_model_by_model_id')
    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_get_model_config_invalid_model_id(self, mock_get_configs, mock_get_model, config_manager):
        """Test with invalid model ID"""
        mock_get_configs.return_value = [
            {"config_key": "model_config", "config_value": "invalid"}]
        mock_get_model.side_effect = ValueError("Invalid model_id")

        result = config_manager.get_model_config("model_config", {}, "tenant1")

        assert result == {}

    def test_get_model_config_no_tenant_id(self, config_manager):
        """Test without tenant ID"""
        result = config_manager.get_model_config("key")
        assert result == {}

    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_get_app_config_success(self, mock_get_configs, config_manager):
        """Test successful app config retrieval"""
        mock_get_configs.return_value = [
            {"config_key": "app_setting", "config_value": "test_value"}]

        result = config_manager.get_app_config("app_setting", "", "tenant1")

        assert result == "test_value"

    def test_get_app_config_no_tenant_id(self, config_manager):
        """Test without tenant ID"""
        result = config_manager.get_app_config("key")
        assert result == ""

    @patch('backend.utils.config_utils.get_single_config_info')
    @patch('backend.utils.config_utils.get_db_session')
    def test_set_single_config_success(self, mock_session, mock_get_single, config_manager):
        """Test successful single config setting"""
        # Mock the database session
        mock_session_instance = mock_session.return_value.__enter__.return_value
        mock_get_single.return_value = {
            "tenant_config_id": 1}  # Existing config to delete

        config_manager.set_single_config("user1", "tenant1", "key1", "value1")

        # Verify delete was called on the existing config
        mock_session_instance.query.return_value.filter.return_value.update.assert_called_once()
        # Verify new config was added
        mock_session_instance.add.assert_called_once()
        # Verify commit was called
        mock_session_instance.commit.assert_called_once()

    def test_set_single_config_no_tenant_id(self, config_manager):
        """Test setting config without tenant ID"""
        config_manager.set_single_config("user1", None, "key1", "value1")
        # Should not raise exception

    @patch('backend.utils.config_utils.delete_config_by_tenant_config_id')
    @patch('backend.utils.config_utils.get_single_config_info')
    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_delete_single_config_success(self, mock_get_configs, mock_get_single, mock_delete, config_manager):
        """Test successful single config deletion"""
        mock_get_configs.return_value = []
        mock_get_single.return_value = {"tenant_config_id": 1}

        config_manager.delete_single_config("tenant1", "key1")

        mock_delete.assert_called_once_with(1)
        assert not hasattr(config_manager, "config_cache")

    def test_delete_single_config_no_tenant_id(self, config_manager):
        """Test deleting config without tenant ID"""
        config_manager.delete_single_config(None, "key1")
        # Should not raise exception

    @patch('backend.utils.config_utils.update_config_by_tenant_config_id_and_data')
    @patch('backend.utils.config_utils.get_single_config_info')
    @patch('backend.utils.config_utils.get_all_configs_by_tenant_id')
    def test_update_single_config_success(self, mock_get_configs, mock_get_single, mock_update, config_manager):
        """Test successful single config update"""
        mock_get_configs.return_value = []
        mock_get_single.return_value = {"tenant_config_id": 1}

        config_manager.update_single_config("tenant1", "key1")

        mock_update.assert_called_once()

    def test_update_single_config_no_tenant_id(self, config_manager):
        """Test updating config without tenant ID"""
        config_manager.update_single_config(None, "key1")
        # Should not raise exception

    def test_clear_cache_specific_tenant(self, config_manager):
        """Test clearing cache for specific tenant"""
        # clear_cache removed with cache removal: method should not exist
        assert not hasattr(config_manager, "clear_cache")

    def test_clear_cache_all(self, config_manager):
        """Test clearing all cache"""
        # clear_cache removed with cache removal: method should not exist
        assert not hasattr(config_manager, "clear_cache")
