#!/bin/bash

echo "🎯 NATS Streaming Test"
echo "====================="
echo ""
echo "Starting NATS subscriber..."
echo "You should see real-time messages as they stream!"
echo ""

# Subscribe to all agent messages
docker run --rm -it --network host natsio/nats-box:latest nats sub 'agent.messages.>'
