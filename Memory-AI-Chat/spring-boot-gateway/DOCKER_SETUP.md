# Docker Setup Guide for Spring Boot Gateway

## 📦 What's Included

This Docker setup includes:
1. **Spring Boot Gateway** (Port 8081)
2. **Python Agent Service** (Port 8000)
3. **NATS Streaming Server** (Port 4222)

All services run in Docker containers and communicate via a Docker network.

## 🚀 Quick Start

### 1. Build and Start All Services

```bash
# Build and start all containers
docker-compose up --build -d

# This will:
# - Build the Spring Boot Gateway from source
# - Pull the Python Agent image (agent_image:new)
# - Pull the NATS image
# - Start all services with proper networking
```

### 2. Check Status

```bash
# View running containers
docker-compose ps

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f spring-gateway
docker-compose logs -f python-agent
docker-compose logs -f nats
```

### 3. Access the Application

Open your browser to:
- **Main UI**: http://localhost:8081
- **Health Check**: http://localhost:8081/chat/health
- **NATS Monitoring**: http://localhost:8222

## 🛠️ Development Commands

### Rebuild After Code Changes

```bash
# Rebuild only the Spring Boot service
docker-compose up --build -d spring-gateway

# Rebuild everything
docker-compose up --build -d
```

### Stop Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes
docker-compose down -v
```

### Restart Services

```bash
# Restart all services
docker-compose restart

# Restart specific service
docker-compose restart spring-gateway
```

### View Logs

```bash
# Follow all logs
docker-compose logs -f

# Last 100 lines from Spring Boot
docker-compose logs --tail=100 spring-gateway

# Real-time logs from Python service
docker-compose logs -f python-agent
```

## 📋 Service Details

### Spring Boot Gateway
- **Container Name**: `spring-boot-gateway`
- **Port**: 8081
- **Profile**: docker (uses application-docker.properties)
- **Python Agent URL**: http://python-agent:8443

### Python Agent Service
- **Container Name**: `python-agent-service`
- **Internal Port**: 8443
- **External Port**: 8000
- **NATS URL**: nats://nats:4222

### NATS Server
- **Container Name**: `nats-streaming`
- **Client Port**: 4222
- **Monitoring Port**: 8222
- **Cluster Port**: 6222

## 🔧 Configuration

### Environment Variables

You can customize services by editing `docker-compose.yml`:

```yaml
services:
  spring-gateway:
    environment:
      - SPRING_PROFILES_ACTIVE=docker
      - PYTHON_AGENT_URL=http://python-agent:8443
      - JAVA_OPTS=-Xmx512m -Xms256m
```

### Application Properties

- **Local Development**: `src/main/resources/application.properties`
- **Docker Deployment**: `src/main/resources/application-docker.properties`

## 🐛 Troubleshooting

### Build Taking Too Long

First build downloads all Maven dependencies (500+ MB). Subsequent builds are faster as dependencies are cached.

```bash
# Check build progress
docker-compose logs -f spring-gateway
```

### Port Already in Use

```bash
# Check what's using the port
lsof -i :8081
lsof -i :8000
lsof -i :4222

# Kill the process or change ports in docker-compose.yml
```

### Service Won't Start

```bash
# Check logs for errors
docker-compose logs spring-gateway

# Check if dependencies are ready
docker-compose ps
```

### Python Service Connection Issues

```bash
# Test Python service directly
curl http://localhost:8000/health

# Check if services can communicate
docker-compose exec spring-gateway ping python-agent
```

### NATS Connection Issues

```bash
# Check NATS status
curl http://localhost:8222/varz

# Test NATS connectivity
docker-compose exec spring-gateway nc -zv nats 4222
```

## 📊 Monitoring

### Health Checks

All services have health checks configured:

```bash
# Check Spring Boot health
curl http://localhost:8081/chat/health

# Check Python service health
curl http://localhost:8000/health

# Check NATS monitoring
curl http://localhost:8222/varz
```

### Container Status

```bash
# View container health status
docker ps

# View resource usage
docker stats

# Inspect specific container
docker inspect spring-boot-gateway
```

## 🔄 Complete Reset

If you need to start fresh:

```bash
# Stop and remove everything
docker-compose down -v

# Remove Spring Boot image
docker rmi spring-boot-gateway_spring-gateway

# Rebuild from scratch
docker-compose up --build -d
```

## 📝 Common Issues

### Issue: "Address already in use"
**Solution**: Another service is using the port. Either stop it or change the port in `docker-compose.yml`

### Issue: "Cannot connect to Python service"
**Solution**: 
1. Check if Python service is running: `docker-compose ps`
2. Check Python logs: `docker-compose logs python-agent`
3. Verify network connectivity: `docker-compose exec spring-gateway ping python-agent`

### Issue: "Build fails with Maven errors"
**Solution**:
1. Clean Maven cache: `docker-compose down && docker-compose up --build --no-cache`
2. Check pom.xml for errors
3. Ensure internet connectivity for Maven downloads

### Issue: "NATS connection refused"
**Solution**:
1. Wait for NATS to fully start (check with `docker-compose ps`)
2. Check NATS logs: `docker-compose logs nats`
3. Verify NATS is listening: `curl http://localhost:8222`

## 🎯 Production Deployment

For production, consider:

1. **Use specific image tags** instead of `latest`:
   ```yaml
   image: nats:2.10-alpine
   ```

2. **Add resource limits**:
   ```yaml
   deploy:
     resources:
       limits:
         cpus: '1.0'
         memory: 512M
   ```

3. **Use Docker secrets** for sensitive data
4. **Enable TLS** for external connections
5. **Add proper logging** and monitoring
6. **Use a reverse proxy** (nginx/traefik) in front

## 📚 Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Spring Boot Docker Guide](https://spring.io/guides/topicals/spring-boot-docker/)
- [NATS Documentation](https://docs.nats.io/)

## 🆘 Getting Help

If you encounter issues:

1. Check logs: `docker-compose logs -f`
2. Verify all services are healthy: `docker-compose ps`
3. Check network connectivity between services
4. Review this troubleshooting guide

## 🎉 Success!

Once all services are running, you should see:

```bash
$ docker-compose ps

NAME                   STATUS          PORTS
nats-streaming         Up (healthy)    0.0.0.0:4222->4222/tcp, ...
python-agent-service   Up (healthy)    0.0.0.0:8000->8443/tcp
spring-boot-gateway    Up (healthy)    0.0.0.0:8081->8081/tcp
```

Now open http://localhost:8081 in your browser and start chatting! 🚀
