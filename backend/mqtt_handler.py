"""
MQTT Handler for Weight Sensor Integration
Handles connection to MQTT broker and processes weight updates from keg sensors
"""

import json
import threading
import time
import logging
from datetime import datetime
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTHandler:
    """Handles MQTT connection and message processing for keg weight sensors"""
    
    def __init__(self, db_connection_func, config=None):
        """
        Initialize MQTT handler
        
        Args:
            db_connection_func: Function to get database connection
            config: MQTT configuration dict (broker_host, broker_port, etc.)
        """
        self.db_connection_func = db_connection_func
        self.config = config or {}
        self.client = None
        self.connected = False
        self.thread = None
        self.should_run = False
        self.lock = threading.Lock()
        
        # Generate a unique, persistent client ID
        import uuid
        self.client_id = f"sbms_{uuid.uuid4().hex[:8]}"
        
        # Store latest weight (in-memory cache for the MQTT worker)
        self.latest_weight = None  # {'weight_kg': float, 'timestamp': str}
        
        logger.info(f"MQTT Handler initialized with client ID: {self.client_id}")
    
    def update_config(self, config):
        """Update MQTT configuration and reconnect if needed"""
        with self.lock:
            old_enabled = self.config.get('enabled', False)
            new_enabled = config.get('enabled', False)
            
            self.config = config
            
            # If already running, restart
            if self.should_run:
                logger.info("Config updated, reconnecting...")
                self.stop()
                time.sleep(1)
                if new_enabled:
                    self.start()
            # If not running but now enabled, start it
            elif new_enabled and not old_enabled:
                logger.info("MQTT enabled, starting...")
                self.start()
            # If was enabled but now disabled, stop it
            elif old_enabled and not new_enabled:
                logger.info("MQTT disabled, stopping...")
                self.stop()
    
    def start(self):
        """Start MQTT client in background thread"""
        try:
            if not self.config.get('enabled', False):
                logger.info("MQTT is disabled in configuration")
                return False
            
            if self.should_run:
                if self.thread and self.thread.is_alive():
                    logger.info("MQTT client already running")
                    return True  # Return True since it's actually running
                else:
                    # Thread died, reset flag
                    self.should_run = False
            
            self.should_run = True
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()
            logger.info("MQTT client thread started")
            return True
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def stop(self):
        """Stop MQTT client gracefully"""
        logger.info("Stopping MQTT client...")
        self.should_run = False
        
        # Clear weight cache from memory
        with self.lock:
            self.latest_weight = None
        
        # Clear weight and connection status from database immediately
        self._clear_weight_from_db()
        
        if self.client:
            try:
                self.client.loop_stop()
                self.client.disconnect()
            except Exception as e:
                logger.error(f"Error stopping MQTT client: {e}")
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        
        self.connected = False
        logger.info("MQTT client stopped")
    
    def _run(self):
        """Main MQTT client loop (runs in background thread)"""
        # Single connection - let Paho handle reconnections automatically
        try:
            self._connect_and_loop()
        except Exception as e:
            logger.error(f"MQTT fatal error: {e}")
            import traceback
            traceback.print_exc()
    
    def _connect_and_loop(self):
        """Connect to broker and start message loop"""
        broker_host = self.config.get('broker_host')
        broker_port = self.config.get('broker_port', 1883)
        username = self.config.get('username')
        password = self.config.get('password')
        use_tls = self.config.get('use_tls', False)
        
        if not broker_host:
            logger.error("No broker host configured")
            self.should_run = False
            return
        
        # Create MQTT client with persistent ID
        self.client = mqtt.Client(client_id=self.client_id)
        
        # Enable automatic reconnection with exponential backoff
        self.client.reconnect_delay_set(min_delay=1, max_delay=60)
        
        # Set callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        
        # Set authentication if provided
        if username:
            self.client.username_pw_set(username, password)
        
        # Enable TLS if configured
        if use_tls:
            self.client.tls_set()
        
        # Connect to broker
        logger.info(f"Connecting to MQTT broker {broker_host}:{broker_port} (ID: {self.client_id})")
        try:
            self.client.connect(broker_host, broker_port, keepalive=60)
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return
        
        # Start network loop in background (non-blocking, handles reconnections)
        self.client.loop_start()
        logger.info("🔄 MQTT network loop started (Paho background thread)")
        
        # Keep thread alive while should_run is True
        connection_logged = False
        heartbeat_counter = 0
        while self.should_run:
            if self.connected and not connection_logged:
                logger.info(f"✅ MQTT fully connected and ready")
                connection_logged = True
            elif not self.connected and connection_logged:
                logger.warning(f"⚠️ MQTT connection lost")
                connection_logged = False
            
            # Send heartbeat to database every 30 seconds to maintain connection status
            heartbeat_counter += 1
            if self.connected and heartbeat_counter >= 30:
                self._update_connection_status(True)
                heartbeat_counter = 0
            
            time.sleep(1)
        
        # Clean shutdown
        logger.info("🛑 MQTT loop ending, stopping network loop...")
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker"""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            
            # Update connection status in database for cross-worker visibility
            self._update_connection_status(True)
            
            # Subscribe to weight topic after connection
            topic_prefix = self.config.get('topic_prefix', 'brewery')
            topic = f"{topic_prefix}/keg/weight"
            result, mid = client.subscribe(topic)
            logger.info(f"Subscribed to topic: {topic}")
            if result != 0:
                logger.error(f"Subscription failed with code: {result}")
        else:
            self.connected = False
            error_messages = {
                1: "Incorrect protocol version",
                2: "Invalid client identifier",
                3: "Server unavailable",
                4: "Bad username or password",
                5: "Not authorized"
            }
            logger.error(f"Connection failed: {error_messages.get(rc, f'Unknown error {rc}')}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker"""
        self.connected = False
        self._update_connection_status(False)
        if rc != 0:
            logger.warning(f"Disconnected unexpectedly (code {rc}), auto-reconnecting...")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        """Callback when message received"""
        try:
            # Parse message payload - expect plain number (grams)
            try:
                payload_str = msg.payload.decode('utf-8').strip()
                # Replace comma with dot for European decimal format
                payload_str = payload_str.replace(',', '.')
                weight_grams = float(payload_str)
            except ValueError as e:
                logger.warning(f"Invalid payload on {msg.topic}: {msg.payload}")
                return
            
            # Convert grams to kg and round to 0.1 kg precision
            weight_kg = round(weight_grams / 1000.0, 1)
            
            # Store in memory cache for Plato button
            timestamp = datetime.now().isoformat()
            with self.lock:
                self.latest_weight = {
                    'weight_kg': weight_kg,
                    'timestamp': timestamp
                }
            
            logger.info(f"Weight received: {weight_kg} kg")
            
            # Save to database for cross-worker access
            self._save_weight_to_db(weight_kg, timestamp)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def _save_weight_to_db(self, weight_kg, timestamp):
        """Save weight to database as cache for other workers"""
        try:
            conn = self.db_connection_func()
            if not conn:
                logger.error("Failed to get database connection")
                return
            
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO mqtt_live_weight (id, weight_kg, timestamp, updated_at)
                    VALUES (TRUE, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (id) DO UPDATE
                    SET weight_kg = EXCLUDED.weight_kg,
                        timestamp = EXCLUDED.timestamp,
                        updated_at = CURRENT_TIMESTAMP
                """, (weight_kg, timestamp))
                conn.commit()
        except Exception as e:
            logger.error(f"DB cache update failed: {e}")
        finally:
            if conn:
                conn.close()
    
    def _clear_weight_from_db(self):
        """Clear weight from database when MQTT stops"""
        try:
            conn = self.db_connection_func()
            if not conn:
                return
            
            with conn.cursor() as cur:
                cur.execute("DELETE FROM mqtt_live_weight")
                conn.commit()
                logger.info("Cleared weight cache from database")
        except Exception as e:
            logger.debug(f"DB cache clear failed (non-critical): {e}")
        finally:
            if conn:
                conn.close()
    
    def _update_connection_status(self, is_connected):
        """Update connection status in database for cross-worker visibility"""
        try:
            conn = self.db_connection_func()
            if not conn:
                return
            
            with conn.cursor() as cur:
                if is_connected:
                    # Create or update entry with current timestamp
                    cur.execute("""
                        INSERT INTO mqtt_live_weight (id, weight_kg, timestamp, updated_at)
                        VALUES (TRUE, 0.0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (id) DO UPDATE
                        SET updated_at = CURRENT_TIMESTAMP
                    """)
                else:
                    # Delete entry when disconnected
                    cur.execute("DELETE FROM mqtt_live_weight")
                conn.commit()
        except Exception as e:
            logger.debug(f"Connection status update failed (non-critical): {e}")
        finally:
            if conn:
                conn.close()
    
    def get_latest_weight(self):
        """Get latest weight (from DB cache for cross-worker access)"""
        # Try database first (works for all workers)
        try:
            conn = self.db_connection_func()
            if conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT weight_kg, timestamp FROM mqtt_live_weight LIMIT 1")
                    result = cur.fetchone()
                    conn.close()
                    
                    if result:
                        return {
                            'weight_kg': result[0],
                            'timestamp': result[1]
                        }
        except Exception:
            pass
        
        # Fallback to memory (only works for MQTT worker)
        with self.lock:
            return self.latest_weight
    
    def is_connected(self):
        """Check if MQTT client is connected - check database for cross-worker consistency"""
        # Always check latest config from database for enabled status
        try:
            conn = self.db_connection_func()
            if conn:
                with conn.cursor() as cur:
                    # Check if MQTT is enabled in database
                    cur.execute("SELECT enabled FROM mqtt_config LIMIT 1")
                    result = cur.fetchone()
                    if not result or not result[0]:
                        conn.close()
                        return False  # MQTT is disabled
                    
                    # Connection is active if database was updated within last 90 seconds
                    cur.execute("""
                        SELECT EXISTS(
                            SELECT 1 FROM mqtt_live_weight 
                            WHERE updated_at > (NOW() - INTERVAL '90 seconds')
                        )
                    """)
                    result = cur.fetchone()
                    conn.close()
                    return bool(result and result[0])
        except Exception as e:
            logger.debug(f"is_connected DB check failed: {e}")
            # Fallback: if we're the MQTT worker, use our direct knowledge
            if self.thread and self.thread.is_alive():
                return self.connected and self.config.get('enabled', False)
        
        return False
    
    @staticmethod
    def test_connection(broker_host, broker_port, username=None, password=None, use_tls=False, timeout=10):
        """
        Test MQTT connection without subscribing
        Returns (success: bool, message: str)
        """
        try:
            test_client = mqtt.Client(client_id=f"sbms_test_{int(time.time())}")
            
            # Track connection result
            connection_result = {'success': False, 'message': ''}
            
            def on_connect(client, userdata, flags, rc):
                if rc == 0:
                    connection_result['success'] = True
                    connection_result['message'] = 'Connection successful'
                    client.disconnect()
                else:
                    error_messages = {
                        1: "Incorrect protocol version",
                        2: "Invalid client identifier",
                        3: "Server unavailable",
                        4: "Bad username or password",
                        5: "Not authorized"
                    }
                    connection_result['message'] = error_messages.get(rc, f'Unknown error {rc}')
            
            test_client.on_connect = on_connect
            
            if username:
                test_client.username_pw_set(username, password)
            
            if use_tls:
                test_client.tls_set()
            
            # Connect with timeout
            test_client.connect(broker_host, broker_port, keepalive=60)
            test_client.loop_start()
            
            # Wait for connection
            start_time = time.time()
            while time.time() - start_time < timeout:
                if connection_result['success'] or connection_result['message']:
                    break
                time.sleep(0.1)
            
            test_client.loop_stop()
            test_client.disconnect()
            
            if not connection_result['message']:
                return False, f"Connection timeout after {timeout} seconds"
            
            return connection_result['success'], connection_result['message']
            
        except Exception as e:
            return False, f"Connection failed: {str(e)}"
