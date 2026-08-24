# Iteration 4 - Production Deployment Infrastructure Checklist

**Date:** 2026-08-18 (Post-Security Audit)
**Document Type:** Infrastructure & Operations Guide
**Scope:** Deployment checklist items from security compliance audit

---

## Overview

This document covers the operational/infrastructure items from Iteration 4's Production Deployment Checklist that require infrastructure/operations configuration rather than code changes.

**Progress:** 10/16 items complete (code & configuration)  
**Remaining:** 6/16 items (infrastructure & operations setup)

---

## Complete Checklist

### ✅ Code & Configuration Level (COMPLETE)

- [x] All hardcoded permissions removed (181 replacements)
- [x] Database-driven RBAC fully implemented (380 protected endpoints)
- [x] Secrets vault configured (Azure/AWS/Env backends)
- [x] Rate limiting tested (in-memory & Redis)
- [x] CORS properly configured (specific origins, no wildcard)
- [x] Authentication verified working (JWT, MFA, RBAC)
- [x] Error handling secure (no information leakage)
- [x] Dependencies scanned (no vulnerabilities)
- [x] Audit logging active (comprehensive logging)
- [x] Documentation disabled in production (DEBUG mode gating)

### ⏳ Infrastructure Items (IN PROGRESS)

- [ ] HTTPS configured on production server
- [ ] Admin endpoints IP-whitelisted
- [ ] WAF rules configured
- [ ] Monitoring/alerting activated
- [ ] Incident response plan documented
- [ ] Security training completed

---

## Item 11: HTTPS Configuration on Production Server

### Status: ⏳ REQUIRED FOR DEPLOYMENT

**Responsibility:** DevOps / Infrastructure Team  
**Timeline:** Required before production launch  
**Effort:** 1-2 hours  
**Impact:** CRITICAL - All traffic must be encrypted

### Configuration Options

#### Option A: Let's Encrypt (Recommended - Free)

**Setup:**
```bash
# 1. Install Certbot
sudo apt-get install certbot python3-certbot-nginx

# 2. Obtain certificate (auto-renewal included)
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# 3. Configure Nginx/Apache to use certificate
# Certificate location: /etc/letsencrypt/live/yourdomain.com/

# 4. Enable auto-renewal
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer
```

**Verification:**
```bash
# Check certificate validity
openssl x509 -in /etc/letsencrypt/live/yourdomain.com/fullchain.pem -text -noout

# Test HTTPS endpoint
curl -I https://yourdomain.com

# Should return: HTTP/2 200
```

**Pro Tips:**
- Set up renewal reminder 30 days before expiry
- Test renewal: `sudo certbot renew --dry-run`
- Use HTTP/2 for better performance

#### Option B: Self-Signed (Development Only)

```bash
# Generate self-signed certificate (valid 365 days)
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

⚠️ **WARNING:** Never use in production (browsers will show security warning)

#### Option C: AWS Certificate Manager (For AWS Deployments)

```bash
# Request ACM certificate
aws acm request-certificate \
    --domain-name yourdomain.com \
    --validation-method DNS

# AWS handles renewal automatically
```

### Reverse Proxy Configuration

**Nginx Example:**
```nginx
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name yourdomain.com;
    return 301 https://$server_name$request_uri;
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL/TLS configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Forward to backend
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

**Apache Example:**
```apache
<VirtualHost *:80>
    ServerName yourdomain.com
    Redirect permanent / https://yourdomain.com/
</VirtualHost>

<VirtualHost *:443>
    ServerName yourdomain.com

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/yourdomain.com/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/yourdomain.com/privkey.pem

    ProxyPreserveHost On
    ProxyPass / http://localhost:8000/
</VirtualHost>
```

### Verification Checklist

- [ ] Certificate installed and valid
- [ ] HTTP → HTTPS redirect working (301/302 response)
- [ ] TLS 1.2+ enabled (TLS 1.0/1.1 disabled)
- [ ] Strong cipher suites configured
- [ ] Certificate renewal automated
- [ ] HSTS header configured (recommended)
- [ ] Mixed content warnings resolved

---

## Item 12: Admin Endpoints IP-Whitelisting

