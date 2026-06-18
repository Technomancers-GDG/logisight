# Solv Frontend - Deployment & Deployment Guide

## Quick Start

### Development

```bash
cd frontend
npm install
npm run dev
```

Visit `http://localhost:5173`

### Production Build

```bash
npm run build
npm run preview
```

Visit `http://localhost:4173` to test the production build locally.

---

## Build Output

After `npm run build`, the `dist/` directory contains:

```
dist/
├── index.html                   (0.93 kB, gzipped 0.45 kB)
├── assets/
│   ├── index-[hash].css         (65.95 kB, gzipped 11.81 kB) - Global styles
│   ├── index-[hash].js          (37.39 kB, gzipped 11.65 kB) - Main app bundle
│   ├── react-vendors-[hash].js  (134.67 kB, gzipped 43.23 kB) - React + ReactDOM
│   ├── views-core-[hash].js     (50.81 kB, gzipped 11.68 kB) - Network, Fleet, etc.
│   └── views-advanced-[hash].js (66.53 kB, gzipped 16.72 kB) - Maps, Analytics, etc.
```

**Total Size**: ~357 kB uncompressed, ~95 kB gzipped

---

## Deployment Options

### Option 1: FastAPI Static Files (Recommended)

**Backend Setup** (main.py or similar):

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Mount frontend dist directory as static files
# This serves all files in dist/ at the root path
app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")

# API routes come before the mount if needed
@app.get("/api/...")
async def api_endpoint():
    ...
```

**Result**: 
- Frontend served at `http://localhost:8000/`
- API available at `http://localhost:8000/api/...`
- WebSocket at `ws://localhost:8000/ws`

### Option 2: Nginx (Production)

**Installation**:
```bash
# Ubuntu/Debian
sudo apt-get install nginx

# macOS
brew install nginx
```

**Configuration** (`/etc/nginx/sites-available/solv`):

```nginx
upstream backend {
    server localhost:8000;
}

server {
    listen 80;
    server_name api.solv.example.com;
    
    # Compression
    gzip on;
    gzip_types text/css application/javascript application/json;
    gzip_min_length 1000;

    # Frontend (SPA)
    location / {
        root /var/www/solv/frontend/dist;
        try_files $uri $uri/ /index.html;
    }

    # Static assets (cache long-term)
    location /assets/ {
        root /var/www/solv/frontend/dist;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api/ {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
    }

    # WebSocket
    location /ws {
        proxy_pass http://backend;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_buffering off;
    }
}
```

**Enable Site**:
```bash
sudo ln -s /etc/nginx/sites-available/solv /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### Option 3: Docker

**Dockerfile**:

```dockerfile
# Build stage
FROM node:18 AS builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Server stage
FROM python:3.11-slim
WORKDIR /app

# Copy built frontend
COPY --from=builder /app/frontend/dist ./frontend/dist

# Copy backend
COPY backend/requirements.txt .
COPY backend/ .

# Install backend dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port
EXPOSE 8000

# Run backend (which serves frontend)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Build & Run**:
```bash
docker build -t solv-app .
docker run -p 8000:8000 solv-app
```

---

## Environment Configuration

### Development (.env.local)

```bash
VITE_API_BASE_URL=http://localhost:8000
VITE_WS_BASE_URL=ws://localhost:8000
VITE_ENVIRONMENT=development
VITE_ENABLE_TESTING=true
```

### Production (.env.production)

```bash
VITE_API_BASE_URL=https://api.solv.example.com
VITE_WS_BASE_URL=wss://api.solv.example.com
VITE_ENVIRONMENT=production
VITE_ENABLE_TESTING=false
VITE_APP_VERSION=1.0.0
```

**Note**: Create `.env.local` or `.env.production` based on `.env.example`

---

## Performance Optimization

### Caching Headers

Set these headers for static assets:

```
# HTML - No cache
Cache-Control: no-cache, no-store, must-revalidate

# CSS & JS with content hash - Long-term cache
Cache-Control: public, max-age=31536000, immutable

# Images - 30 days
Cache-Control: public, max-age=2592000
```

### Compression

Enable gzip compression for:
- `.css` files
- `.js` files
- `.json` responses
- `.html` files

Example (Nginx):
```nginx
gzip on;
gzip_types text/css application/javascript application/json text/html;
gzip_min_length 1024;
gzip_vary on;
```

### Content Delivery Network (CDN)

For production, use a CDN like Cloudflare or AWS CloudFront:

1. Upload `dist/` contents to CDN
2. Configure CDN origin to backend server
3. Point domain to CDN
4. Cache rules:
   - `index.html`: No cache
   - `/assets/*`: Cache 1 year
   - `/api/*`: No cache (proxy to origin)

---

## Testing

### Unit Tests

```bash
npm run test              # Run all tests
npm run test:watch       # Watch mode
npm run test:coverage    # Coverage report
```

### Build Verification

```bash
npm run build            # Build production bundle
npm run preview          # Test locally on port 4173
```

Then visit `http://localhost:4173` and verify:
- [ ] Page loads without errors
- [ ] All tabs accessible
- [ ] WebSocket connection works
- [ ] API calls succeed
- [ ] Language switching works
- [ ] Responsive on mobile (test with DevTools)

---

## Troubleshooting

### WebSocket Connection Fails

**Symptoms**: Error when connecting to WebSocket, simulation doesn't update

**Solutions**:
1. Check backend is running: `http://localhost:8000/api/dashboard`
2. Verify WS_BASE_URL is correct in environment
3. Check browser console for errors (F12 → Console)
4. For reverse proxy (Nginx): Ensure WebSocket upgrade headers are set

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

### API Calls Fail with CORS Error

