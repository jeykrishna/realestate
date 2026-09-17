# HTTPS Setup for PlotBook API

The backend currently serves plain HTTP on `13.53.169.16:8000`. Let's Encrypt
(and AWS ACM public certs) **cannot** be issued for a bare IP — you need a
domain name. Once you have one, follow these steps to get real TLS.

## Prerequisites
- A domain/subdomain for the API, e.g. `api.plotbook.in`.
- A **DNS A record** for that name pointing at `13.53.169.16`.
  Verify it has propagated: `dig +short api.plotbook.in` → `13.53.169.16`.

## 1. Open port 443 in the EC2 security group
The security group `sg-075576e36103ccd99` currently opens 22/80/8000. Add 443:

```bash
aws ec2 authorize-security-group-ingress \
  --region eu-north-1 \
  --group-id sg-075576e36103ccd99 \
  --protocol tcp --port 443 --cidr 0.0.0.0/0
```

(Optional hardening: once nginx fronts the app, restrict 8000 so the API is
only reachable via nginx, not directly:
`aws ec2 revoke-security-group-ingress --group-id sg-075576e36103ccd99 --protocol tcp --port 8000 --cidr 0.0.0.0/0`)

## 2. Install nginx + certbot on the EC2 box
```bash
sudo apt update
sudo apt install -y nginx certbot python3-certbot-nginx
```

## 3. Install the reverse-proxy config
Copy `nginx-plotbook.conf` from this folder to the server, edit `server_name`
to your real domain, then enable it:

```bash
scp -i ~/.ssh/ec2-temp-key deploy/nginx-plotbook.conf \
  ubuntu@13.53.169.16:/tmp/plotbook.conf
# on the server:
sudo mv /tmp/plotbook.conf /etc/nginx/sites-available/plotbook
sudo sed -i 's/api.example.com/api.plotbook.in/' /etc/nginx/sites-available/plotbook
sudo ln -sf /etc/nginx/sites-available/plotbook /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

## 4. Obtain the certificate
certbot will fetch the cert and rewrite the nginx config to add the
`listen 443 ssl` block and a HTTP→HTTPS redirect automatically:

```bash
sudo certbot --nginx -d api.plotbook.in --redirect \
  -m vigneshwarsivalingam@gmail.com --agree-tos --no-eff-email
```

Renewal is automatic via the `certbot.timer` systemd unit. Test it:
`sudo certbot renew --dry-run`.

## 5. Point the app at HTTPS
- Backend `.env`: add the new origin to `ALLOWED_ORIGINS`, e.g.
  `https://api.plotbook.in` (and your frontend domain).
- Frontend build env: set `NEXT_PUBLIC_API_URL=https://api.plotbook.in`,
  then rebuild + redeploy the static frontend.
- `pm2 restart backend` after editing `.env`.

## Verify
```bash
curl https://api.plotbook.in/health        # {"status":"ok","app":"PlotBook"}
curl -I http://api.plotbook.in/health       # 301 redirect to https
```

## Alternative (no domain): CloudFront
If you can't get a domain, put AWS CloudFront in front of the origin — it
serves HTTPS on a free `*.cloudfront.net` hostname. More moving parts than the
nginx route above, so the domain + certbot path is recommended.
