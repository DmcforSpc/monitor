# Docker 部署

## 单容器

```bash
docker build -t cve-monitor .
docker run -d --name cve-monitor \
    -p 8000:8000 \
    -v cve-data:/data \
    -e CVE_DATABASE_URL=sqlite:////data/cve_monitor.db \
    --env-file .env \
    cve-monitor
```

## docker compose（推荐）

```bash
docker compose up -d
docker compose logs -f
docker compose down
```

`docker-compose.yml` 已配置：
- 持久化 volume `cve-data` 挂到 `/data`，DB 保存其中
- 健康检查（命中 `/api/health` 30s 一次）
- 自动从 `.env` 读环境变量（可选）

## 镜像特性

- **多阶段构建** — builder 装依赖，runtime 只拷 venv + 源码
- **uv 0.11 锁定** — `uv.lock` 保证可重现，构建快
- **非 root 用户** — `app:app` 系统账号运行
- **HEALTHCHECK** — 内置 30s 间隔的 `/api/health` 探测
- **基础镜像** — `python:3.11-slim`（Debian 12 bookworm slim）
- **字节码预编译** — `UV_COMPILE_BYTECODE=1`，冷启动更快

## 镜像大小参考

```bash
docker images cve-monitor
# REPOSITORY    TAG       SIZE
# cve-monitor   latest    ~150 MB
```

## 推送到 registry

```bash
docker tag cve-monitor:latest ghcr.io/dmcforspc/cve-monitor:1.0.0
docker push ghcr.io/dmcforspc/cve-monitor:1.0.0
```

## Kubernetes 简易示范

```yaml title="deployment.yaml"
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cve-monitor
spec:
  replicas: 1                    # SQLite 锁限制；切 Postgres 后可水平扩
  selector:
    matchLabels: { app: cve-monitor }
  template:
    metadata:
      labels: { app: cve-monitor }
    spec:
      containers:
        - name: app
          image: ghcr.io/dmcforspc/cve-monitor:1.0.0
          ports:
            - containerPort: 8000
          env:
            - { name: CVE_DATABASE_URL, value: "postgresql+psycopg://..." }
          envFrom:
            - secretRef: { name: cve-monitor-secrets }
          livenessProbe:
            httpGet: { path: /api/health, port: 8000 }
            periodSeconds: 30
          readinessProbe:
            httpGet: { path: /api/ready, port: 8000 }
            periodSeconds: 10
          resources:
            requests: { cpu: 100m, memory: 128Mi }
            limits:   { cpu: 500m, memory: 512Mi }
```

## Nginx 反向代理 + TLS

```nginx
server {
    listen 443 ssl http2;
    server_name cve.example.com;

    ssl_certificate     /etc/letsencrypt/live/cve.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cve.example.com/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

容器内同步设置 `CVE_ALLOWED_HOSTS=cve.example.com,127.0.0.1` 拒绝直接 IP 访问。
