# main.py
import logging
import os
import signal
import sys
import time
import pika

# Create logger instance (not root logger)
logger = logging.getLogger(__name__)

def setup_logging():
    """Configure logging with proper formatting"""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    
    # Handler for stdout (Kubernetes captures this)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Structured format for easy parsing
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    # Configure logger
    logger.setLevel(log_level)
    logger.addHandler(handler)
    
    # Reduce pika noise
    logging.getLogger('pika').setLevel(logging.WARNING)

def process_message(body):
    """Process message - add your logic here"""
    logger.info(f"Processing message: {body.decode()}")
    # will change to 300 for long processing
    time.sleep(300)
    logger.info("Processing complete")

def callback(ch, method, properties, body):
    """Message callback with error handling"""
    logger.info("Received message from queue")
    
    try:
        process_message(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        logger.info("Message acknowledged")
    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
        logger.warning("Message requeued for retry")
    finally:
        ch.stop_consuming()

def main():
    setup_logging()
    
    admin = os.environ.get("ADMIN")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    host = os.environ.get("LAVINMQ_HOST", "localhost")
    port = int(os.environ.get("LAVINMQ_PORT", "5672"))
    queue_name = os.environ.get("QUEUE_NAME", "hello")
    
    if not admin or not admin_password:
        logger.error("LAVINMQ_USER and LAVINMQ_PASSWORD must be set")
        sys.exit(1)
    
    logger.info(f"Connecting to LavinMQ at {host}:{port}")
    
    credentials = pika.PlainCredentials(admin, admin_password)
    parameters = pika.ConnectionParameters(
        host=host,
        port=port,
        credentials=credentials,
        heartbeat=600,
        blocked_connection_timeout=300,
    )

    shutdown_requested = False

    def handle_shutdown(signum, _frame):
        nonlocal shutdown_requested
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        shutdown_requested = True
        channel.stop_consuming()

    signal.signal(signal.SIGTERM, handle_shutdown)
    signal.signal(signal.SIGINT, handle_shutdown)
    
    try:
        connection = pika.BlockingConnection(parameters)
        channel = connection.channel()
        
        # Declare queue (idempotent)
        channel.queue_declare(queue=queue_name, durable=True)
        channel.basic_qos(prefetch_count=1)
        
        channel.basic_consume(
            queue=queue_name,
            on_message_callback=callback,
            auto_ack=False
        )
        
        logger.info(f"Listening on queue '{queue_name}'. Press CTRL+C to exit")
        channel.start_consuming()
        
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        if 'channel' in locals():
            channel.stop_consuming()
        if 'connection' in locals():
            connection.close()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        if 'connection' in locals() and connection.is_open:
            connection.close()
        logger.info('Shutdown complete')
        sys.exit(0)

if __name__ == "__main__":
    main()