### Status: ⏳ REQUIRED FOR PRODUCTION

**Responsibility:** DevOps / Security Team  
**Timeline:** Required before production launch  
**Effort:** 1-2 hours  
**Impact:** HIGH - Restricts admin access to trusted IPs only

### Admin Endpoints to Protect

These endpoints should only be accessible from internal/trusted networks:

```
POST   /admin/users/create-with-roles
GET    /admin/users/*
PUT    /admin/users/*/roles
DELETE /admin/users/*
GET    /admin/roles/*
POST   /admin/roles/create
PUT    /admin/roles/*/permissions
GET    /admin/permissions/*
POST   /admin/audit-logs
GET    /admin/system-config
PUT    /admin/system-config
```

### Implementation Options

#### Option A: Nginx IP Whitelisting

```nginx
# In nginx.conf or site config

# Whitelist trusted IPs
geo $admin_access {
    default 0;
    192.168.1.0/24 1;        # Internal network
    203.0.113.45 1;          # Admin office IP
    2001:db8::1 1;           # IPv6 admin
}

server {
    listen 443 ssl;
    server_name yourdomain.com;

    # Admin routes
    location ~ ^/admin/ {
        # Check whitelist
        if ($admin_access = 0) {
            return 403 "Access denied. Admin access restricted to authorized IPs.";
        }
        
        proxy_pass http://localhost:8000;
    }

    # All other routes
    location / {
        proxy_pass http://localhost:8000;
    }
}
```

#### Option B: AWS Security Groups (For AWS Deployments)

```bash
# Create security group for admin access
aws ec2 create-security-group \
    --group-name admin-access \
    --description "Admin endpoints access control"

# Allow admin access only from specific IPs
aws ec2 authorize-security-group-ingress \
    --group-id sg-12345678 \
    --protocol tcp \
    --port 443 \
    --cidr 203.0.113.45/32 \
    --description "Admin office IP"

aws ec2 authorize-security-group-ingress \
    --group-id sg-12345678 \
    --protocol tcp \
    --port 443 \
    --cidr 192.168.1.0/24 \
    --description "Internal network"
```

#### Option C: Application-Level Middleware

**File:** `app/middleware/admin_access.py`

```python
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

class AdminAccessMiddleware(BaseHTTPMiddleware):
    """Restrict admin endpoints to whitelisted IPs."""

    ADMIN_PATHS = ["/admin/", "/api/v1/admin/"]
    WHITELIST = [
        "192.168.1.0/24",      # Internal network
        "203.0.113.45",        # Admin office
        "::1",                 # IPv6 localhost
    ]

    async def dispatch(self, request: Request, call_next):
        # Check if admin endpoint
        if any(request.url.path.startswith(path) for path in self.ADMIN_PATHS):
            client_ip = request.client.host if request.client else None
            
            if not self._is_whitelisted(client_ip):
                raise HTTPException(
                    status_code=403,
                    detail="Admin access restricted to authorized IPs"
                )
        
        return await call_next(request)

    @staticmethod
    def _is_whitelisted(client_ip: str) -> bool:
        """Check if IP is in whitelist."""
        from ipaddress import ip_address, ip_network
        
        try:
            ip = ip_address(client_ip)
            for network in AdminAccessMiddleware.WHITELIST:
                if "/" in network:
                    if ip in ip_network(network, strict=False):
                        return True
                elif ip_address(client_ip) == ip_address(network):
                    return True
        except ValueError:
            pass
        
        return False
```

**Register in app/main.py:**
```python
from app.middleware.admin_access import AdminAccessMiddleware

app.add_middleware(AdminAccessMiddleware)
```

### Whitelist Configuration

**Add to .env.production:**
```env
# Admin access whitelist (comma-separated IPs/CIDR ranges)
ADMIN_WHITELIST="192.168.1.0/24,203.0.113.45,203.0.113.46"
```

### Verification Checklist

- [ ] Admin endpoints identified and documented
- [ ] IP whitelist configured (internal + admin office)
- [ ] VPN/proxy IPs added to whitelist
- [ ] Non-whitelisted IPs return 403
- [ ] Whitelisted IPs access admin endpoints normally
- [ ] IPv4 and IPv6 addresses both work
- [ ] CIDR ranges properly validated

