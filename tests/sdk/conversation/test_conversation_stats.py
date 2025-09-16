import base64
import pickle
import tempfile
import uuid
from unittest.mock import patch

import pytest
from pydantic import SecretStr

from openhands.sdk import LLM, ConversationStats, LLMRegistry, RegistryEvent
from openhands.sdk.io.local import LocalFileStore
from openhands.sdk.llm.utils.metrics import Metrics


# Test UUIDs
TEST_CONVERSATION_ID = uuid.UUID("12345678-1234-5678-9abc-123456789abc")
CONV_MERGE_A_ID = uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONV_MERGE_B_ID = uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")


@pytest.fixture
def mock_file_store():
    """Create a mock file store for testing."""
    return LocalFileStore(root=tempfile.mkdtemp())


@pytest.fixture
def conversation_stats(mock_file_store):
    """Create a ConversationStats instance for testing."""
    return ConversationStats(
        file_store=mock_file_store,
        conversation_id=TEST_CONVERSATION_ID,
    )


@pytest.fixture
def mock_llm_registry():
    """Create a mock LLM registry that properly simulates LLM registration."""
    registry = LLMRegistry()
    return registry


@pytest.fixture
def connected_registry_and_stats(mock_llm_registry, conversation_stats):
    """Connect the LLMRegistry and ConversationStats properly."""
    # Subscribe to LLM registry events to track metrics
    mock_llm_registry.subscribe(conversation_stats.register_llm)
    return mock_llm_registry, conversation_stats


def test_conversation_stats_initialization(conversation_stats):
    """Test that ConversationStats initializes correctly."""
    assert conversation_stats.conversation_id == TEST_CONVERSATION_ID
    assert conversation_stats.service_to_metrics == {}
    assert isinstance(conversation_stats.restored_metrics, dict)


def test_save_metrics(conversation_stats, mock_file_store):
    """Test that metrics are saved correctly."""
    # Add a service with metrics
    service_id = "test-service"
    metrics = Metrics(model_name="gpt-4")
    metrics.add_cost(0.05)
    conversation_stats.service_to_metrics[service_id] = metrics

    # Save metrics
    conversation_stats.save_metrics()

    # Verify that metrics were saved to the file store
    try:
        # Verify the saved content can be decoded and unpickled
        encoded = mock_file_store.read(conversation_stats.metrics_file_name)
        pickled = base64.b64decode(encoded)
        restored = pickle.loads(pickled)

        assert service_id in restored
        assert restored[service_id].accumulated_cost == 0.05
    except FileNotFoundError:
        pytest.fail(f"File not found: {conversation_stats.metrics_file_name}")


def test_maybe_restore_metrics(mock_file_store):
    """Test that metrics are restored correctly."""
    # Create metrics to save
    service_id = "test-service"
    metrics = Metrics(model_name="gpt-4")
    metrics.add_cost(0.1)
    service_to_metrics = {service_id: metrics}

    # Serialize and save metrics
    pickled = pickle.dumps(service_to_metrics)
    serialized_metrics = base64.b64encode(pickled).decode("utf-8")

    # Create a new ConversationStats with pre-populated file store
    conversation_id = TEST_CONVERSATION_ID

    # Write to the correct path (using the metrics_file_name)
    mock_file_store.write("conversation_stats.pkl", serialized_metrics)

    # Create ConversationStats which should restore metrics
    stats = ConversationStats(
        file_store=mock_file_store, conversation_id=conversation_id
    )

    # Verify metrics were restored
    assert service_id in stats.restored_metrics
    assert stats.restored_metrics[service_id].accumulated_cost == 0.1


