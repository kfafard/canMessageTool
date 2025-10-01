#!/usr/bin/env bash
pkill -f "uvicorn app:app" || true
pkill -f "vite" || true
echo "✅ Stopped backend & frontend"
