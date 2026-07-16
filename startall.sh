#!/bin/bash
cd /home/z/my-project

# Start z-ai bridge
pkill -f "bun.*zai-bridge" 2>/dev/null; sleep 1
setsid bun run mini-services/zai-bridge/index.ts </dev/null >/tmp/zai-bridge.log 2>&1 &

# Start Python server
pkill -f "python3 server" 2>/dev/null; sleep 1
setsid python3 server.py </dev/null >server.log 2>&1 &

# Start Next.js
pkill -f "next dev" 2>/dev/null; sleep 1
setsid npx next dev -p 3000 </dev/null >dev.log 2>&1 &

# Keepalive loop
while true; do
  curl -s -o /dev/null http://localhost:3001/health 2>/dev/null || { setsid bun run mini-services/zai-bridge/index.ts </dev/null >>/tmp/zai-bridge.log 2>&1 & sleep 2; }
  curl -s -o /dev/null http://localhost:8000/api/health 2>/dev/null || { setsid python3 server.py </dev/null >>server.log 2>&1 & sleep 3; }
  curl -s -o /dev/null http://localhost:3000/ 2>/dev/null || { setsid npx next dev -p 3000 </dev/null >>dev.log 2>&1 & sleep 10; }
  sleep 10
done
