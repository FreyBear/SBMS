#!/bin/bash
# Script to properly restart MQTT with the fixes

cd /home/ingve/GitHub/SBMS

echo "Stopping web container..."
docker-compose stop web

echo "Starting web container..."
docker-compose up -d web

echo "Waiting for startup..."
sleep 6

echo ""
echo "Publishing test message..."
mosquitto_pub -h 192.168.1.233 -p 1883 -u MQTT -P hemmelig -t "brewery/keg/weight" -m "8500"

echo ""
echo "Checking logs for connection status..."
docker-compose logs web --tail 20 | grep -E "\[MQTT\]|Connected|Disconnect|acquired MQTT lock"

echo ""
echo "Done. Check your settings page now - it should show 'Connected'"
echo "The fix makes non-MQTT workers check the database cache timestamp"
echo "to determine if MQTT is connected (recent data = connected)"
