"""
altitude_test.py
─────────────────
Standalone altitude test mission for PX4 via pymavlink.

The drone:
  1. Arms in place (lat/lon unchanged throughout)
  2. Takes off vertically to a user-specified target altitude (AGL)
  3. Holds position in LOITER and streams altitude error to the console
  4. Lands vertically back to the same spot

Abort / failsafe at ANY time:
  • Press  Ctrl+C  → immediate RTL (Return-to-Launch)
  • The monitor loop also sends RTL if the drone disarms unexpectedly
    or if a MAVLink heartbeat is lost for > HEARTBEAT_TIMEOUT_S seconds.

Usage:
    python altitude_test.py                          # serial /dev/ttyUSB0
    python altitude_test.py udp:127.0.0.1:14550      # SITL
    python altitude_test.py /dev/cu.usbserial-XXXX 57600
"""

import sys
import time
import logging
import threading
from pymavlink import mavutil

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-14s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("AltitudeTest")

# ── Configuration — edit to match your setup ──────────────────────────────────
DEFAULT_CONNECTION  = "/dev/cu.usbserial-D30K0P9O"
DEFAULT_BAUD        = 57600

HOLD_DURATION_S     = 10.0      # seconds to hover at target altitude before landing
ALT_REACHED_THRESH  = 0.5       # metres — "close enough to target" threshold
HEARTBEAT_TIMEOUT_S = 5.0       # seconds without heartbeat → RTL

# ── MAV_RESULT decoder (for readable ACK logs) ────────────────────────────────
MAV_RESULT = {
    0: "ACCEPTED",
    1: "TEMPORARILY_REJECTED",
    2: "DENIED",
    3: "UNSUPPORTED",
    4: "FAILED",
    5: "IN_PROGRESS",
    6: "CANCELLED",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def connect(connection_string: str, baud: int) -> mavutil.mavfile:
    log.info(f"Connecting to PX4 at {connection_string} …")
    master = mavutil.mavlink_connection(connection_string, baud=baud)
    master.wait_heartbeat(timeout=15)
    log.info(
        f"✓ Heartbeat from system {master.target_system} "
        f"component {master.target_component}"
    )
    log.info(f"Available flight modes: {list(master.mode_mapping().keys())}")
    return master


def send_rtl(master: mavutil.mavfile, reason: str = ""):
    """Switch to RTL mode — safest abort for a PX4 drone in the air."""
    tag = f" ({reason})" if reason else ""
    log.warning(f"⚠ ABORT{tag} — sending RTL")
    mapping = master.mode_mapping()
    rtl_val = mapping.get("RTL") or mapping.get("AUTO.RTL")
    if rtl_val is None:
        log.error("RTL mode not found in mode_mapping — disarming instead")
        master.mav.command_long_send(
            master.target_system, master.target_component,
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            0, 0, 0, 0, 0, 0, 0, 0,
        )
        return

    if isinstance(rtl_val, tuple):
        base_mode, custom_mode, custom_sub_mode = rtl_val
    else:
        base_mode       = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        custom_mode     = rtl_val
        custom_sub_mode = 0

    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        0,
        float(base_mode), float(custom_mode), float(custom_sub_mode),
        0.0, 0.0, 0.0, 0.0,
    )


def set_mode(master: mavutil.mavfile, mode_name: str) -> bool:
    """
    Set PX4 flight mode by exact name.
    Prints available modes on failure so you always know what's valid.
    """
    mapping = master.mode_mapping()
    if mode_name not in mapping:
        log.error(f"Mode '{mode_name}' not found. Available: {list(mapping.keys())}")
        return False

    val = mapping[mode_name]
    if isinstance(val, tuple):
        base_mode, custom_mode, custom_sub_mode = val
    else:
        base_mode       = mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED
        custom_mode     = val
        custom_sub_mode = 0

    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_DO_SET_MODE,
        0,
        float(base_mode), float(custom_mode), float(custom_sub_mode),
        0.0, 0.0, 0.0, 0.0,
    )
    log.info(f"Set mode → '{mode_name}'")

    deadline = time.time() + 5
    while time.time() < deadline:
        hb = master.recv_match(type="HEARTBEAT", blocking=True, timeout=2)
        if hb and hb.get_srcSystem() == master.target_system:
            if master.flightmode == mode_name:
                log.info(f"Mode confirmed: {mode_name} ✓")
                return True
    log.error(f"Mode '{mode_name}' not confirmed (current: {master.flightmode})")
    return False


