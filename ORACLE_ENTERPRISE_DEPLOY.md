# 🚀 Auto-Broker Enterprise Deploy - Oracle Cloud Free Tier

**Production-Grade Deployment on 4GB RAM / 1 CPU ARM Ampere A1**

> Zero-Waste Architecture - Every MB Optimized Like Big Tech (Google/Netflix Style)

---

## 📊 Resource Allocation Strategy

| Service | RAM Limit | CPU | Purpose |
|---------|-----------|-----|---------|
| **nginx** | 64MB | 0.25 | Reverse proxy + static assets |
| **postgres** | 1.2GB | 0.5 | Tuned for ARM + SSD |
| **redis** | 256MB | 0.1 | Cache & sessions |
| **api** | 768MB | 0.75 | FastAPI + uvicorn workers |
| **ollama** | 1.5GB* | 0.5 | Local AI (disabled by default) |
| **system** | ~300MB | - | OS overhead |
| **free** | ~1.4GB | - | Buffer for spikes |

*Ollama disabled by default - use Hume AI Cloud to save RAM

---

## ⚡ Quick Start (One-Command Deploy)

```bash
# 1. Clone repository
git clone https://github.com/giuaaaan/auto-broker.git
cd auto-broker

# 2. Configure environment
cp .env.oracle.example .env.oracle
nano .env.oracle  # Edit with your API keys

# 3. Deploy everything
chmod +x scripts/deploy-oracle-enterprise.sh
./scripts/deploy-oracle-enterprise.sh

# 4. Access your deployment
echo "http://$(curl -s ifconfig.me)"
```

---

## 📋 Prerequisites

### Oracle Cloud Setup

