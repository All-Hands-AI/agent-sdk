This example demonstrates the OpenHands Webhook protocol.

* A test server is started on port 8001 which simply logs webhook events
* An Agent Server is started on port 8000 and configured using the
  openhands_agent_server_config.json to pass events back to the test server