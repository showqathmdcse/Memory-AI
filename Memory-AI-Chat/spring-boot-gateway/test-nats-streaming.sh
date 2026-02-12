#!/bin/bash

echo "🎯 NATS Live Streaming Test"
echo "============================"
echo ""
echo "This will show real-time messages streaming from the agent!"
echo ""
echo "Instructions:"
echo "1. Keep this terminal open to see NATS messages"
echo "2. Open another terminal and run:"
echo "   curl -X POST http://localhost:8000/chat \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"user_id\":\"user1\",\"chat_id\":\"chat1\",\"message\":\"What is 2+2?\"}'"
echo ""
echo "You'll see messages appear here in real-time!"
echo ""
echo "Press Ctrl+C to stop..."
echo ""
echo "--- Subscribing to all agent messages ---"
echo ""

# Subscribe to all agent messages
docker run --rm -it --network host natsio/nats-box:latest nats sub 'agent.messages.>'
