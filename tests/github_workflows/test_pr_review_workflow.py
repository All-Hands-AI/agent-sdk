"""Tests for the PR review workflow to ensure it handles forks correctly."""

from pathlib import Path

import yaml


def test_pr_review_workflow_handles_forks():
    """Test that the PR review workflow correctly handles forks."""
    workflow_path = (
        Path(__file__).parent.parent.parent
        / ".github"
        / "workflows"
        / "pr-review-by-openhands.yml"
    )

    assert workflow_path.exists(), f"Workflow file not found: {workflow_path}"

    with open(workflow_path) as f:
        workflow = yaml.safe_load(f)

    # Find the checkout PR repository step
    checkout_step = None
    for step in workflow["jobs"]["pr-review"]["steps"]:
        if step.get("name") == "Checkout PR repository":
            checkout_step = step
            break

    assert checkout_step is not None, "Checkout PR repository step not found"

    # Verify that the step includes the repository parameter for handling forks
    checkout_with = checkout_step.get("with", {})
    assert "repository" in checkout_with, (
        "Repository parameter missing from checkout step"
    )
    assert (
        checkout_with["repository"]
        == "${{ github.event.pull_request.head.repo.full_name }}"
    ), "Repository parameter should use head.repo.full_name for fork support"

    # Verify that ref is still present
    assert "ref" in checkout_with, "Ref parameter missing from checkout step"
    assert checkout_with["ref"] == "${{ github.event.pull_request.head.ref }}", (
        "Ref parameter should use head.ref"
    )


def test_example_workflow_handles_forks():
    """Test that the example workflow template correctly handles forks."""
    workflow_path = (
        Path(__file__).parent.parent.parent
        / "examples"
        / "03_github_workflows"
        / "02_pr_review"
        / "workflow.yml"
    )

    assert workflow_path.exists(), f"Example workflow file not found: {workflow_path}"

    with open(workflow_path) as f:
        workflow = yaml.safe_load(f)

    # Find the checkout PR repository step
    checkout_step = None
    for step in workflow["jobs"]["pr-review"]["steps"]:
        if step.get("name") == "Checkout PR repository":
            checkout_step = step
            break

    assert checkout_step is not None, "Checkout PR repository step not found"

    # Verify that the step includes the repository parameter for handling forks
    checkout_with = checkout_step.get("with", {})
    assert "repository" in checkout_with, (
        "Repository parameter missing from checkout step"
    )
    assert (
        checkout_with["repository"]
        == "${{ github.event.pull_request.head.repo.full_name }}"
    ), "Repository parameter should use head.repo.full_name for fork support"

    # Verify that ref is still present
    assert "ref" in checkout_with, "Ref parameter missing from checkout step"
    assert checkout_with["ref"] == "${{ github.event.pull_request.head.ref }}", (
        "Ref parameter should use head.ref"
    )


def test_workflow_yaml_syntax():
    """Test that both workflow files have valid YAML syntax."""
    workflow_files = [
        Path(__file__).parent.parent.parent
        / ".github"
        / "workflows"
        / "pr-review-by-openhands.yml",
        Path(__file__).parent.parent.parent
        / "examples"
        / "03_github_workflows"
        / "02_pr_review"
        / "workflow.yml",
    ]

    for workflow_path in workflow_files:
        assert workflow_path.exists(), f"Workflow file not found: {workflow_path}"

        with open(workflow_path) as f:
            try:
                yaml.safe_load(f)
            except yaml.YAMLError as e:
                assert False, f"Invalid YAML syntax in {workflow_path}: {e}"
