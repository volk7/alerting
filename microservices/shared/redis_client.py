import redis
import json
import os
from typing import Optional, Dict, Any
from .models import AlarmEvent, EmailRequest
import logging

logger = logging.getLogger(__name__)

class RedisClient:
    def __init__(self):
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        try:
            self.redis = redis.from_url(redis_url, decode_responses=True)
            logger.info(f"Redis client initialized with URL: {redis_url}")
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            raise
        
    def publish_alarm_event(self, event: AlarmEvent) -> bool:
        """Publish alarm trigger event to Redis"""
        try:
            channel = "alarm_events"
            message = event.json()
            result = self.redis.publish(channel, message)
            logger.info(f"Published alarm event to Redis: {result} subscribers")
            return True
        except Exception as e:
            logger.error(f"Error publishing alarm event: {e}")
            return False
           
    def publish_email_request(self, email_req: EmailRequest) -> bool:
        """Publish email request to Redis"""
        try:
            channel = "email_requests"
            message = email_req.json()
            self.redis.publish(channel, message)
            return True
        except Exception as e:
            print(f"Error publishing email request: {e}")
            return False
    
    def subscribe_to_alarm_events(self, callback):
        """Subscribe to alarm events"""
        pubsub = self.redis.pubsub()
        pubsub.subscribe("alarm_events")
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    event_data = json.loads(message['data'])
                    event = AlarmEvent(**event_data)
                    callback(event)
                except Exception as e:
                    print(f"Error processing alarm event: {e}")
    
    def subscribe_to_email_requests(self, callback):
        """Subscribe to email requests"""
        pubsub = self.redis.pubsub()
        pubsub.subscribe("email_requests")
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    email_data = json.loads(message['data'])
                    email_req = EmailRequest(**email_data)
                    callback(email_req)
                except Exception as e:
                    print(f"Error processing email request: {e}")
    
    def set_alarm_schedule(self, alarm_id: str, schedule_data: Dict[str, Any]) -> bool:
        """Store alarm schedule in Redis"""
        try:
            key = f"alarm_schedule:{alarm_id}"
            self.redis.setex(key, 86400, json.dumps(schedule_data))  # 24 hour expiry
            return True
        except Exception as e:
            print(f"Error setting alarm schedule: {e}")
            return False
    
    def get_alarm_schedule(self, alarm_id: str) -> Optional[Dict[str, Any]]:
        """Get alarm schedule from Redis"""
        try:
            key = f"alarm_schedule:{alarm_id}"
            data = self.redis.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            print(f"Error getting alarm schedule: {e}")
            return None 