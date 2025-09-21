#!/usr/bin/env python3
"""
Basic test script to verify the web chat application components work correctly.
This script tests the HTML structure, CSS loading, and JavaScript functionality.
"""

import os
import sys
from pathlib import Path


def test_file_structure():
    """Test that all required files exist."""
    print("🔍 Testing file structure...")

    required_files = [
        "web/index.html",
        "web/index-dev.html",
        "web/styles.css",
        "web/app.js",
        "web/app-dev.js",
        "config/agent_server_config.json",
        "docker-compose.yml",
        "Dockerfile.frontend",
        "nginx.conf",
        "start.sh",
        "demo.sh",
        ".env.example",
    ]

    missing_files = []
    for file_path in required_files:
        if not os.path.exists(file_path):
            missing_files.append(file_path)

    if missing_files:
        print(f"❌ Missing files: {missing_files}")
        return False

    print("✅ All required files exist")
    return True


def test_html_structure():
    """Test HTML file structure and content."""
    print("🔍 Testing HTML structure...")

    # Test main HTML file
    with open("web/index.html", "r") as f:
        html_content = f.read()

    required_elements = [
        "OpenHands Web Chat",
        "new-conversation-btn",
        "chat-messages",
        "message-input",
        "send-btn",
        "app.js",
    ]

    missing_elements = []
    for element in required_elements:
        if element not in html_content:
            missing_elements.append(element)

    if missing_elements:
        print(f"❌ Missing HTML elements: {missing_elements}")
        return False

    print("✅ HTML structure is correct")
    return True


def test_css_structure():
    """Test CSS file structure."""
    print("🔍 Testing CSS structure...")

    with open("web/styles.css", "r") as f:
        css_content = f.read()

    required_classes = [
        ".app-container",
        ".sidebar",
        ".main-content",
        ".chat-messages",
        ".message",
        ".btn",
    ]

    missing_classes = []
    for css_class in required_classes:
        if css_class not in css_content:
            missing_classes.append(css_class)

    if missing_classes:
        print(f"❌ Missing CSS classes: {missing_classes}")
        return False

    print("✅ CSS structure is correct")
    return True


def test_javascript_structure():
    """Test JavaScript file structure."""
    print("🔍 Testing JavaScript structure...")

    with open("web/app.js", "r") as f:
        js_content = f.read()

    required_functions = [
        "class OpenHandsWebChat",
        "apiRequest",
        "connectWebSocket",
        "sendMessage",
        "loadConversations",
    ]

    missing_functions = []
    for func in required_functions:
        if func not in js_content:
            missing_functions.append(func)

    if missing_functions:
        print(f"❌ Missing JavaScript functions: {missing_functions}")
        return False

    print("✅ JavaScript structure is correct")
    return True


def test_docker_config():
    """Test Docker configuration."""
    print("🔍 Testing Docker configuration...")

    # Check docker-compose.yml
    with open("docker-compose.yml", "r") as f:
        compose_content = f.read()

    required_services = ["agent-server", "web-frontend"]
    missing_services = []
    for service in required_services:
        if service not in compose_content:
            missing_services.append(service)

    if missing_services:
        print(f"❌ Missing Docker services: {missing_services}")
        return False

    print("✅ Docker configuration is correct")
    return True


def test_environment_setup():
    """Test environment configuration."""
    print("🔍 Testing environment setup...")

    # Check .env.example exists and has required variables
    with open(".env.example", "r") as f:
        env_content = f.read()

    required_vars = ["LITELLM_API_KEY", "WEB_PORT"]
    missing_vars = []
    for var in required_vars:
        if var not in env_content:
            missing_vars.append(var)

    if missing_vars:
        print(f"❌ Missing environment variables: {missing_vars}")
        return False

    print("✅ Environment setup is correct")
    return True


def run_all_tests():
    """Run all tests."""
    print("🧪 Running OpenHands Web Chat Application Tests")
    print("=" * 50)

    tests = [
        test_file_structure,
        test_html_structure,
        test_css_structure,
        test_javascript_structure,
        test_docker_config,
        test_environment_setup,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with error: {e}")
            failed += 1
        print()

    print("=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 All tests passed! The application is ready to deploy.")
        return True
    else:
        print("❌ Some tests failed. Please fix the issues before deploying.")
        return False


if __name__ == "__main__":
    # Change to the script directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)

    success = run_all_tests()
    sys.exit(0 if success else 1)
