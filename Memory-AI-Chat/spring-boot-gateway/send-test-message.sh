#!/bin/bash

echo "📤 Sending Test Message to Agent"
echo "================================="
echo ""

# Default values
USER_ID=${1:-"test_user"}
CHAT_ID=${2:-"test_chat_$(date +%s)"}
MESSAGE=${3:-"What is 2+2?"}

echo "User ID: $USER_ID"
echo "Chat ID: $CHAT_ID"
echo "Message: $MESSAGE"
echo ""
echo "Sending to Python Agent at http://localhost:8000/chat..."
echo ""

# Send the message
response=$(curl -s -X POST http://localhost:8000/chat \
  -H 'Content-Type: application/json' \
  -d "{
    \"user_id\": \"$USER_ID\",
    \"chat_id\": \"$CHAT_ID\",
    \"message\": \"$MESSAGE\"
  }")

echo "Response:"
echo "$response" | jq '.' 2>/dev/null || echo "$response"
echo ""
echo "✅ Message sent! Check the NATS subscriber terminal to see streaming updates."
echo ""
echo "Usage: ./send-test-message.sh [user_id] [chat_id] [message]"
echo "Example: ./send-test-message.sh user1 chat1 'Tell me a joke'"