---

## Item 13: WAF Rules Configuration

### Status: ⏳ RECOMMENDED FOR PRODUCTION

**Responsibility:** Security / DevOps Team  
**Timeline:** Recommended before production launch  
**Effort:** 2-4 hours  
**Impact:** MEDIUM-HIGH - Additional protection against common attacks

### WAF Options

#### Option A: AWS WAF (For AWS Deployments)

```bash
# Create Web ACL
aws wafv2 create-web-acl \
    --name MyWebAcl \
    --region us-east-1 \
    --scope REGIONAL \
    --default-action Block={}

# Add common rule groups
aws wafv2 create-rule-group \
    --name AWSManagedRulesCommonRuleSet \
    --region us-east-1 \
    --scope REGIONAL

# Apply to ALB/CloudFront
aws wafv2 associate-web-acl \
    --web-acl-arn arn:aws:wafv2:... \
    --resource-arn arn:aws:elasticloadbalancing:... \
    --region us-east-1
```

#### Option B: Cloudflare WAF (For Any Provider)

1. Update DNS to point to Cloudflare
2. Enable WAF in Cloudflare dashboard
3. Configure rules:
   - SQL Injection protection
   - XSS protection
   - Bot management
   - Rate limiting

#### Option C: ModSecurity (Self-Hosted)

```bash
# Install ModSecurity
sudo apt-get install libmodsecurity3 libmodsecurity-dev
sudo apt-get install modsecurity-apache2

# Enable in Apache
sudo a2enmod security2

# Configure OWASP ModSecurity Core Rule Set
sudo apt-get install modsecurity-ruleset-owasp

# Restart Apache
sudo systemctl restart apache2
```

### Recommended Rules

```
✅ SQL Injection Protection
✅ Cross-Site Scripting (XSS) Protection
✅ Cross-Site Request Forgery (CSRF) Protection
✅ Local File Inclusion (LFI) Protection
✅ Remote File Inclusion (RFI) Protection
✅ PHP Injection Protection
✅ Path Traversal Protection
✅ Scanner/Probe Detection
✅ Protocol Attack Protection
✅ HTTP Protocol Violation
```

### Verification Checklist

- [ ] WAF solution selected and configured
- [ ] OWASP Top 10 rules enabled
- [ ] SQL injection protection active
- [ ] XSS protection active
- [ ] Rate limiting rules configured
- [ ] False positive testing completed
- [ ] Logging and monitoring configured

---

## Item 14: Monitoring & Alerting Activation

### Status: ⏳ REQUIRED FOR PRODUCTION

**Responsibility:** DevOps / Operations Team  
**Timeline:** Required before production launch  
**Effort:** 2-3 hours  
**Impact:** CRITICAL - Essential for production support

### Monitoring Solution Options

#### Option A: Prometheus + Grafana (Open Source)

```bash
# Install Prometheus
docker run -d -p 9090:9090 \
    -v prometheus.yml:/etc/prometheus/prometheus.yml \
    prom/prometheus

# Install Grafana
docker run -d -p 3000:3000 grafana/grafana
```

**Prometheus config (prometheus.yml):**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'backend'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
```

**Grafana dashboards to create:**
- Request rate (req/s)
- Response time (p50, p95, p99)
- Error rate (5xx, 4xx)
- Database connection pool status
- Rate limit hits
- Authentication failures
- Active user sessions

#### Option B: AWS CloudWatch (For AWS Deployments)

```bash
# Install CloudWatch agent
wget https://s3.amazonaws.com/amazoncloudwatch-agent/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb

# Configure and start
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
    -a fetch-config \
    -m ec2 \
    -s \
    -c file:/opt/aws/amazon-cloudwatch-agent/etc/config.json
```

#### Option C: Datadog (Enterprise SaaS)

```python
# Add to app/main.py
from datadog import initialize, api
from datadog.api.monitor import Monitor

