"""Simulator verbs (ADR 0002 D4, "all simulator use", contract section 4a).

A simulator is named in a request by { name, os } exactly as sim-list reports
them. The runner looks that pair up in `xcrun simctl list` and uses the UDID it
found there. Nothing from the request reaches a command line: not the name,
not the OS, not a path. Only iOS runtimes that simctl reports as available
count. Two simulators with the same name and OS are refused, never guessed."""

from __future__ import annotations

import base64
import json
import plistlib
import re
from pathlib import Path
from typing import List, Optional

from .core import (ApiError, StepFailed, RUN_ID_RE, _fields, _int, _str, envelope, tier_note,
                        tree_digest)

SIM_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ().,'-]{0,63}$")
SIM_OS_RE = re.compile(r"^[0-9]{1,2}\.[0-9]{1,2}(\.[0-9]{1,2})?$")
SIM_UDID_RE = re.compile(r"^[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{4}-[0-9A-F]{12}$")
SIM_STATES = {"Booted": "booted", "Shutdown": "shutdown", "Booting": "booting", "Shutting Down": "shutting-down"}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_FILE_PAGE = 262144
SCREENSHOT_NAME = "screenshot.png"


def public(sim: dict) -> dict:
    return {"name": sim["name"], "os": sim["os"], "state": sim["state"]}


