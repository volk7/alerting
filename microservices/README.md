# Alarm System Microservices Architecture

This directory contains a scalable microservices implementation of the alarm system, designed to handle thousands of simultaneous alarms.

## Architecture Overview

### Services

1. **API Gateway** (`api-gateway/`) - Routes requests to appropriate services
2. **Database Service** (`database-service/`) - Manages alarm CRUD operations
3. **Alarm Scheduler** (`alarm-scheduler/`) - Schedules and triggers alarms
4. **Alarm Processor** (`alarm-processor/`) - Processes triggered alarms
5. **Email Service** (`email-service/`) - Handles email sending
6. **Shared Components** (`shared/`) - Common models and utilities

### Infrastructure

- **PostgreSQL** - Persistent alarm storage
- **Redis** - Message queue and caching
- **Nginx** - Load balancer and reverse proxy

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+

### Running the System

1. **Start all services:**
   ```bash
   docker-compose up -d
   ```

2. **Check service health:**
   ```bash
   curl http://localhost/health
   ```

3. **Add an alarm:**
   ```bash
   curl -X POST http://localhost/alarms/ \
     -H "Content-Type: application/json" \
     -d '{
       "code_id": "TEST_001",
       "email": "test@example.com",
       "time": "14:30:00",
       "is_recurring": false
     }'
   ```

4. **List alarms:**
   ```bash
   curl http://localhost/alarms/
   ```

## Service Details

### API Gateway (Port 8000)
- Routes requests to appropriate microservices
- Provides unified API interface
- Handles service discovery and load balancing

### Database Service (Port 8001)
- Manages alarm CRUD operations
- Handles PostgreSQL connections
- Provides data persistence

### Alarm Scheduler (Port 8002)
- Schedules alarms using Redis
- Publishes alarm events when triggered
- Handles recurring alarms

### Alarm Processor (Port 8003)
- Subscribes to alarm events
- Processes triggered alarms
- Publishes email requests

### Email Service (Port 8004)
- Subscribes to email requests
- Sends emails via SMTP
- Handles email queuing and retries

## Scalability Features

### Horizontal Scaling
- Each service can be scaled independently
- Add more instances: `docker-compose up --scale alarm-processor=3`

### Message Queue
- Redis Pub/Sub for asynchronous communication
- Decouples services for better reliability
- Handles high throughput

### Database Optimization
- Connection pooling
- Efficient queries
- Indexed for performance

### Load Balancing
- Nginx distributes requests
- Health checks ensure availability
- Automatic failover

## Development

### Adding a New Service

1. Create service directory
2. Add Dockerfile and requirements.txt
3. Update docker-compose.yml
4. Implement service logic
5. Add health check endpoint

### Testing

```bash
# Run tests for all services
docker-compose exec api-gateway python -m pytest

# Load test
python test_scalability.py
```

### Monitoring

- Health checks: `http://localhost/health`
- Service status: `http://localhost/debug/services`
- Redis monitoring: `redis-cli -h localhost -p 6379`

## Production Deployment

### Environment Variables
- Set production database credentials
- Configure Redis cluster
- Set up monitoring and logging

### Scaling
- Use Kubernetes for orchestration
- Implement service mesh (Istio)
- Add monitoring (Prometheus/Grafana)

### Security
- Use secrets management
- Implement authentication/authorization
- Enable HTTPS/TLS

## Troubleshooting

### Common Issues

1. **Service not starting:**
   - Check Docker logs: `docker-compose logs <service-name>`
   - Verify environment variables
   - Check port conflicts

2. **Database connection issues:**
   - Verify PostgreSQL is running
   - Check connection string
   - Ensure database exists

3. **Redis connection issues:**
   - Verify Redis is running
   - Check Redis URL
   - Test connectivity

### Debug Commands

```bash
# View all logs
docker-compose logs

# Restart specific service
docker-compose restart <service-name>

# Check service health
curl http://localhost/debug/services

# Access Redis CLI
docker-compose exec redis redis-cli
```

## Performance Tuning

### For High Load

1. **Increase worker processes:**
   - Modify service configurations
   - Scale horizontally

2. **Optimize database:**
   - Add indexes
   - Tune connection pool
   - Use read replicas

3. **Redis optimization:**
   - Configure persistence
   - Tune memory settings
   - Use Redis cluster

4. **Network optimization:**
   - Use gRPC for inter-service communication
   - Implement connection pooling
   - Add circuit breakers 