# Initialize Datadog
options = {
    'api_key': os.getenv('DATADOG_API_KEY'),
    'app_key': os.getenv('DATADOG_APP_KEY')
}
initialize(**options)
```

### Key Metrics to Monitor

```
**Application Metrics:**
- Request rate (requests/second)
- Response time (latency percentiles: p50, p95, p99)
- Error rate (5xx errors per minute)
- Rate limit hits (429 responses per minute)
- Authentication failures (401 responses)
- Authorization failures (403 responses)

**System Metrics:**
- CPU usage (%)
- Memory usage (%)
- Disk usage (%)
- Network I/O (Mbps)
- Database connection pool (used/available)

**Business Metrics:**
- Active users
- API key usage
- Feature utilization
- Error budget tracking
```

### Alert Configuration

**High Priority (Page on-call):**
```
- Error rate > 5% for 5 minutes
- Response time (p99) > 5 seconds
- Database connection pool > 80%
- Disk usage > 90%
- Any 500 errors
```

**Medium Priority (Email/Slack):**
```
- Error rate > 1% for 10 minutes
- Response time (p95) > 2 seconds
- Rate limit threshold > 80%
- Certificate expiry < 7 days
```

**Low Priority (Dashboard only):**
```
- Request rate anomalies
- Unusual geographic patterns
- Deprecated API endpoint usage
```

### Verification Checklist

- [ ] Monitoring solution deployed
- [ ] Metrics collection active (check dashboard)
- [ ] Alerting rules configured
- [ ] Alert channels configured (PagerDuty/Slack/Email)
- [ ] Dashboards created for key metrics
- [ ] Alert testing completed (verify notifications)
- [ ] On-call rotation established

---

## Item 15: Incident Response Plan Documentation

### Status: ⏳ RECOMMENDED FOR PRODUCTION

**Responsibility:** Security / Operations Team  
**Timeline:** Recommended before production launch  
**Effort:** 2-3 hours  
**Impact:** HIGH - Enables rapid response to security incidents

### Incident Response Plan Outline

**File:** Create `INCIDENT_RESPONSE_PLAN.md`

```markdown
# Incident Response Plan

## 1. Detection & Alerting
- Who monitors alerts? (24/7 coverage)
- Alert escalation procedure
- When to wake up on-call lead

## 2. Assessment
- Initial impact assessment (data breach, availability, performance)
- Severity classification (Critical/High/Medium/Low)
- Stakeholder notification

## 3. Response Procedures

### Security Breach
1. Isolate affected systems
2. Preserve evidence (logs, dumps)
3. Assess data exposure scope
4. Notify affected users (within X hours)
5. Contact authorities if required

### DDoS Attack
1. Engage WAF/rate limiting
2. Scale infrastructure (auto-scaling)
3. Contact CDN provider (if applicable)
4. Monitor attack patterns
5. Document for post-incident review

### Data Corruption
1. Stop write operations
2. Restore from backup to staging
3. Verify data integrity
4. Gradual rollout of recovered data
5. Root cause analysis

## 4. Communication
- Internal communication channel (Slack, Teams)
- External communication template (status page, email)
- Customer notification timing

## 5. Recovery & Restoration
- Rollback procedures
- Data restoration procedures
- Verification steps