class SimulatorVerbs:
    """Mixed into Runner. Uses its quick(), take_lock(), project(), new_run(),
    _work(), load(), reply() and _check_artifact()."""

    # listing and lookup

    def sim_list_raw(self) -> Optional[List[dict]]:
        """simctl's available iOS simulators, or None when simctl could not answer."""
        code, out = self.quick(["xcrun", "simctl", "list", "--json", "devices", "runtimes"],
                               self.config.state_dir, "simulator", merge=False)
        if code != 0:
            return None
        try:
            data = json.loads(out.decode("utf-8", "replace"))
            runtimes = {r.get("identifier"): r.get("version") for r in data.get("runtimes", [])
                        if isinstance(r, dict) and r.get("platform") == "iOS" and r.get("isAvailable")}
            sims = []
            for runtime, devices in (data.get("devices") or {}).items():
                version = runtimes.get(runtime)
                if not isinstance(version, str) or not SIM_OS_RE.match(version):
                    continue
                for d in devices or []:
                    if not isinstance(d, dict) or not d.get("isAvailable"):
                        continue
                    name, udid = d.get("name"), str(d.get("udid", "")).upper()
                    if not isinstance(name, str) or not SIM_NAME_RE.match(name) or not SIM_UDID_RE.match(udid):
                        continue
                    sims.append({"name": name, "os": version, "udid": udid,
                                 "state": SIM_STATES.get(d.get("state"), "unknown")})
            return sorted(sims, key=lambda s: (s["os"], s["name"], s["udid"]))
        except (ValueError, AttributeError, TypeError):
            return None

    def sim_allowed(self):
        if not self.config.simulator_allowed:
            raise ApiError("SIMULATOR_DISABLED", "Simulator use is turned off in the runner's allowlist.")

    def sim_resolve(self, body) -> dict:
        value = body.get("simulator")
        if not isinstance(value, dict) or set(value) != {"name", "os"}:
            raise ApiError("BAD_ARGUMENT", "simulator must be { name, os }, as sim-list reports them.")
        name, os_version = value["name"], value["os"]
        if not isinstance(name, str) or not SIM_NAME_RE.match(name):
            raise ApiError("BAD_ARGUMENT", "simulator name is not valid.")
        if not isinstance(os_version, str) or not SIM_OS_RE.match(os_version):
            raise ApiError("BAD_ARGUMENT", "simulator os is not valid.")
        sims = self.sim_list_raw()
        if sims is None:
            raise ApiError("SIMULATOR_UNAVAILABLE", "simctl could not list the simulators.")
        found = [s for s in sims if s["name"] == name and s["os"] == os_version]
        if not found:
            raise ApiError("SIMULATOR_NOT_FOUND", f"No available simulator {name} on iOS {os_version}.")
        if len(found) > 1:
            raise ApiError("SIMULATOR_NOT_FOUND",
                           f"{len(found)} simulators are named {name} on iOS {os_version}. The runner won't guess.")
        return found[0]

    def sim_state(self, udid) -> Optional[dict]:
        sims = self.sim_list_raw()
        if sims is None:
            return None
        return next((s for s in sims if s["udid"] == udid), None)

    # non-run verbs

    def sim_list(self, body):
        _fields(body or {}, [], [])
        self.sim_allowed()
        sims = self.sim_list_raw()
        if sims is None:
            raise ApiError("SIMULATOR_UNAVAILABLE", "simctl could not list the simulators.")
        return envelope(True, None, simulators=[public(s) for s in sims])

    def sim_boot(self, body):
        _fields(body, ["simulator"], [])
        self.sim_allowed()
        sim = self.sim_resolve(body)
        lock = self.take_lock()
        try:
            if sim["state"] != "booted":
                # bootstatus -b boots it if needed and waits until it has finished booting.
                code, _ = self.quick(["xcrun", "simctl", "bootstatus", sim["udid"], "-b"],
                                     self.config.state_dir, "simulator")
                if code != 0:
                    raise ApiError("SIMULATOR_UNAVAILABLE", f"{sim['name']} did not boot.")
            now = self.sim_state(sim["udid"])
            if not now or now["state"] != "booted":
                raise ApiError("SIMULATOR_UNAVAILABLE", f"{sim['name']} is not booted after the boot.")
            return envelope(True, None, simulator=public(now))
        finally:
            lock.release()

    def sim_shutdown(self, body):
        _fields(body, ["simulator"], [])
        self.sim_allowed()
        sim = self.sim_resolve(body)
        lock = self.take_lock()
        try:
            if sim["state"] != "shutdown":
                code, _ = self.quick(["xcrun", "simctl", "shutdown", sim["udid"]], self.config.state_dir, "simulator")
                if code != 0:
                    raise ApiError("SIMULATOR_UNAVAILABLE", f"{sim['name']} did not shut down.")
            now = self.sim_state(sim["udid"])
            if not now or now["state"] != "shutdown":
                raise ApiError("SIMULATOR_UNAVAILABLE", f"{sim['name']} is not shut down after the shutdown.")
            return envelope(True, None, simulator=public(now))
        finally:
            lock.release()

    def sim_terminate(self, body):
        _fields(body, ["project", "simulator"], [])
        self.sim_allowed()
        project = self.project(body)
        sim = self.sim_resolve(body)
        if sim["state"] != "booted":
            raise ApiError("SIMULATOR_UNAVAILABLE", f"{sim['name']} is not booted.")
        lock = self.take_lock()
        try:
            code, _ = self.quick(["xcrun", "simctl", "terminate", sim["udid"], project.bundle_id],
                                 self.config.state_dir, "simulator")
            if code != 0:
                raise ApiError("TERMINATE_FAILED", "simctl could not stop the app. It may not be running.")
            return envelope(True, None, project=project.name, simulator=public(sim), terminated=True)
        finally:
            lock.release()

    # run verbs: install, launch, screenshot

    def _sim_run(self, project, kind, sim, configuration=None, commit=None, artifact=None, launch=False, **extra):
        lock = self.take_lock()
        try:
            ctx = self.new_run(project, kind, configuration, commit, simulator=public(sim), **extra)
            ctx.sim_udid = sim["udid"]
            ctx.sim_artifact = artifact
            ctx.sim_launch = launch
        except BaseException:
            lock.release()
            raise
        self._work(ctx, lock)  # simulator runs are synchronous, like install-device
        return self.reply(ctx.run["run_id"])

    def sim_install(self, body):
        _fields(body, ["build_run_id", "simulator"], ["launch"])
        self.sim_allowed()
        launch = body.get("launch", False)
        if not isinstance(launch, bool):
            raise ApiError("BAD_ARGUMENT", "launch must be true or false.")
        build_id = _str(body, "build_run_id", RUN_ID_RE, "build_run_id")
        build = self.load(build_id)["run"]
        if build.get("kind") != "simulator" or build.get("state") != "succeeded" or not build.get("artifact"):
            raise ApiError("NOT_INSTALLABLE", "That run is not a finished simulator build.")
        project = self.config.projects.get(build["project"])
        if project is None:
            raise ApiError("PROJECT_NOT_ALLOWED", f"Project {build['project']} is no longer in the allowlist.")
        sim = self.sim_resolve(body)
        return self._sim_run(project, "sim-install", sim, build["configuration"], build["commit"],
                             artifact=build["artifact"], launch=launch, build_run_id=build_id)

    def sim_launch(self, body):
        _fields(body, ["project", "simulator"], [])
        self.sim_allowed()
        project = self.project(body)
        return self._sim_run(project, "sim-launch", self.sim_resolve(body))

    def sim_screenshot(self, body):
        _fields(body, ["project", "simulator"], [])
        self.sim_allowed()
        project = self.project(body)
        return self._sim_run(project, "sim-screenshot", self.sim_resolve(body))

    def _sim_work(self, ctx):
        kind = ctx.run["kind"]
        udid = ctx.sim_udid
        bundle = ctx.project.bundle_id
        if kind == "sim-install":
            artifact = ctx.sim_artifact
            app = self._check_artifact(artifact)
            ctx.set(artifact=dict(artifact), tier="build", tier_note=tier_note("sim-install", "build"))
        self._sim_booted(ctx, udid)
        if kind == "sim-install":
            ctx.failure_code = "INSTALL_FAILED"
            ctx.step("simctl-install", ["xcrun", "simctl", "install", udid, str(app)], ctx.dir, "simulator")
            installed = self._sim_container(ctx, udid, bundle)
            if installed is None:
                raise StepFailed("INSTALL_FAILED", "simctl does not list the app on the simulator after the install.")
            ctx.set(tier="install", tier_note=tier_note("sim-install", "install"))
            if ctx.sim_launch:
                self._sim_launch(ctx, udid, bundle)
                ctx.set(tier="launch", tier_note=tier_note("sim-install", "launch"))
        elif kind == "sim-launch":
            if self._sim_container(ctx, udid, bundle) is None:
                raise StepFailed("LAUNCH_FAILED", "The app is not installed on that simulator.")
            self._sim_launch(ctx, udid, bundle)
            ctx.set(tier="launch", tier_note=tier_note("sim-launch", "launch"))
        elif kind == "sim-screenshot":
            self._sim_screenshot(ctx, udid)
            ctx.set(tier_note=tier_note("sim-screenshot", "none"))
        else:
            raise StepFailed("RUNNER_ERROR", "Unknown simulator run.")

    def _sim_booted(self, ctx, udid):
        now = self.sim_state(udid)
        if now is None:
            raise StepFailed("SIMULATOR_UNAVAILABLE", "simctl could not list the simulators.")
        if now["state"] != "booted":
            raise StepFailed("SIMULATOR_UNAVAILABLE", f"{now['name']} is not booted. Boot it first.")

    def _sim_container(self, ctx, udid, bundle) -> Optional[Path]:
        """The installed app's folder, if simctl lists the bundle ID on the
        simulator and the folder's Info.plist carries it. None otherwise."""
        try:
            out = ctx.step("simctl-get-app-container", ["xcrun", "simctl", "get_app_container", udid, bundle, "app"],
                           ctx.dir, "simulator", capture=True)
        except StepFailed as e:
            if e.code == "STEP":  # not installed: simctl exits non-zero
                return None
            raise
        lines = [x.strip() for x in out.decode("utf-8", "replace").splitlines() if x.strip().endswith(".app")]
        if not lines:
            return None
        folder = Path(lines[-1])
        try:
            with open(folder / "Info.plist", "rb") as f:
                if plistlib.load(f).get("CFBundleIdentifier") != bundle:
                    return None
        except (OSError, plistlib.InvalidFileException, ValueError):
            return None
        return folder

    def _sim_launch(self, ctx, udid, bundle):
        ctx.failure_code = "LAUNCH_FAILED"
        out = ctx.step("simctl-launch", ["xcrun", "simctl", "launch", "--terminate-running-process", udid, bundle],
                       ctx.dir, "simulator", capture=True)
        match = re.search(rf"^{re.escape(bundle)}: ([0-9]+)\s*$", out.decode("utf-8", "replace"), re.MULTILINE)
        if not match or int(match.group(1)) <= 0:
            raise StepFailed("LAUNCH_FAILED", "simctl did not report a process for the app.")
        ctx.set(process_id=int(match.group(1)))

    def _sim_screenshot(self, ctx, udid):
        handoff = self.config.handoff_dir / ctx.run["run_id"]
        self._make_handoff(handoff)
        target = handoff / SCREENSHOT_NAME
        ctx.failure_code = "SCREENSHOT_FAILED"
        ctx.step("simctl-screenshot", ["xcrun", "simctl", "io", udid, "screenshot", "--type=png", str(target)],
                 ctx.dir, "simulator")
        try:
            with open(target, "rb") as f:
                head = f.read(len(PNG_MAGIC))
        except OSError:
            raise StepFailed("SCREENSHOT_FAILED", "simctl exited 0 but wrote no screenshot.")
        if head != PNG_MAGIC:
            raise StepFailed("SCREENSHOT_FAILED", "The screenshot is not a PNG.")
        size, digest = tree_digest(target)
        ctx.set(artifact={"kind": "png", "path": str(target), "bytes": size, "sha256": digest})

    # bounded read of a screenshot

    def sim_screenshot_read(self, body):
        _fields(body, ["run_id"], ["offset", "max_bytes"])
        run_id = _str(body, "run_id", RUN_ID_RE, "run_id")
        offset = _int(body, "offset", 0, 1 << 40, 0)
        max_bytes = _int(body, "max_bytes", 1, MAX_FILE_PAGE, MAX_FILE_PAGE)
        run = self.load(run_id)["run"]
        artifact = run.get("artifact") or {}
        if run.get("kind") != "sim-screenshot" or run.get("state") != "succeeded" or artifact.get("kind") != "png":
            raise ApiError("BAD_ARGUMENT", "That run is not a finished screenshot.")
        # The path is rebuilt from the run ID, never taken from a request or the stored run.
        path = self.config.handoff_dir / run_id / SCREENSHOT_NAME
        try:
            total, digest = tree_digest(path)
            if digest != artifact.get("sha256"):
                raise ApiError("ARTIFACT_MISSING", "The screenshot changed since it was taken.")
            with open(path, "rb") as f:
                f.seek(min(offset, total))
                data = f.read(max_bytes)
        except OSError:
            raise ApiError("ARTIFACT_MISSING", "The screenshot is gone from the handoff folder.")
        start = min(offset, total)
        return envelope(True, None, run_id=run_id, offset=start, bytes=len(data), total_bytes=total,
                        eof=start + len(data) >= total, sha256=digest, media_type="image/png",
                        data_base64=base64.b64encode(data).decode("ascii"))
