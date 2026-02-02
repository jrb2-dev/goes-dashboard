#!/usr/bin/env python3
"""
GOES Satellite Dashboard
A real-time web dashboard for monitoring goestools ground stations.

https://github.com/YOUR_USERNAME/goes-dashboard
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import subprocess
import psutil
import os
import re
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List

# =============================================================================
# Configuration
# =============================================================================

CONFIG_PATH = Path(__file__).parent / "config.json"
DEFAULT_CONFIG = {
    "satellite": "GOES-16",
    "data_dir": "/home/pi/goes16",
    "images_dir": "/home/pi/goes16",
    "emwin_dir": "/home/pi/goes16/emwinTEXT/emwin",
    "upload_logs_dir": "/home/pi",
    "services": {
        "receiver": "goesrecv",
        "processors": ["goesproc"]
    },
    "upload_stations": [],
    "image_types": {
        "fd_fc": "fd/fc",
        "m1_fc": "m1/fc",
        "m2_fc": "m2/fc"
    },
    "dashboard_port": 8080,
    "refresh_interval": 5000
}

def load_config() -> dict:
    """Load configuration from file or use defaults."""
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                user_config = json.load(f)
                # Merge with defaults
                config = DEFAULT_CONFIG.copy()
                config.update(user_config)
                return config
        except Exception as e:
            print(f"Warning: Could not load config.json: {e}")
    return DEFAULT_CONFIG

CONFIG = load_config()

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="GOES Satellite Dashboard",
    description="Real-time monitoring for goestools ground stations",
    version="1.0.0"
)

# CORS for local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Helper Functions
# =============================================================================

def run_cmd(cmd: list, timeout: int = 5) -> str:
    """Run a shell command and return output."""
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return "Command timed out"
    except Exception as e:
        return str(e)


def get_service_names() -> List[str]:
    """Get list of all service names to monitor."""
    services = [CONFIG["services"]["receiver"]]
    services.extend(CONFIG["services"].get("processors", []))
    return services


def parse_signal_line(line: str) -> dict:
    """Parse a goesrecv monitor line into stats dict."""
    patterns = {
        "gain": r"gain:\s*([\d.]+)",
        "freq": r"freq:\s*([-\d.]+)",
        "omega": r"omega:\s*([\d.]+)",
        "vit_avg": r"vit\(avg\):\s*(\d+)",
        "drops": r"drops:\s*(\d+)",
        "packets": r"packets:\s*(\d+)"
    }
    
    stats = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, line)
        if match:
            val = match.group(1)
            stats[key] = float(val) if '.' in val else int(val)
    
    return stats


def get_signal_quality(vit_avg: int) -> str:
    """Determine signal quality from viterbi average."""
    if vit_avg < 300:
        return "excellent"
    elif vit_avg < 400:
        return "good"
    elif vit_avg < 500:
        return "fair"
    return "poor"

# =============================================================================
# API Endpoints
# =============================================================================

@app.get("/api/config")
def get_config():
    """Get current dashboard configuration (safe values only)."""
    return {
        "satellite": CONFIG["satellite"],
        "refresh_interval": CONFIG["refresh_interval"],
        "services": get_service_names(),
        "upload_stations": CONFIG["upload_stations"]
    }


@app.get("/api/signal")
def get_signal_stats():
    """Get current goesrecv signal statistics from journalctl."""
    receiver = CONFIG["services"]["receiver"]
    output = run_cmd([
        "journalctl", "-u", f"{receiver}.service",
        "-n", "50", "--no-pager", "-o", "cat"
    ])
    
    stats = {
        "gain": None,
        "freq": None,
        "omega": None,
        "vit_avg": None,
        "drops": None,
        "packets": None,
        "timestamp": datetime.now().isoformat(),
        "status": "unknown",
        "satellite": CONFIG["satellite"]
    }
    
    # Find most recent monitor line
    lines = output.strip().split('\n')
    for line in reversed(lines):
        if '[monitor]' in line:
            parsed = parse_signal_line(line)
            stats.update(parsed)
            
            if stats.get("vit_avg") is not None:
                stats["status"] = get_signal_quality(stats["vit_avg"])
            break
    
    return stats


@app.get("/api/services")
def get_services_status():
    """Get status of all GOES-related systemd services."""
    services = []
    
    for service in get_service_names():
        service_name = f"{service}.service"
        
        # Get service status
        status_output = run_cmd(["systemctl", "is-active", service_name])
        is_active = status_output.strip() == "active"
        
        # Get uptime/details
        details_output = run_cmd([
            "systemctl", "show", service_name,
            "--property=ActiveEnterTimestamp,MainPID,MemoryCurrent"
        ])
        
        details = {}
        for line in details_output.strip().split('\n'):
            if '=' in line:
                key, val = line.split('=', 1)
                details[key] = val
        
        # Calculate uptime
        uptime = None
        if details.get("ActiveEnterTimestamp"):
            try:
                start_str = details["ActiveEnterTimestamp"]
                if start_str and start_str not in ["n/a", ""]:
                    start_time = datetime.strptime(
                        start_str.split('.')[0],
                        "%a %Y-%m-%d %H:%M:%S"
                    )
                    uptime = (datetime.now() - start_time).total_seconds()
            except Exception:
                pass
        
        # Get memory usage
        memory_mb = None
        if details.get("MemoryCurrent"):
            try:
                mem_bytes = int(details["MemoryCurrent"])
                memory_mb = round(mem_bytes / 1024 / 1024, 1)
            except (ValueError, TypeError):
                pass
        
        services.append({
            "name": service,
            "active": is_active,
            "pid": details.get("MainPID"),
            "uptime_seconds": uptime,
            "memory_mb": memory_mb
        })
    
    return {"services": services}


@app.get("/api/disk")
def get_disk_usage():
    """Get disk usage statistics."""
    disk = psutil.disk_usage('/')
    
    def get_dir_size(path_str: str) -> Optional[int]:
        path = Path(path_str)
        if not path.exists():
            return None
        try:
            result = run_cmd(["du", "-sb", str(path)])
            return int(result.split()[0])
        except Exception:
            return None
    
    return {
        "total_gb": round(disk.total / 1024**3, 1),
        "used_gb": round(disk.used / 1024**3, 1),
        "free_gb": round(disk.free / 1024**3, 1),
        "percent": disk.percent,
        "directories": {
            "data": get_dir_size(CONFIG["data_dir"]),
            "images": get_dir_size(CONFIG["images_dir"]),
            "emwin": get_dir_size(CONFIG["emwin_dir"])
        }
    }


@app.get("/api/system")
def get_system_stats():
    """Get system health metrics."""
    # CPU temperature (Raspberry Pi specific)
    temp = None
    try:
        result = run_cmd(["vcgencmd", "measure_temp"])
        match = re.search(r"temp=([\d.]+)", result)
        if match:
            temp = float(match.group(1))
    except Exception:
        # Try alternative method for non-Pi systems
        try:
            with open("/sys/class/thermal/thermal_zone0/temp") as f:
                temp = int(f.read().strip()) / 1000
        except Exception:
            pass
    
    # Memory
    mem = psutil.virtual_memory()
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Load average
    load = os.getloadavg()
    
    # Boot time
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime_seconds = (datetime.now() - boot_time).total_seconds()
    
    return {
        "cpu_temp_c": temp,
        "cpu_percent": cpu_percent,
        "memory_percent": mem.percent,
        "memory_used_mb": round(mem.used / 1024**2, 1),
        "memory_total_mb": round(mem.total / 1024**2, 1),
        "load_1m": round(load[0], 2),
        "load_5m": round(load[1], 2),
        "load_15m": round(load[2], 2),
        "uptime_seconds": uptime_seconds,
        "hostname": os.uname().nodename
    }


@app.get("/api/images")
def get_recent_images(limit: int = 10):
    """Get list of recent satellite images."""
    today = datetime.now().strftime("%Y-%m-%d")
    images = []
    images_dir = Path(CONFIG["images_dir"])
    
    for type_key, subpath in CONFIG.get("image_types", {}).items():
        image_dir = images_dir / subpath / today
        if image_dir.exists():
            try:
                files = sorted(
                    image_dir.glob("*.jpg"),
                    key=lambda f: f.stat().st_mtime,
                    reverse=True
                )
                for f in files[:limit]:
                    images.append({
                        "path": str(f),
                        "name": f.name,
                        "type": type_key,
                        "size_kb": round(f.stat().st_size / 1024, 1),
                        "timestamp": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
                    })
            except Exception as e:
                print(f"Error reading {image_dir}: {e}")
    
    # Sort all by timestamp and limit
    images = sorted(images, key=lambda x: x["timestamp"], reverse=True)[:limit]
    return {"images": images}


@app.get("/api/image/{image_type}/{date}/{filename}")
def serve_image(image_type: str, date: str, filename: str):
    """Serve a satellite image file."""
    # Validate inputs to prevent path traversal
    if ".." in date or ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid path")
    
    image_types = CONFIG.get("image_types", {})
    if image_type not in image_types:
        raise HTTPException(status_code=404, detail="Unknown image type")
    
    image_path = Path(CONFIG["images_dir"]) / image_types[image_type] / date / filename
    
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")
    
    return FileResponse(image_path, media_type="image/jpeg")


@app.get("/api/uploads")
def get_upload_stats():
    """Get today's upload statistics."""
    today = datetime.now().strftime("%Y-%m-%d")
    upload_logs_dir = Path(CONFIG["upload_logs_dir"])
    
    stats = {}
    total = 0
    
    for station in CONFIG.get("upload_stations", []):
        log_path = upload_logs_dir / f"{station}_upload_log_{today}.txt"
        count = 0
        if log_path.exists():
            try:
                with open(log_path) as f:
                    count = len(f.readlines())
            except Exception:
                pass
        stats[station] = count
        total += count
    
    # Count EMWIN files received today
    emwin_dir = Path(CONFIG["emwin_dir"]) / today
    emwin_count = 0
    if emwin_dir.exists():
        try:
            emwin_count = len(list(emwin_dir.glob("*.TXT")))
        except Exception:
            pass
    
    return {
        "date": today,
        "uploads_by_station": stats,
        "total_uploads": total,
        "emwin_files_received": emwin_count
    }