def arm(master: mavutil.mavfile) -> bool:
    log.info("Arming …")
    master.mav.command_long_send(
        master.target_system, master.target_component,
        mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        1, 0, 0, 0, 0, 0, 0,   # param1=1 → arm
    )
    msg = master.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
    if msg and msg.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
        log.info("Armed ✓")
        return True
    result_str = MAV_RESULT.get(msg.result, str(msg.result)) if msg else "no ACK"
    log.error(f"Arm failed: {result_str}")
    return False


def set_takeoff_altitude_param(master: mavutil.mavfile, target_alt_m: float):
    """
    Write MIS_TAKEOFF_ALT so PX4 knows how high to climb in TAKEOFF mode.
    This is the correct way to set takeoff altitude when using the TAKEOFF
    flight mode (as opposed to sending a NAV_TAKEOFF command).
    """
    log.info(f"Setting MIS_TAKEOFF_ALT = {target_alt_m:.1f}m …")
    master.mav.param_set_send(
        master.target_system,
        master.target_component,
        b'MIS_TAKEOFF_ALT',
        float(target_alt_m),
        mavutil.mavlink.MAV_PARAM_TYPE_REAL32,
    )
    # Wait for PARAM_VALUE echo to confirm it was accepted
    msg = master.recv_match(type="PARAM_VALUE", blocking=True, timeout=3)
    if msg and msg.param_id.strip('\x00') == 'MIS_TAKEOFF_ALT':
        log.info(f"MIS_TAKEOFF_ALT confirmed = {msg.param_value:.1f}m ✓")
    else:
        log.warning("No PARAM_VALUE echo received — param may still have been set")


# ── Heartbeat watchdog ────────────────────────────────────────────────────────

class HeartbeatWatchdog(threading.Thread):
    """
    Background thread — triggers RTL if no heartbeat is received within
    HEARTBEAT_TIMEOUT_S seconds.  Call .cancel() when done.
    """
    def __init__(self, master: mavutil.mavfile, abort_event: threading.Event):
        super().__init__(daemon=True)
        self.master      = master
        self.abort_event = abort_event
        self._last_hb    = time.time()
        self._cancelled  = False

    def touch(self):
        """Call this each time a heartbeat is received."""
        self._last_hb = time.time()

    def cancel(self):
        self._cancelled = True

    def run(self):
        while not self._cancelled:
            time.sleep(1.0)
            if time.time() - self._last_hb > HEARTBEAT_TIMEOUT_S:
                log.error(
                    f"No heartbeat for >{HEARTBEAT_TIMEOUT_S}s — triggering RTL"
                )
                send_rtl(self.master, "heartbeat lost")
                self.abort_event.set()
                break


# ── Phase: climb to target altitude ──────────────────────────────────────────

def wait_for_altitude(
    master: mavutil.mavfile,
    target_alt_m: float,
    abort_event: threading.Event,
    watchdog: HeartbeatWatchdog,
) -> bool:
    """
    Poll GLOBAL_POSITION_INT until relative_alt >= target_alt - ALT_REACHED_THRESH.
    Returns True when reached, False if aborted.
    """
    log.info(f"Climbing to {target_alt_m:.1f}m … (Ctrl+C to abort)")
    while not abort_event.is_set():
        msg = master.recv_match(
            type=["GLOBAL_POSITION_INT", "HEARTBEAT", "STATUSTEXT"],
            blocking=True, timeout=2,
        )
        if msg is None:
            continue

        if msg.get_type() == "HEARTBEAT":
            watchdog.touch()
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if not armed:
                log.error("Drone disarmed during climb — aborting")
                abort_event.set()
                return False

        if msg.get_type() == "STATUSTEXT":
            log.info(f"PX4: {msg.text.strip()}")

        if msg.get_type() == "GLOBAL_POSITION_INT":
            current_alt = msg.relative_alt / 1000.0   # mm → m
            err = target_alt_m - current_alt
            log.info(
                f"  Climbing … current={current_alt:.2f}m  "
                f"target={target_alt_m:.1f}m  error={err:+.2f}m"
            )
            if current_alt >= target_alt_m - ALT_REACHED_THRESH:
                log.info(f"✓ Target altitude reached: {current_alt:.2f}m")
                return True

    return False