def test_get_combined_metrics(conversation_stats):
    """Test that combined metrics are calculated correctly."""
    # Add multiple services with metrics
    service1 = "service1"
    metrics1 = Metrics(model_name="gpt-4")
    metrics1.add_cost(0.05)
    metrics1.add_token_usage(
        prompt_tokens=100,
        completion_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
        context_window=8000,
        response_id="resp1",
    )

    service2 = "service2"
    metrics2 = Metrics(model_name="gpt-3.5")
    metrics2.add_cost(0.02)
    metrics2.add_token_usage(
        prompt_tokens=200,
        completion_tokens=100,
        cache_read_tokens=0,
        cache_write_tokens=0,
        context_window=4000,
        response_id="resp2",
    )

    conversation_stats.service_to_metrics[service1] = metrics1
    conversation_stats.service_to_metrics[service2] = metrics2

    # Get combined metrics
    combined = conversation_stats.get_combined_metrics()

    # Verify combined metrics
    assert combined.accumulated_cost == 0.07  # 0.05 + 0.02
    assert combined.accumulated_token_usage.prompt_tokens == 300  # 100 + 200
    assert combined.accumulated_token_usage.completion_tokens == 150  # 50 + 100
    assert (
        combined.accumulated_token_usage.context_window == 8000
    )  # max of 8000 and 4000


def test_get_metrics_for_service(conversation_stats):
    """Test that metrics for a specific service are retrieved correctly."""
    # Add a service with metrics
    service_id = "test-service"
    metrics = Metrics(model_name="gpt-4")
    metrics.add_cost(0.05)
    conversation_stats.service_to_metrics[service_id] = metrics

    # Get metrics for the service
    retrieved_metrics = conversation_stats.get_metrics_for_service(service_id)

    # Verify metrics
    assert retrieved_metrics.accumulated_cost == 0.05
    assert retrieved_metrics is metrics  # Should be the same object

    # Test getting metrics for non-existent service
    # Use a specific exception message pattern instead of a blind Exception
    with pytest.raises(Exception, match="LLM service does not exist"):
        conversation_stats.get_metrics_for_service("non-existent-service")


def test_register_llm_with_new_service(conversation_stats):
    """Test registering a new LLM service."""
    # Patch the LLM class to avoid actual API calls
    with patch("openhands.sdk.llm.llm.litellm_completion"):
        llm = LLM(
            service_id="new-service",
            model="gpt-4o",
            api_key=SecretStr("test_key"),
            num_retries=2,
            retry_min_wait=1,
            retry_max_wait=2,
        )

        # Create a registry event
        service_id = "new-service"
        event = RegistryEvent(llm=llm, service_id=service_id)

        # Register the LLM
        conversation_stats.register_llm(event)

        # Verify the service was registered
        assert service_id in conversation_stats.service_to_metrics
        assert conversation_stats.service_to_metrics[service_id] is llm.metrics


def test_register_llm_with_restored_metrics(conversation_stats):
    """Test registering an LLM service with restored metrics."""
    # Create restored metrics
    service_id = "restored-service"
    restored_metrics = Metrics(model_name="gpt-4")
    restored_metrics.add_cost(0.1)
    conversation_stats.restored_metrics = {service_id: restored_metrics}

    # Patch the LLM class to avoid actual API calls
    with patch("openhands.sdk.llm.llm.litellm_completion"):
        llm = LLM(
            service_id=service_id,
            model="gpt-4o",
            api_key=SecretStr("test_key"),
            num_retries=2,
            retry_min_wait=1,
            retry_max_wait=2,
        )

        # Create a registry event
        event = RegistryEvent(llm=llm, service_id=service_id)

        # Register the LLM
        conversation_stats.register_llm(event)

        # Verify the service was registered with restored metrics
        assert service_id in conversation_stats.service_to_metrics
        assert conversation_stats.service_to_metrics[service_id] is llm.metrics
        assert llm.metrics is not None
        assert llm.metrics.accumulated_cost == 0.1  # Restored cost

        # Verify the specific service was removed from restored_metrics
        assert service_id not in conversation_stats.restored_metrics
        assert hasattr(
            conversation_stats, "restored_metrics"
        )  # The dict should still exist


