#!/usr/bin/env python3
"""
dump_props_0_10000.py
Brute-force-read camera properties ID range 0..10000 (read-only).
Keeps things simple and robust (no setters except setting MONO mode if available).
"""

from __future__ import annotations

import sys
import time

# adapt imports to your environment
try:
    from sparrow.mode_shared import camera_manager
except Exception as e:
    print("error importing project modules:", e)
    print("make sure you're running this inside the project environment where sparrow is available.")
    sys.exit(1)


def try_get(cam, pid):
    """Try various getters for a single property id. Return (type_name, value) or None."""
    # try int
    try:
        v = cam.get_parameter_int_by_id(pid)
        return ("int", v)
    except Exception:
        pass
    # try bool
    try:
        v = cam.get_parameter_bool_by_id(pid)
        return ("bool", v)
    except Exception:
        pass
    # try float
    try:
        v = cam.get_parameter_float_by_id(pid)
        return ("float", v)
    except Exception:
        pass
    # try string (if camera exposes)
    try:
        v = cam.get_parameter_string_by_id(pid)
        return ("string", v)
    except Exception:
        pass
    # no readable value
    return None


def get_cameras():
    """Return list of camera objects we can use (best-effort filter for Orbbec)."""
    mgr = camera_manager.CAMERA_MANAGER
    try:
        ids, cams = mgr.get_camera_ids_without_opening_cameras()
    except Exception:
        # fallback to whatever manager provides
        try:
            cams = getattr(mgr, "cameras", None) or []
            ids = [getattr(c, "camera_id", lambda: "<unknown>")() for c in cams]
        except Exception:
            cams = []
            ids = []
    # try to filter Orbbec-ish devices, but keep any if filter empties
    orbbec_cams = []
    for idx, cam in zip(ids, cams):
        try:
            manu = cam.manufacturer.lower()
            if "orbbec" in manu or "femto" in manu or "ob" in manu:
                orbbec_cams.append((idx, cam))
        except Exception:
            # unknown manufacturer -> still include (we want to probe)
            orbbec_cams.append((idx, cam))
    if not orbbec_cams and cams:
        orbbec_cams = list(zip(ids, cams))
    return orbbec_cams


def set_mono_mode(cam, cam_id):
    """Try to set MONO mode (best-effort)."""
    try:
        # many wrappers expose set_mode or set_capture_mode; try common names
        if hasattr(cam, "set_mode"):
            cam.set_mode("MONO")
            print(f"[{cam_id}] set to MONO mode (via set_mode)")
            return True
        if hasattr(cam, "set_capture_mode"):
            cam.set_capture_mode("MONO")
            print(f"[{cam_id}] set to MONO mode (via set_capture_mode)")
            return True
        # fallback: try a property set (no-op if not allowed)
        if hasattr(cam, "set_parameter_string_by_id"):
            # try common property id/name: but keep it safe — we won't brute-force setters here
            pass
    except Exception as e:
        print(f"[{cam_id}] set MONO attempt failed: {e}")
    return False


def probe_cam(cam_id, cam, start=0, end=10000, progress_interval=500):
    """Probe property IDs [start, end] and return dict pid->(type,val)."""
    found = {}
    t0 = time.time()
    last_print = t0
    total = end - start + 1
    for i, pid in enumerate(range(start, end + 1), 1):
        # progress printing
        if (pid - start) % progress_interval == 0:
            now = time.time()
            elapsed = now - t0
            pct = (pid - start) / total * 100
            print(f"[{cam_id}] probing pid {pid} ({pct:.1f}% done), elapsed {elapsed:.1f}s")
            last_print = now
        try:
            res = try_get(cam, pid)
            if res is not None:
                found[pid] = res
        except Exception:
            # swallow anything unexpected to keep sweep robust
            pass
    elapsed_total = time.time() - t0
    print(f"[{cam_id}] done probing {total} ids in {elapsed_total:.1f}s — found {len(found)} readable props")
    return found


def main():
    cam_list = get_cameras()
    if not cam_list:
        print("No cameras detected (or camera_manager didn't expose cameras).")
        return

    print("Found cameras:", [cid for cid, _ in cam_list])

    overall = {}
    for cam_id, cam in cam_list:
        # best-effort set MONO at start
        set_mono_mode(cam, cam_id)

        # SDK sometimes prevents listing; print a small notice if listing missing
        try:
            if hasattr(cam, "get_supported_properties"):
                try:
                    props = cam.get_supported_properties()
                    print(f"[{cam_id}] supported_properties() exists, length={len(props)}")
                except Exception:
                    pass
            else:
                print(f"[{cam_id}] property listing not available on this build (probing IDs instead)")
        except Exception:
            pass

        # probe 0..10000
        found = probe_cam(cam_id, cam, start=0, end=10000, progress_interval=1)
        overall[cam_id] = found

    # print compact summary
    print("\n=== SUMMARY ===")
    for cam_id, props in overall.items():
        print(f"[{cam_id}] readable properties: {len(props)}")
        if props:
            # show first 200 entries max (compact)
            shown = 0
            for pid in sorted(props.keys()):
                t, v = props[pid]
                print(f"  id={pid:<5} type={t:<6} value={v}")
                shown += 1
                if shown >= 200:
                    print("  ... (truncated display of results)")
                    break

    # Optionally write full dumps to files
    try:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        for cam_id, props in overall.items():
            fn = f"prop_dump_{cam_id}_{timestamp}.txt"
            with open(fn, "w") as f:
                f.write(f"Camera: {cam_id}\n")
                f.write("Probed range: 0..10000\n")
                f.write(f"Found {len(props)} readable properties\n\n")
                for pid in sorted(props.keys()):
                    t, v = props[pid]
                    f.write(f"{pid}\t{t}\t{v}\n")
            print(f"Wrote full dump to {fn}")
    except Exception as e:
        print("Failed to write dumps:", e)


if __name__ == "__main__":
    main()