# ── Phase: hold and display error ────────────────────────────────────────────

def hold_and_report(
    master: mavutil.mavfile,
    target_alt_m: float,
    hold_seconds: float,
    abort_event: threading.Event,
    watchdog: HeartbeatWatchdog,
):
    """
    Hover at target altitude for hold_seconds in LOITER mode,
    printing altitude error every poll cycle.
    """
    log.info(f"Holding at {target_alt_m:.1f}m for {hold_seconds:.0f}s …")
    log.info("━" * 62)
    log.info(f"  {'TIME':>6}  {'CURRENT':>10}  {'TARGET':>8}  {'ERROR':>8}  STATUS")
    log.info("━" * 62)

    start = time.time()
    while not abort_event.is_set():
        elapsed = time.time() - start
        if elapsed >= hold_seconds:
            break

        msg = master.recv_match(
            type=["GLOBAL_POSITION_INT", "HEARTBEAT", "STATUSTEXT"],
            blocking=True, timeout=2,
        )
        if msg is None:
            continue

        if msg.get_type() == "HEARTBEAT":
            watchdog.touch()
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if not armed:
                log.error("Drone disarmed during hold — aborting")
                abort_event.set()
                return

        if msg.get_type() == "STATUSTEXT":
            log.info(f"PX4: {msg.text.strip()}")

        if msg.get_type() == "GLOBAL_POSITION_INT":
            current_alt = msg.relative_alt / 1000.0
            error_m     = current_alt - target_alt_m
            abs_err     = abs(error_m)
            remaining   = hold_seconds - elapsed

            if abs_err <= 0.3:
                status = "✓ EXCELLENT"
            elif abs_err <= 0.7:
                status = "~ GOOD"
            elif abs_err <= 1.5:
                status = "△ MODERATE"
            else:
                status = "✗ POOR"

            log.info(
                f"  {elapsed:5.1f}s  {current_alt:8.3f}m  "
                f"{target_alt_m:8.1f}m  {error_m:+8.3f}m  "
                f"{status}  ({remaining:.0f}s left)"
            )

    log.info("━" * 62)
    if not abort_event.is_set():
        log.info("Hold complete.")


# ── Phase: wait for landing ───────────────────────────────────────────────────

