# Claude Assistant

Web UI for the Claude voice assistant with cyberpunk avatar.

## Development

```bash
cd frontend
npm install
npm run dev
```

## Deployment

Pushed to `main` triggers GitHub Actions to build and push Docker image to GHCR.
ArgoCD syncs the k8s manifests to deploy at assistant.sogos.io.