1. **Create Free Tier Account**: [cloud.oracle.com](https://cloud.oracle.com)
2. **Create VM Instance**:
   - Shape: VM.Standard.A1.Flex (ARM)
   - OCPUs: 1
   - Memory: 4GB
   - Boot Volume: 50GB (default)
   - Image: Oracle Linux 8 or Ubuntu 22.04
3. **Open Security List**:
   - Ingress: TCP 22 (SSH)
   - Ingress: TCP 80 (HTTP)
   - Ingress: TCP 443 (HTTPS)

### Install Dependencies

```bash
# Oracle Linux 8
sudo dnf update -y
sudo dnf install -y docker docker-compose git curl
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker

# Ubuntu 22.04
sudo apt update && sudo apt upgrade -y
sudo apt install -y docker.io docker-compose git curl
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
newgrp docker
```

---

## 🔧 Configuration

### Required Environment Variables

Edit `.env.oracle`:

```bash
# AI Services (Get keys from dashboard)
HUME_API_KEY=your_key_here
HUME_SECRET_KEY=your_secret_here
INSIGHTO_API_KEY=your_key_here

# Security (Generate: openssl rand -hex 32)
JWT_SECRET=your_32_char_secret_minimum

# Database (Change default password!)
DB_PASSWORD=secure_random_password_32_chars
```

### Getting API Keys

| Service | URL | Purpose |
|---------|-----|---------|
| **Hume AI** | [dev.hume.ai](https://dev.hume.ai) | Emotional Intelligence |
| **Insighto** | [insighto.ai](https://insighto.ai) | Carrier Analytics |

---

## 🚀 Deployment Commands

### Standard Deploy (Recommended)
```bash
./scripts/deploy-oracle-enterprise.sh
```

### With System Prune (Clean deploy)
```bash
PRUNE=true ./scripts/deploy-oracle-enterprise.sh
```

### Deploy with Local AI (Ollama)
```bash
# Requires 1.5GB additional RAM
OLLAMA_ENABLED=true ./scripts/deploy-oracle-enterprise.sh
docker-compose -f docker-compose.oracle.enterprise.yml --profile local-ai up -d ollama
```

### Manual Docker Compose
```bash
# Build and start
docker-compose -f docker-compose.oracle.enterprise.yml up -d --build

# View logs
docker-compose -f docker-compose.oracle.enterprise.yml logs -f

# Scale API workers (if needed)
docker-compose -f docker-compose.oracle.enterprise.yml up -d --scale api=2
```

---

## 🔍 Health Checks & Monitoring

### Service Health

```bash
# Overall health
curl http://localhost/health

# API health
curl http://localhost:8000/health

# Database health
docker-compose -f docker-compose.oracle.enterprise.yml exec postgres pg_isready -U autobroker

# Redis health
docker-compose -f docker-compose.oracle.enterprise.yml exec redis redis-cli ping
```

### Resource Monitoring

```bash
# Live resource usage
docker stats --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}"

# System resources
free -h
df -h
top

# Container logs
docker-compose -f docker-compose.oracle.enterprise.yml logs -f api
docker-compose -f docker-compose.oracle.enterprise.yml logs -f --tail=100 postgres
```

### Database Queries

```bash
# Connect to PostgreSQL
docker-compose -f docker-compose.oracle.enterprise.yml exec postgres psql -U autobroker

# Useful queries
\dt                          # List tables
SELECT count(*) FROM users;  # Count users
SELECT * FROM pg_stat_activity;  # Active connections
```

---

## 🛠️ Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose -f docker-compose.oracle.enterprise.yml logs <service>

# Restart service
docker-compose -f docker-compose.oracle.enterprise.yml restart <service>

# Full reset
docker-compose -f docker-compose.oracle.enterprise.yml down -v
docker-compose -f docker-compose.oracle.enterprise.yml up -d
```

### RAM Exhausted (OOM)

**Symptoms**: Containers killed, "Out of memory" errors

**Solutions**:

1. **Disable Ollama** (saves 1.5GB):
   ```bash
   docker-compose -f docker-compose.oracle.enterprise.yml stop ollama
   ```

2. **Reduce PostgreSQL buffers**:
   ```bash
   # Edit config/postgresql.oracle.conf
   shared_buffers = 128MB  # Instead of 256MB
   ```

3. **Reduce API workers**:
   ```bash
   # In docker-compose, change:
   UVICORN_WORKERS=1  # Instead of 2
   ```

4. **Add swap** (emergency only):
   ```bash
   sudo fallocate -l 2G /swapfile
   sudo chmod 600 /swapfile
   sudo mkswap /swapfile
   sudo swapon /swapfile
   ```

### Database Connection Issues

```bash
# Reset database (WARNING: data loss)
docker-compose -f docker-compose.oracle.enterprise.yml down -v
docker volume rm autobroker_postgres_data
./scripts/deploy-oracle-enterprise.sh

# Check connection pool
# In .env.oracle:
DATABASE_POOL_SIZE=3  # Reduce from 5
```

### API Slow Response

```bash
# Check worker utilization
docker-compose -f docker-compose.oracle.enterprise.yml top api

# Increase workers (if RAM available)
UVICORN_WORKERS=3

# Enable query logging in postgres
log_min_duration_statement = 500  # Log queries >500ms
```

### SSL/HTTPS Setup

```bash
# Install certbot
sudo dnf install -y certbot  # Oracle Linux
sudo apt install -y certbot   # Ubuntu

# Get certificate
sudo certbot certonly --standalone -d your-domain.com

# Copy to nginx
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem nginx/ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem nginx/ssl/

# Uncomment HTTPS section in nginx/oracle-nginx.conf
# Reload nginx
docker-compose -f docker-compose.oracle.enterprise.yml exec nginx nginx -s reload
```

---

## 💾 Backup & Recovery

### Automated Backup

```bash
# Run backup
./scripts/backup-oracle.sh

# Scheduled backup (cron)
0 2 * * * /path/to/auto-broker/scripts/backup-oracle.sh >> /var/log/autobroker-backup.log 2>&1
```

### Restore from Backup

```bash
# Stop services
docker-compose -f docker-compose.oracle.enterprise.yml stop api

# Restore database
gunzip < backups/autobroker_db_YYYYMMDD_HHMMSS.sql.gz | \
  docker-compose -f docker-compose.oracle.enterprise.yml exec -T postgres psql -U autobroker

# Restart services
docker-compose -f docker-compose.oracle.enterprise.yml start api
```

---

## 📈 Scaling Path to Hetzner

When ready to scale beyond Oracle Free Tier:

### Hetzner CPX11 (€5.35/month)
- **2 vCPUs** AMD EPYC
- **2GB RAM** → Scale down services proportionally
- **40GB NVMe SSD**

### Hetzner CPX21 (€8.92/month) ⭐ Recommended
- **4 vCPUs** AMD EPYC
- **8GB RAM** → Double current allocation
- **80GB NVMe SSD**
- **3.3x faster** than Oracle Free Tier

### Migration Steps

1. **Backup on Oracle**:
   ```bash
   ./scripts/backup-oracle.sh
   scp backups/* root@new-server:/backups/
   ```

2. **Deploy on Hetzner**:
   ```bash
   # Same deploy script works on any Docker host
   ./scripts/deploy-oracle-enterprise.sh
   ```

3. **Update allocations** in docker-compose:
   ```yaml
   postgres:
     deploy:
       resources:
         limits:
           memory: 2G  # Instead of 1.2G
   
   api:
     deploy:
       resources:
         limits:
           memory: 1.5G  # Instead of 768M
   ```

---

## 🔐 Security Checklist

- [ ] Change default passwords
- [ ] Use strong JWT secret (32+ chars)
- [ ] Enable firewall (UFW/firewalld)
- [ ] Configure SSL/HTTPS
- [ ] Regular backups
- [ ] Update containers regularly
- [ ] Monitor logs for anomalies

### Firewall Setup

```bash
# Oracle Linux
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload

# Ubuntu
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

---

## 📚 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Oracle Cloud VM                         │
│                   4GB RAM / 1 CPU ARM                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │  Nginx   │────│   API    │────│ Postgres │              │
│  │  64MB    │    │  768MB   │    │  1.2GB   │              │
│  │ Reverse  │    │ FastAPI  │    │ Tuned    │              │
│  │ Proxy    │    │ 2 Workers│    │ 20 conn  │              │
│  └──────────┘    └────┬─────┘    └──────────┘              │
│                       │                                     │
│                       ▼                                     │
│                  ┌──────────┐                              │
│                  │  Redis   │                              │
│                  │  256MB   │                              │
│                  │  LRU     │                              │
│                  └──────────┘                              │
│                                                             │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ Dashboard│    │  Hume AI │    │ Insighto │              │
│  │  React   │    │  Cloud   │    │   AI     │              │
│  │  Static  │    │ Emotion  │    │ Carrier  │              │
│  └──────────┘    └──────────┘    └──────────┘              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 🆘 Support

- **Issues**: [GitHub Issues](https://github.com/giuaaaan/auto-broker/issues)
- **Documentation**: [README.md](README.md)
- **API Docs**: `http://your-server/api/docs`

---

## 📝 Changelog

### v1.5.0 - Enterprise Deploy
- ✅ Multi-stage Docker builds
- ✅ PostgreSQL tuning for 4GB RAM
- ✅ Oracle Cloud optimizations
- ✅ Automated backup scripts
- ✅ Health checks & monitoring
- ✅ Zero-Waste architecture

---

**Built with ❤️ for the freight forwarding revolution**