def wait_for_landing(
    master: mavutil.mavfile,
    abort_event: threading.Event,
    watchdog: HeartbeatWatchdog,
    timeout_s: float = 60.0,
):
    """
    Wait until PX4 auto-disarms after touchdown.
    Falls through after timeout_s seconds to avoid hanging indefinitely in SITL.
    """
    log.info("Landing … waiting for touchdown and auto-disarm")
    deadline = time.time() + timeout_s
    while not abort_event.is_set():
        if time.time() > deadline:
            log.warning(f"Landing timeout after {timeout_s:.0f}s — assuming grounded")
            return

        msg = master.recv_match(
            type=["HEARTBEAT", "STATUSTEXT", "GLOBAL_POSITION_INT"],
            blocking=True, timeout=2,
        )
        if msg is None:
            continue

        if msg.get_type() == "HEARTBEAT":
            watchdog.touch()
            armed = bool(msg.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
            if not armed:
                log.info("✓ Drone disarmed — landing complete")
                return

        if msg.get_type() == "STATUSTEXT":
            log.info(f"PX4: {msg.text.strip()}")

        if msg.get_type() == "GLOBAL_POSITION_INT":
            alt = msg.relative_alt / 1000.0
            log.info(f"  Landing … alt={alt:.2f}m")


# ── Main mission ──────────────────────────────────────────────────────────────

def run_altitude_test(master: mavutil.mavfile, target_alt_m: float):
    abort_event = threading.Event()
    watchdog    = HeartbeatWatchdog(master, abort_event)
    watchdog.start()

    try:
        # ── 1. Write MIS_TAKEOFF_ALT before arming ────────────────────────────
        set_takeoff_altitude_param(master, target_alt_m)
        time.sleep(0.5)

        # ── 2. Arm ────────────────────────────────────────────────────────────
        if not arm(master):
            log.error("Arming failed — aborting")
            return

        log.info("Settling 1s post-arm …")
        time.sleep(1.0)

        # ── 3. Switch to TAKEOFF mode — drone climbs automatically ────────────
        #
        # Your PX4 build exposes "TAKEOFF" directly (not "AUTO.TAKEOFF").
        # In TAKEOFF mode PX4 climbs to MIS_TAKEOFF_ALT then transitions
        # to LOITER automatically — we also switch to LOITER explicitly
        # after confirming altitude so we control the timing.
        #
        if not set_mode(master, "TAKEOFF"):
            log.error("Could not set TAKEOFF mode — aborting")
            send_rtl(master, "mode set failed")
            return

        # ── 4. Wait to reach target altitude ──────────────────────────────────
        reached = wait_for_altitude(master, target_alt_m, abort_event, watchdog)
        if not reached or abort_event.is_set():
            send_rtl(master, "altitude not reached")
            wait_for_landing(master, abort_event, watchdog)
            return

        # ── 5. Switch to LOITER to hold position ──────────────────────────────
        log.info("Switching to LOITER …")
        if not set_mode(master, "LOITER"):
            log.warning("LOITER failed — drone may drift; continuing hold anyway")

        # ── 6. Hold + report altitude error ───────────────────────────────────
        hold_and_report(master, target_alt_m, HOLD_DURATION_S, abort_event, watchdog)
        if abort_event.is_set():
            send_rtl(master, "abort during hold")
            wait_for_landing(master, abort_event, watchdog)
            return

        # ── 7. Land in place ──────────────────────────────────────────────────
        log.info("Switching to LAND mode …")
        if not set_mode(master, "LAND"):
            log.warning("LAND mode failed — falling back to RTL")
            send_rtl(master, "LAND mode unavailable")

        wait_for_landing(master, abort_event, watchdog)

    except KeyboardInterrupt:
        log.warning("Ctrl+C — initiating RTL")
        abort_event.set()
        send_rtl(master, "user abort")
        wait_for_landing(master, abort_event, watchdog)

    finally:
        watchdog.cancel()
        log.info("Altitude test finished.")


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    conn_str = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONNECTION
    baud     = int(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_BAUD

    master = connect(conn_str, baud)

    print("\n" + "═" * 58)
    print("  PX4 Altitude Test — vertical climb, hold, and land")
    print("═" * 58)
    print(f"  Drone climbs straight up, holds for {HOLD_DURATION_S:.0f}s, then lands.")
    print("  Latitude and longitude will NOT change.\n")
    print("  RC killswitch overrides at any time.")
    print("  Press  Ctrl+C  to trigger RTL from this script.\n")

    while True:
        raw = input("  Target altitude in metres AGL (e.g. 10): ").strip()
        try:
            target_alt = float(raw)
            if target_alt <= 0:
                raise ValueError
            break
        except ValueError:
            print("  ✗ Enter a positive number.")

    confirm = input(f"\n  Fly to {target_alt:.1f}m and return? [y/N]: ").strip().lower()
    if confirm != "y":
        print("  Aborted.")
        return

    print()
    run_altitude_test(master, target_alt)


if __name__ == "__main__":
    main()