**Symptoms**: Console shows "CORS policy" error

**Solutions**:
1. Check backend CORS configuration
2. Verify API_BASE_URL matches backend origin
3. For development, the proxy in `vite.config.js` handles CORS

### Bundle Size Too Large

**Symptoms**: Slow page load, large download

**Solutions**:
1. Check code splitting: Run `npm run build` and review chunk sizes
2. Lazy load heavy components (Map, Analytics)
3. Remove unused dependencies: `npm prune`
4. Enable production mode: `NODE_ENV=production npm run build`

### Styles Not Loading

**Symptoms**: Page appears unstyled

**Solutions**:
1. Check CSS file is in dist/assets
2. Verify no inline style errors
3. Clear browser cache (Ctrl+Shift+Delete)
4. Check Content Security Policy (CSP) headers

---

## Security Checklist

- [ ] HTTPS enabled in production
- [ ] CORS properly configured (backend should restrict origins)
- [ ] Content Security Policy (CSP) headers set
- [ ] X-Frame-Options header set (prevent clickjacking)
- [ ] X-Content-Type-Options: nosniff
- [ ] Environment variables not committed to git
- [ ] Dependencies are from trusted sources
- [ ] No sensitive data in frontend code
- [ ] Input validation on all forms
- [ ] API authentication tokens managed securely

---

## Monitoring

### Application Monitoring

Use tools like:
- **Sentry**: Error tracking and performance monitoring
- **Google Analytics**: User behavior tracking
- **New Relic**: Full-stack monitoring

### Health Checks

```bash
# Check if app is running
curl http://localhost:8000/

# Check API health
curl http://localhost:8000/api/dashboard
```

### Logs

Check browser console (F12 → Console):
- Network errors
- JavaScript errors
- WebSocket connection status
- API call results

Server logs:
```bash
# If using systemd
journalctl -u solv-backend -f

# If running directly
# Look for output in terminal
```

---

## Maintenance

### Dependency Updates

```bash
# Check for outdated packages
npm outdated

# Update minor/patch versions
npm update

# Update to latest major version (careful!)
npm install package@latest
```

### Security Updates

```bash
# Check for vulnerabilities
npm audit

# Fix automatically
npm audit fix

# Or manually review and fix critical issues
```

### Backup

Before deploying:
```bash
git tag v1.0.0
git push origin v1.0.0
```

---

## Support

For issues or questions:

1. Check `FRONTEND_IMPLEMENTATION_PLAN.md` for architecture details
2. Check `PHASE_10_IMPLEMENTATION.md` for optimization details
3. Review browser console for error messages
4. Check server logs for API errors
5. Contact the development team

---

## Additional Resources

- **Vite Documentation**: https://vitejs.dev/
- **React Documentation**: https://react.dev/
- **FastAPI Documentation**: https://fastapi.tiangolo.com/
- **WCAG 2.1 Accessibility**: https://www.w3.org/WAI/WCAG21/quickref/
- **HTTP Caching**: https://web.dev/http-cache/

---

## Hackathon Deployment (Render Free Tier + Cron Job)

For hackathon submissions where judges may visit your link at any time, use this zero-budget setup to keep the app awake 24/7.

### Step 1: Push to GitHub

Make sure your repo includes:
- `render.yaml` — Render Blueprint (already in repo root)
- `build.sh` — Build script (already in repo root)
- All source code, Excel data files, and the `data/` directory

```bash
git add render.yaml build.sh
git commit -m "Add Render deployment config"
git push origin main
```

### Step 2: Deploy on Render

1. Go to [render.com](https://render.com) and sign up (free, no credit card required)
2. Click **New +** → **Blueprint**
3. Connect your GitHub repository
4. Render reads `render.yaml` and creates the service automatically
5. Wait for the first deploy to complete (2–3 minutes)
6. Copy your app's URL: `https://solv-hackathon.onrender.com`

**URLs after deploy:**
- Admin Panel: `https://solv-hackathon.onrender.com/`
- Driver App: `https://solv-hackathon.onrender.com/driver`
- API Health: `https://solv-hackathon.onrender.com/api/health`
- Swagger Docs: `https://solv-hackathon.onrender.com/docs`

### Step 3: Keep It Awake with cron-job.org

Render's free tier sleeps after 15 minutes of inactivity. Set up a free cron job to ping it every 10 minutes:

1. Go to [cron-job.org](https://cron-job.org) and create a free account
2. Click **Create cronjob**
3. Fill in:
   - **Title**: Solv Hackathon Uptime
   - **URL**: `https://solv-hackathon.onrender.com/api/health`
   - **Schedule**: Every 10 minutes
4. Save and enable the job

Your app will now stay warm and respond instantly when judges click the link.

### Step 4: Share with Judges

Include these in your submission:
- **Live App**: `https://solv-hackathon.onrender.com`
- **GitHub Repo**: `https://github.com/Technomancers-GDG/solv-v2`
- **API Docs**: `https://solv-hackathon.onrender.com/docs`

### Troubleshooting

| Issue | Solution |
|---|---|
| Build fails on Render | Check Render dashboard logs; usually a missing dependency in `requirements.txt` |
| Frontend shows blank page | Ensure `frontend/dist` and `driver-app-main/dist` were built in `build.sh` |
| API works but UI doesn't | Check browser DevTools → Network for 404s on `/assets/` or `/driver-assets/` |
| App is slow on first load | This is normal if the cron job hasn't pinged it yet; wait 10–15 seconds |
| SQLite data resets | Expected on free tier — `DEMO_MODE=true` auto-seeds data on every restart |

---

**Last Updated**: April 25, 2026  
**Version**: 1.0.0  
**Status**: Production Ready ✅