@app.get("/api/logs/{log_type}")
def get_logs(log_type: str, lines: int = 50):
    """Get recent log entries."""
    # Validate lines parameter
    lines = min(max(1, lines), 500)
    
    all_services = get_service_names()
    
    if log_type in all_services:
        output = run_cmd([
            "journalctl", "-u", f"{log_type}.service",
            "-n", str(lines), "--no-pager"
        ])
    elif log_type == "health":
        health_log = Path(CONFIG["upload_logs_dir"]) / "health_log.txt"
        if health_log.exists():
            try:
                with open(health_log) as f:
                    output = ''.join(f.readlines()[-lines:])
            except Exception as e:
                output = f"Error reading health log: {e}"
        else:
            output = "Health log not found"
    elif log_type == "system":
        output = run_cmd([
            "journalctl", "-n", str(lines), "--no-pager"
        ])
    else:
        raise HTTPException(status_code=400, detail="Unknown log type")
    
    return {"log_type": log_type, "content": output}


@app.get("/api/health")
def health_check():
    """Simple health check endpoint."""
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "hostname": os.uname().nodename,
        "satellite": CONFIG["satellite"],
        "version": "1.0.0"
    }


# =============================================================================
# Static Files (Frontend)
# =============================================================================

static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    
    port = CONFIG.get("dashboard_port", 8080)
    print(f"🛰️  Starting GOES Dashboard on port {port}")
    print(f"   Satellite: {CONFIG['satellite']}")
    print(f"   Data dir: {CONFIG['data_dir']}")
    
    uvicorn.run(app, host="0.0.0.0", port=port)
