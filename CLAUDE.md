# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a scalable alarm/alert system with two deployment architectures:
1. **Monolithic Flask app** (`app.py`) - Development/testing with dashboard UI
2. **Microservices architecture** (`microservices/`) - Production-ready scalable system

## Development Commands

### Running the System

**Microservices (Recommended for Development):**
```bash
cd microservices
docker-compose up -d
```

**Monolithic Flask App:**
```bash
python app.py
```

### Testing and Performance

**Load/Performance Testing:**
```bash
python scalability_test.py          # Comprehensive scalability test
python quick_scalability_test.py    # Quick performance check
python stress_test.py               # Stress testing
python test_scalability.py          # Microservices load test
```

**Database Testing:**
```bash
python test_db_connection.py        # Test database connectivity
python check_db.py                  # Check database status
python check_postgres.py            # PostgreSQL-specific checks
```

### Database Operations

**Migration:**
```bash
python run_migration.py             # Full migration with validation
python run_simple_migration.py      # Simple migration
```

**Cleanup:**
```bash
python clear_scheduler.py           # Clear scheduler data
```

## Architecture

### Microservices Components

- **API Gateway** (`:8000`) - Routes requests, unified API interface
- **Database Service** (`:8001`) - Alarm CRUD operations with PostgreSQL
- **Alarm Scheduler** (`:8002`) - Time-indexed scheduling with O(1) lookup
- **Alarm Processor** (`:8003`) - Processes triggered alarms
- **Email Service** (`:8004`) - SMTP email handling
- **Nginx** (`:80`) - Load balancer and reverse proxy

### Key Technologies

- **Database**: PostgreSQL with connection pooling
- **Message Queue**: Redis Pub/Sub for inter-service communication
- **Framework**: FastAPI for microservices, Flask for dashboard
- **Containerization**: Docker with Docker Compose

### Time-Indexed Scheduler

The core innovation is the `TimeIndexedAlarmScheduler` that uses a time-based index structure:
```
{hour: {minute: {second: Set[alarm_id]}}}
```
This provides O(1) alarm lookup vs O(n) in traditional implementations, enabling handling of 1M+ simultaneous alarms.

## Database Schema

**Main alarms table:**
- `code_id` (TEXT, PRIMARY KEY)
- `email` (TEXT, NOT NULL)  
- `time` (TIME, NOT NULL)
- `is_recurring` (BOOLEAN, DEFAULT false)

**Code descriptions table:**
- `code_id` (TEXT, PRIMARY KEY)
- `description` (TEXT, NOT NULL)

Key indexes exist on `time`, `email`, and composite fields for performance.

## Configuration

### Environment Variables

```bash
DATABASE_URL=postgresql://admin:ZZ4charlie@postgres:5432/alarms_db
REDIS_URL=redis://redis:6379
MAX_DB_CONNECTIONS=20
MIN_DB_CONNECTIONS=5
TIMEZONE=America/Los_Angeles  # Converted to UTC internally
```

### Service Endpoints

- Dashboard UI: `http://localhost:5000` (Flask app)
- API Gateway: `http://localhost/` (via Nginx)
- Direct services: `http://localhost:800X` (X = service number)

## Performance Characteristics

- **Capacity**: 1M+ simultaneous alarms in scalable mode
- **Response Time**: <10ms for alarm operations
- **Memory**: ~2GB for 1M alarms
- **Throughput**: 1000+ alarms/second

## Important Files

- `microservices/SCALABILITY_README.md` - Detailed performance documentation
- `microservices/README.md` - Microservices setup and operations
- `TIMEZONE_MIGRATION.md` - Timezone handling documentation
- `custom_migration.sql` - Database migration scripts