# Gunicorn configuration for SBMS production deployment
import multiprocessing

# Server socket
bind = "0.0.0.0:5000"
backlog = 2048

# Worker processes
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
worker_connections = 1000
timeout = 30
keepalive = 2

# Restart workers after this many requests (prevents memory leaks)
# Increased to reduce MQTT reconnection frequency
max_requests = 10000
max_requests_jitter = 500

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
access_log_format = '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'

# Process naming
proc_name = "sbms_gunicorn"

# Server mechanics
preload_app = False  # Changed to False to avoid shared MQTT client across workers
daemon = False
pidfile = "/tmp/gunicorn.pid"
user = None
group = None
tmp_upload_dir = None

# SSL (handled by reverse proxy, so disabled here)
keyfile = None
certfile = None

# Worker hooks to ensure only one worker handles MQTT
def post_fork(server, worker):
    """Called after a worker has been forked"""
    import os
    import fcntl
    
    lock_file = '/tmp/sbms_mqtt_worker.lock'
    
    try:
        # Try to acquire exclusive lock
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        
        # Got the lock - this worker handles MQTT
        # Store the fd in the worker object so we can access it in worker_exit
        worker.mqtt_lock_fd = fd
        
        # Write our PID to the file
        os.ftruncate(fd, 0)
        os.write(fd, str(worker.pid).encode())
        
        from app import start_mqtt_if_enabled
        print(f"✓ Worker {worker.pid} acquired MQTT lock and starting...")
        start_mqtt_if_enabled()
        
        # Don't close fd - keep the lock for the lifetime of this worker
        
    except IOError:
        # Another worker already has the lock
        worker.mqtt_lock_fd = None
        print(f"ℹ️  Worker {worker.pid} - MQTT handled by another worker")

def worker_exit(server, worker):
    """Called when a worker is about to exit"""
    import os
    import fcntl
    
    # Check if this worker had the MQTT lock
    if hasattr(worker, 'mqtt_lock_fd') and worker.mqtt_lock_fd is not None:
        try:
            # Stop MQTT before releasing lock
            from app import stop_mqtt
            print(f"🛑 Worker {worker.pid} stopping MQTT before exit...")
            stop_mqtt()
            
            # Release the lock
            fcntl.flock(worker.mqtt_lock_fd, fcntl.LOCK_UN)
            os.close(worker.mqtt_lock_fd)
            print(f"✓ Worker {worker.pid} released MQTT lock")
        except Exception as e:
            print(f"⚠️  Error releasing MQTT lock: {e}")
