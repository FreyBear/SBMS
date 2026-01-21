#!/bin/bash
# Monitor MQTT connection stability for 60 seconds

echo "=========================================="
echo "MQTT Connection Stability Monitor"
echo "Duration: 60 seconds"
echo "Started: $(date)"
echo "=========================================="
echo ""

# Start log monitoring in background
docker-compose -f /home/ingve/GitHub/SBMS/docker-compose.yml logs -f --tail=0 web 2>&1 | \
    grep --line-buffered -E "acquired MQTT lock|_on_connect|_on_disconnect|stopping MQTT|released MQTT lock|Worker exiting" | \
    while IFS= read -r line; do
        echo "[$(date '+%H:%M:%S')] $line"
    done &

MONITOR_PID=$!

# Let it run for 60 seconds
sleep 60

# Stop monitoring
kill $MONITOR_PID 2>/dev/null

echo ""
echo "=========================================="
echo "Test Complete: $(date)"
echo "=========================================="
echo ""
echo "Summary for last 60 seconds:"
echo "----------------------------"

cd /home/ingve/GitHub/SBMS
echo -n "MQTT lock acquisitions: "
docker-compose logs web --since 65s 2>&1 | grep -c "acquired MQTT lock"

echo -n "Connection events: "
docker-compose logs web --since 65s 2>&1 | grep -c "_on_connect"

echo -n "Disconnection events: "
docker-compose logs web --since 65s 2>&1 | grep -c "_on_disconnect"

echo -n "MQTT stop events: "
docker-compose logs web --since 65s 2>&1 | grep -c "stopping MQTT"

echo -n "Worker exits: "
docker-compose logs web --since 65s 2>&1 | grep -c "Worker exiting"

echo ""
echo "Current MQTT weight data:"
docker exec sbms_db psql -U sbms_user -d sbms -c "SELECT weight_kg, timestamp FROM mqtt_live_weight;" 2>/dev/null

echo ""
echo "If you see multiple 'acquired MQTT lock' or '_on_disconnect' events,"
echo "that indicates connection instability."