def test_llm_registry_notifications(connected_registry_and_stats):
    """Test that LLM registry notifications update conversation stats."""
    mock_llm_registry, conversation_stats = connected_registry_and_stats

    # Create a new LLM through the registry
    service_id = "test-service"

    # Create LLM directly
    llm = LLM(
        service_id=service_id,
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Add LLM to registry (this should trigger the notification)
    mock_llm_registry.add(service_id, llm)

    # Verify the service was registered in conversation stats
    assert service_id in conversation_stats.service_to_metrics
    assert conversation_stats.service_to_metrics[service_id] is llm.metrics

    # Add some metrics to the LLM
    assert llm.metrics is not None
    llm.metrics.add_cost(0.05)
    llm.metrics.add_token_usage(
        prompt_tokens=100,
        completion_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
        context_window=8000,
        response_id="resp1",
    )

    # Verify the metrics are reflected in conversation stats
    assert conversation_stats.service_to_metrics[service_id].accumulated_cost == 0.05
    assert (
        conversation_stats.service_to_metrics[
            service_id
        ].accumulated_token_usage.prompt_tokens
        == 100
    )
    assert (
        conversation_stats.service_to_metrics[
            service_id
        ].accumulated_token_usage.completion_tokens
        == 50
    )

    # Get combined metrics and verify
    combined = conversation_stats.get_combined_metrics()
    assert combined.accumulated_cost == 0.05
    assert combined.accumulated_token_usage.prompt_tokens == 100
    assert combined.accumulated_token_usage.completion_tokens == 50


def test_multiple_llm_services(connected_registry_and_stats):
    """Test tracking metrics for multiple LLM services."""
    mock_llm_registry, conversation_stats = connected_registry_and_stats

    # Create multiple LLMs through the registry
    service1 = "service1"
    service2 = "service2"

    # Create LLMs directly
    llm1 = LLM(
        service_id=service1,
        model="gpt-4o",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    llm2 = LLM(
        service_id=service2,
        model="gpt-3.5-turbo",
        api_key=SecretStr("test_key"),
        num_retries=2,
        retry_min_wait=1,
        retry_max_wait=2,
    )

    # Add LLMs to registry (this should trigger notifications)
    mock_llm_registry.add(service1, llm1)
    mock_llm_registry.add(service2, llm2)

    # Add different metrics to each LLM
    assert llm1.metrics is not None
    llm1.metrics.add_cost(0.05)
    llm1.metrics.add_token_usage(
        prompt_tokens=100,
        completion_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
        context_window=8000,
        response_id="resp1",
    )

    assert llm2.metrics is not None
    llm2.metrics.add_cost(0.02)
    llm2.metrics.add_token_usage(
        prompt_tokens=200,
        completion_tokens=100,
        cache_read_tokens=0,
        cache_write_tokens=0,
        context_window=4000,
        response_id="resp2",
    )

    # Verify services were registered in conversation stats
    assert service1 in conversation_stats.service_to_metrics
    assert service2 in conversation_stats.service_to_metrics

    # Verify individual metrics
    assert conversation_stats.service_to_metrics[service1].accumulated_cost == 0.05
    assert conversation_stats.service_to_metrics[service2].accumulated_cost == 0.02

    # Get combined metrics and verify
    combined = conversation_stats.get_combined_metrics()
    assert combined.accumulated_cost == 0.07  # 0.05 + 0.02
    assert combined.accumulated_token_usage.prompt_tokens == 300  # 100 + 200
    assert combined.accumulated_token_usage.completion_tokens == 150  # 50 + 100
    assert (
        combined.accumulated_token_usage.context_window == 8000
    )  # max of 8000 and 4000


def test_register_llm_with_multiple_restored_services_bug(conversation_stats):
    """
    Test that reproduces the bug where del self.restored_metrics
    deletes entire dict instead of specific service.
    """

    # Create restored metrics for multiple services
    service_id_1 = "service-1"
    service_id_2 = "service-2"

    restored_metrics_1 = Metrics(model_name="gpt-4")
    restored_metrics_1.add_cost(0.1)

    restored_metrics_2 = Metrics(model_name="gpt-3.5")
    restored_metrics_2.add_cost(0.05)

    # Set up restored metrics for both services
    conversation_stats.restored_metrics = {
        service_id_1: restored_metrics_1,
        service_id_2: restored_metrics_2,
    }

    # Patch the LLM class to avoid actual API calls
    with patch("openhands.sdk.llm.llm.litellm_completion"):
        # Register first LLM
        llm_1 = LLM(
            service_id=service_id_1,
            model="gpt-4o",
            api_key=SecretStr("test_key"),
            num_retries=2,
            retry_min_wait=1,
            retry_max_wait=2,
        )
        event_1 = RegistryEvent(llm=llm_1, service_id=service_id_1)
        conversation_stats.register_llm(event_1)

        # Verify first service was registered with restored metrics
        assert service_id_1 in conversation_stats.service_to_metrics
        assert llm_1.metrics is not None
        assert llm_1.metrics.accumulated_cost == 0.1

        # After registering first service,
        # restored_metrics should still contain service_id_2
        assert service_id_2 in conversation_stats.restored_metrics

        # Register second LLM - this should also work with restored metrics
        llm_2 = LLM(
            service_id=service_id_2,
            model="gpt-3.5-turbo",
            api_key=SecretStr("test_key"),
            num_retries=2,
            retry_min_wait=1,
            retry_max_wait=2,
        )
        event_2 = RegistryEvent(llm=llm_2, service_id=service_id_2)
        conversation_stats.register_llm(event_2)

        # Verify second service was registered with restored metrics
        assert service_id_2 in conversation_stats.service_to_metrics
        assert llm_2.metrics is not None
        assert llm_2.metrics.accumulated_cost == 0.05

        # After both services are registered, restored_metrics should be empty
        assert len(conversation_stats.restored_metrics) == 0


def test_save_and_restore_workflow(mock_file_store):
    """Test the full workflow of saving and restoring metrics."""
    # Create initial conversation stats
    conversation_id = TEST_CONVERSATION_ID

    stats1 = ConversationStats(
        file_store=mock_file_store, conversation_id=conversation_id
    )

    # Add a service with metrics
    service_id = "test-service"
    metrics = Metrics(model_name="gpt-4")
    metrics.add_cost(0.05)
    metrics.add_token_usage(
        prompt_tokens=100,
        completion_tokens=50,
        cache_read_tokens=0,
        cache_write_tokens=0,
        context_window=8000,
        response_id="resp1",
    )
    stats1.service_to_metrics[service_id] = metrics

    # Save metrics
    stats1.save_metrics()

    # Create a new conversation stats instance that should restore the metrics
    stats2 = ConversationStats(
        file_store=mock_file_store, conversation_id=conversation_id
    )

    # Verify metrics were restored
    assert service_id in stats2.restored_metrics
    assert stats2.restored_metrics[service_id].accumulated_cost == 0.05
    token_usage = stats2.restored_metrics[service_id].accumulated_token_usage
    assert token_usage is not None
    assert token_usage.prompt_tokens == 100
    assert token_usage.completion_tokens == 50

    # Patch the LLM class to avoid actual API calls
    with patch("openhands.sdk.llm.llm.litellm_completion"):
        llm = LLM(
            service_id=service_id,
            model="gpt-4o",
            api_key=SecretStr("test_key"),
            num_retries=2,
            retry_min_wait=1,
            retry_max_wait=2,
        )

        # Create a registry event
        event = RegistryEvent(llm=llm, service_id=service_id)

        # Register the LLM to trigger restoration
        stats2.register_llm(event)

        # Verify metrics were applied to the LLM
        assert llm.metrics is not None
        assert llm.metrics.accumulated_cost == 0.05
        assert llm.metrics.accumulated_token_usage is not None
        assert llm.metrics.accumulated_token_usage.prompt_tokens == 100
        assert llm.metrics.accumulated_token_usage.completion_tokens == 50


def test_merge_conversation_stats_success_non_overlapping(mock_file_store):
    """Merging two ConversationStats combines only restored metrics. Active metrics
    (service_to_metrics) are not merged; if present, an error is logged but
    execution continues. Incoming restored metrics overwrite duplicates.
    """
    stats_a = ConversationStats(
        file_store=mock_file_store, conversation_id=CONV_MERGE_A_ID
    )
    stats_b = ConversationStats(
        file_store=mock_file_store, conversation_id=CONV_MERGE_B_ID
    )

    # Self active + restored
    m_a_active = Metrics(model_name="model-a")
    m_a_active.add_cost(0.1)
    m_a_restored = Metrics(model_name="model-a")
    m_a_restored.add_cost(0.2)
    stats_a.service_to_metrics["a-active"] = m_a_active
    stats_a.restored_metrics = {"a-restored": m_a_restored}

    # Other active + restored
    m_b_active = Metrics(model_name="model-b")
    m_b_active.add_cost(0.3)
    m_b_restored = Metrics(model_name="model-b")
    m_b_restored.add_cost(0.4)
    stats_b.service_to_metrics["b-active"] = m_b_active
    stats_b.restored_metrics = {"b-restored": m_b_restored}

    # Merge B into A
    stats_a.merge_and_save(stats_b)

    # Active metrics should not be merged; only self's active metrics remain
    assert set(stats_a.service_to_metrics.keys()) == {
        "a-active",
    }

    # Restored metrics from both sides should be in A's restored_metrics
    assert set(stats_a.restored_metrics.keys()) == {
        "a-restored",
        "b-restored",
    }

    # The exact Metrics objects should be present (no copies)
    assert stats_a.service_to_metrics["a-active"] is m_a_active
    assert stats_a.restored_metrics["a-restored"] is m_a_restored
    assert stats_a.restored_metrics["b-restored"] is m_b_restored

    # Merge triggers a save; confirm the saved blob decodes to expected keys
    # The save_metrics method combines both service_to_metrics and restored_metrics
    encoded = mock_file_store.read(stats_a.metrics_file_name)
    pickled = base64.b64decode(encoded)
    restored_dict = pickle.loads(pickled)
    assert set(restored_dict.keys()) == {
        "a-active",
        "a-restored",
        "b-restored",
    }


@pytest.mark.parametrize(
    "self_side,other_side",
    [
        ("active", "active"),
        ("restored", "active"),
        ("active", "restored"),
        ("restored", "restored"),
    ],
)
def test_merge_conversation_stats_duplicates_overwrite_and_log_errors(
    mock_file_store, self_side, other_side
):
    stats_a = ConversationStats(
        file_store=mock_file_store, conversation_id=CONV_MERGE_A_ID
    )
    stats_b = ConversationStats(
        file_store=mock_file_store, conversation_id=CONV_MERGE_B_ID
    )

    # Place the same service id on the specified sides
    dupe_id = "dupe-service"
    m1 = Metrics(model_name="m")
    m1.add_cost(0.1)  # ensure not dropped
    m2 = Metrics(model_name="m")
    m2.add_cost(0.2)  # ensure not dropped

    if self_side == "active":
        stats_a.service_to_metrics[dupe_id] = m1
    else:
        stats_a.restored_metrics[dupe_id] = m1

    if other_side == "active":
        stats_b.service_to_metrics[dupe_id] = m2
    else:
        stats_b.restored_metrics[dupe_id] = m2

    # Perform merge; should not raise and should
    # log error internally if active metrics present
    stats_a.merge_and_save(stats_b)

    # Only restored metrics are merged; duplicates are allowed with incoming overwriting
    if other_side == "restored":
        assert dupe_id in stats_a.restored_metrics
        assert stats_a.restored_metrics[dupe_id] is m2  # incoming overwrites existing
    else:
        # No restored metric came from incoming; existing restored stays as-is
        if self_side == "restored":
            assert dupe_id in stats_a.restored_metrics
            assert stats_a.restored_metrics[dupe_id] is m1
        else:
            assert dupe_id not in stats_a.restored_metrics


def test_save_metrics_preserves_restored_metrics_fix(mock_file_store):
    """
    Test that save_metrics correctly preserves
    restored metrics for unregistered services.
    """
    conversation_id = TEST_CONVERSATION_ID

    # Step 1: Create initial conversation stats with multiple services
    stats1 = ConversationStats(
        file_store=mock_file_store, conversation_id=conversation_id
    )

    # Add metrics for multiple services
    service_a = "service-a"
    service_b = "service-b"
    service_c = "service-c"

    metrics_a = Metrics(model_name="gpt-4")
    metrics_a.add_cost(0.10)

    metrics_b = Metrics(model_name="gpt-3.5")
    metrics_b.add_cost(0.05)

    metrics_c = Metrics(model_name="claude-3")
    metrics_c.add_cost(0.08)

    stats1.service_to_metrics[service_a] = metrics_a
    stats1.service_to_metrics[service_b] = metrics_b
    stats1.service_to_metrics[service_c] = metrics_c

    # Save metrics (all three services should be saved)
    stats1.save_metrics()

    # Step 2: Create new conversation stats instance (simulates app restart)
    stats2 = ConversationStats(
        file_store=mock_file_store, conversation_id=conversation_id
    )

    # Verify all metrics were restored
    assert service_a in stats2.restored_metrics
    assert service_b in stats2.restored_metrics
    assert service_c in stats2.restored_metrics
    assert stats2.restored_metrics[service_a].accumulated_cost == 0.10
    assert stats2.restored_metrics[service_b].accumulated_cost == 0.05
    assert stats2.restored_metrics[service_c].accumulated_cost == 0.08

    # Step 3: Register only one LLM service (simulates partial LLM activation)
    with patch("openhands.sdk.llm.llm.litellm_completion"):
        llm_a = LLM(
            service_id=service_a,
            model="gpt-4o",
            api_key=SecretStr("test_key"),
            num_retries=2,
            retry_min_wait=1,
            retry_max_wait=2,
        )
        event_a = RegistryEvent(llm=llm_a, service_id=service_a)
        stats2.register_llm(event_a)

    # Verify service_a was moved from restored_metrics to service_to_metrics
    assert service_a in stats2.service_to_metrics
    assert service_a not in stats2.restored_metrics
    assert stats2.service_to_metrics[service_a].accumulated_cost == 0.10

    # Verify services B and C are still in restored_metrics (not yet registered)
    assert service_b in stats2.restored_metrics
    assert service_c in stats2.restored_metrics
    assert stats2.restored_metrics[service_b].accumulated_cost == 0.05
    assert stats2.restored_metrics[service_c].accumulated_cost == 0.08

    # Step 4: Save metrics again (this is where the bug occurs)
    stats2.save_metrics()

    # Step 5: Create a third conversation stats instance to verify what was saved
    stats3 = ConversationStats(
        file_store=mock_file_store, conversation_id=conversation_id
    )

    # Service A should be restored with its current metrics from service_to_metrics
    assert service_a in stats3.restored_metrics
    assert stats3.restored_metrics[service_a].accumulated_cost == 0.10

    # Services B and C should be preserved from restored_metrics
    assert service_b in stats3.restored_metrics  # FIXED: Now preserved
    assert service_c in stats3.restored_metrics  # FIXED: Now preserved
    assert stats3.restored_metrics[service_b].accumulated_cost == 0.05
    assert stats3.restored_metrics[service_c].accumulated_cost == 0.08


def test_save_metrics_throws_error_on_duplicate_service_ids(mock_file_store):
    """
    Test updated: save_metrics should NOT raise on duplicate service IDs;
    it should prefer service_to_metrics and proceed.
    """
    conversation_id = TEST_CONVERSATION_ID

    stats = ConversationStats(
        file_store=mock_file_store, conversation_id=conversation_id
    )

    # Manually create a scenario with duplicate service IDs
    # (this should never happen in normal operation)
    service_id = "duplicate-service"

    # Add to both restored_metrics and service_to_metrics
    restored_metrics = Metrics(model_name="gpt-4")
    restored_metrics.add_cost(0.10)
    stats.restored_metrics[service_id] = restored_metrics

    service_metrics = Metrics(model_name="gpt-3.5")
    service_metrics.add_cost(0.05)
    stats.service_to_metrics[service_id] = service_metrics

    # Should not raise. Should save with service_to_metrics preferred.
    stats.save_metrics()

    # Verify the saved content prefers service_to_metrics for duplicates
    encoded = mock_file_store.read(stats.metrics_file_name)
    pickled = base64.b64decode(encoded)
    restored = pickle.loads(pickled)

    assert service_id in restored
    assert restored[service_id].accumulated_cost == 0.05  # prefers service_to_metrics