## 6. Post-Incident Review
- Timeline reconstruction
- Root cause analysis
- Preventive measures
- Process improvements
```

### Create Runbooks for Common Incidents

**Example: Authentication System Down**
```
1. Check if authentication service is running
2. Check database connectivity
3. Check secrets manager access
4. Review recent deployments
5. Check error logs for details
6. If recent deploy: rollback previous version
7. If database issue: restore from backup
8. If secrets manager down: use .env fallback
9. Monitor for recurrence
10. Document root cause
```

### Verification Checklist

- [ ] Incident response plan created
- [ ] Runbooks created for top 5 incident types
- [ ] Escalation contacts documented
- [ ] Communication templates prepared
- [ ] Recovery procedures tested
- [ ] Team trained on procedures
- [ ] Plan reviewed quarterly

---

## Item 16: Security Training Completion

### Status: ⏳ RECOMMENDED FOR PRODUCTION

**Responsibility:** Security / HR Team  
**Timeline:** Recommended before production launch  
**Effort:** 4-8 hours per person  
**Impact:** MEDIUM - Ensures team understands security practices

### Training Topics

**For All Team Members:**
1. OWASP Top 10 (2-hour video)
2. Secure coding practices (2-hour workshop)
3. Password security (1-hour)
4. Phishing awareness (1-hour)
5. Incident response procedures (1-hour)

**For Backend Developers:**
1. SQL injection prevention (2-hour)
2. Authentication & authorization (2-hour)
3. API security (1-hour)
4. Secrets management (1-hour)
5. Logging & monitoring (1-hour)

**For DevOps/Infrastructure:**
1. Network security (2-hour)
2. Container security (2-hour)
3. Infrastructure hardening (2-hour)
4. Incident response (1-hour)
5. Compliance & auditing (1-hour)

**For QA/Testing:**
1. Security testing (2-hour)
2. Penetration testing basics (2-hour)
3. OWASP testing guide (1-hour)

### Training Resources

**Free:**
- OWASP Top 10: https://owasp.org/Top10/
- Google Cloud Security: https://cloud.google.com/security
- Microsoft Azure Security: https://docs.microsoft.com/en-us/azure/security/
- Linux Academy Security: https://www.linuxacademy.com/

**Paid (but comprehensive):**
- SANS Institute courses
- Udemy Security courses
- Pluralsight Security paths
- Coursera Security Specializations

### Verification Checklist

- [ ] Training plan created
- [ ] Training materials selected
- [ ] Training schedule set
- [ ] All team members complete baseline training
- [ ] Specialized training for roles
- [ ] Quizzes/assessments passed
- [ ] Annual refresher training scheduled
- [ ] Training records maintained

---

## Summary: Deployment Readiness Status

| Item # | Requirement | Status | Owner | ETA |
|--------|-------------|--------|-------|-----|
| 1-10 | Code & Config Level | ✅ COMPLETE | Dev Team | Done |
| 11 | HTTPS Configuration | ⏳ IN PROGRESS | DevOps | Week 1 |
| 12 | IP Whitelisting | ⏳ IN PROGRESS | Security | Week 1 |
| 13 | WAF Configuration | ⏳ IN PROGRESS | Security | Week 1 |
| 14 | Monitoring/Alerting | ⏳ IN PROGRESS | DevOps | Week 1 |
| 15 | Incident Response Plan | ⏳ TODO | Security | Week 1 |
| 16 | Security Training | ⏳ TODO | HR/Security | Week 2 |

**Total Deployment Readiness: 63% (10/16 items complete)**

**Ready for Production: Week 2-3** (after infrastructure items complete)

---

## Deployment Day Checklist

### Day Before
- [ ] All infrastructure items complete and tested
- [ ] Backups verified
- [ ] Rollback procedures tested
- [ ] Communication plan reviewed
- [ ] On-call team briefed

### Deployment Day
- [ ] HTTPS certificates installed
- [ ] Admin IP whitelist configured
- [ ] WAF rules enabled
- [ ] Monitoring dashboards active
- [ ] Load balancer configured
- [ ] Database replicas synced
- [ ] Rate limiting tested
- [ ] Error handling verified
- [ ] Security checks passed

### Post-Deployment
- [ ] Smoke tests passed
- [ ] Monitoring alerts flowing
- [ ] Error rate nominal
- [ ] Response times acceptable
- [ ] All endpoints responding
- [ ] User access verified
- [ ] Incident response team standing by

---

## References & Resources

**Documentation:**
- `SECURITY_COMPLIANCE_ITERATION4_VERIFICATION.md` - Security audit findings
- `ITERATION4_MULTI_WORKER_FIXES.md` - Code-level fixes
- `VPS_DEPLOYMENT.md` - Production deployment guide

**External Resources:**
- Let's Encrypt: https://letsencrypt.org/
- OWASP Top 10: https://owasp.org/Top10/
- NIST Security Framework: https://www.nist.gov/cyberframework/
- AWS Well-Architected Security Pillar: https://docs.aws.amazon.com/wellarchitected/latest/security-pillar/

---

**Status:** ✅ READY FOR INFRASTRUCTURE TEAM  
**Next Step:** Assign infrastructure items to respective teams
