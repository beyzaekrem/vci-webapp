#!/bin/bash

echo "Starting system, please wait..."

# 1. Start Capture Server
echo "[1/3] Starting vci-capture server (SIMULATED mode)..."
cd /home/student_polat/Desktop/vci-webapp-master/vci-capture-main
source venv/bin/activate
python src/sparrow/server.py --sim &
CAPTURE_PID=$!
sleep 2

# 2. Start Automation API Server
echo "[2/3] Starting vci-automation API server..."
cd /home/student_polat/Desktop/vci-webapp-master/vci-automation-main
source venv/bin/activate
python scripts/web_service/api_server.py &
AUTO_PID=$!
sleep 2

# 3. Start Web Application
echo "[3/3] Starting Web application..."
cd /home/student_polat/Desktop/vci-webapp-master
npm run dev &
WEBAPP_PID=$!

echo ""
echo "=================================================="
echo "✅ Entire system successfully started!"
echo "🌐 Open in your browser: http://localhost:3000"
echo "🛑 Press CTRL+C to stop all servers and exit."
echo "=================================================="

# Trap to cleanly shut down everything when CTRL+C is pressed
trap "echo -e '\nShutting down...'; kill $CAPTURE_PID $AUTO_PID $WEBAPP_PID 2>/dev/null; exit" SIGINT SIGTERM EXIT
wait
