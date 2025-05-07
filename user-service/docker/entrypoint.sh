#!/bin/bash
set -e

# 直接uvicornを実行（すべてのインターフェースでリッスン）
exec uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 2