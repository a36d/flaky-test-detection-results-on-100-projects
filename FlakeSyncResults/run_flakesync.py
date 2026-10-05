#!/usr/bin/env python3

import csv
import shutil
import subprocess
import time
from pathlib import Path

RESEARCH = Path.home() / "research"
PROJECTS = RESEARCH / "projects"
RESULTS = RESEARCH / "flaky-test-detection-results" / "FlakeSyncResults"
MANIFEST = RESULTS / "flakesync_manifest.csv"
OUTPUT_CSV = RESULTS / "flakesync_results.csv"
LOGS = RESULTS / "logs"
ARTIFACTS = RESULTS / "artifacts"

PLUGIN = "edu.utexas.ece:flakesync-maven-plugin:1.0-SNAPSHOT"

PHASES = [
    "concurrentfind",
    "delaylocs",
    "deltadebug",
    "critsearch",
    "barrierpointsearch",
    "patch",
]

# Maximum time allowed for each individual Maven/FlakeSync phase.
PHASE_TIMEOUT = 300

LOGS.mkdir(parents=True, exist_ok=True)
ARTIFACTS.mkdir(parents=True, exist_ok=True)

def run_command(command, cwd, log_file, timeout=PHASE_TIMEOUT):
    start = time.time()

    try:
        with open(log_file, "w", encoding="utf-8") as log:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=timeout,
            )

        return {
            "status": "SUCCESS" if result.returncode == 0 else "FAILED",
            "returncode": result.returncode,
            "seconds": round(time.time() - start, 2),
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "TIMEOUT",
            "returncode": "",
            "seconds": round(time.time() - start, 2),
        }

    except Exception as exc:
        with open(log_file, "a", encoding="utf-8") as log:
            log.write(f"\nRunner exception: {type(exc).__name__}: {exc}\n")

        return {
            "status": "RUNNER_ERROR",
            "returncode": "",
            "seconds": round(time.time() - start, 2),
        }

def safe_name(value):
    """Convert a test/project name into a filesystem-safe name."""
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return "".join(c if c in allowed else "_" for c in value)

def load_completed_tests():
    completed = set()

    if not OUTPUT_CSV.exists():
        return completed

    with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            key = (
                row["project_url"],
                row["sha"],
                row["flakesync_test"],
            )
            completed.add(key)

    return completed

RESULT_FIELDS = [
    "project_name",
    "project_url",
    "sha",
    "module",
    "detector",
    "flaky_test",
    "flakesync_test",
    "baseline_status",
    "concurrentfind_status",
    "delaylocs_status",
    "deltadebug_status",
    "critsearch_status",
    "barrierpointsearch_status",
    "patch_status",
    "final_status",
    "total_seconds",
    "artifact_dir",
]


def save_result(row):
    write_header = not OUTPUT_CSV.exists()

    with open(OUTPUT_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESULT_FIELDS)

        if write_header:
            writer.writeheader()

        writer.writerow(row)

def clean_flakesync_artifacts(project_dir, module):
    module_dir = project_dir if module == "." else project_dir / module
    flakesync_dir = module_dir / ".flakesync"

    if flakesync_dir.exists():
        shutil.rmtree(flakesync_dir)

    return module_dir

def save_artifacts(module_dir, project_name, flakesync_test):
    source = module_dir / ".flakesync"
    destination = ARTIFACTS / safe_name(project_name) / safe_name(flakesync_test)

    if destination.exists():
        shutil.rmtree(destination)

    if source.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, destination)
        return str(destination)

    return ""

def run_baseline(project_dir, module, test_name, log_file):
    command = ["mvn"]

    if module != ".":
        command += ["-pl", module, "-am"]

    command += [
        f"-Dtest={test_name}",
        "-DfailIfNoTests=false",
        "test",
    ]

    return run_command(
        command,
        cwd=project_dir,
        log_file=log_file,
    )

def run_flakesync_phase(project_dir, module, test_name, phase, log_file):
    command = ["mvn"]

    if module != ".":
        command += ["-pl", module, "-am"]

    command += [
        f"{PLUGIN}:{phase}",
        f"-Dflakesync.testName={test_name}",
    ]

    return run_command(
        command,
        cwd=project_dir,
        log_file=log_file,
    )

def process_test(item):
    project_name = item["project_name"]
    project_dir = PROJECTS / project_name
    module = item["module"]
    test_name = item["flakesync_test"]

    test_log_dir = (
        LOGS
        / safe_name(project_name)
        / safe_name(item["sha"])
        / safe_name(test_name)
    )
    test_log_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "project_name": project_name,
        "project_url": item["project_url"],
        "sha": item["sha"],
        "module": module,
        "detector": item["detector"],
        "flaky_test": item["flaky_test"],
        "flakesync_test": test_name,
        "baseline_status": "",
        "concurrentfind_status": "",
        "delaylocs_status": "",
        "deltadebug_status": "",
        "critsearch_status": "",
        "barrierpointsearch_status": "",
        "patch_status": "",
        "final_status": "",
        "total_seconds": "",
        "artifact_dir": "",
    }

    start = time.time()
    module_dir = clean_flakesync_artifacts(project_dir, module)

    baseline = run_baseline(
        project_dir,
        module,
        test_name,
        test_log_dir / "baseline.log",
    )

    result["baseline_status"] = baseline["status"]

    if baseline["status"] != "SUCCESS":
        result["final_status"] = "BASELINE_" + baseline["status"]
        result["total_seconds"] = round(time.time() - start, 2)
        result["artifact_dir"] = save_artifacts(
            module_dir, project_name, test_name
        )
        return result


    for phase in PHASES:
        phase_result = run_flakesync_phase(
            project_dir,
            module,
            test_name,
            phase,
            test_log_dir / f"{phase}.log",
        )

        phase_log = test_log_dir / f"{phase}.log"

        result[f"{phase}_status"] = phase_result["status"]

        if phase_result["status"] != "SUCCESS":
            result["final_status"] = (
                f"{phase.upper()}_{phase_result['status']}"
            )
            result["total_seconds"] = round(time.time() - start, 2)
            result["artifact_dir"] = save_artifacts(
                module_dir, project_name, test_name
            )
            return result

    result["final_status"] = "PIPELINE_COMPLETED"
    result["total_seconds"] = round(time.time() - start, 2)
    result["artifact_dir"] = save_artifacts(
        module_dir, project_name, test_name
    )

    return result

def instrumented_test_failed(log_file):
    try:
        text = Path(log_file).read_text(
            encoding="utf-8",
            errors="replace",
        )
        return "Surefire failed when running tests" in text
    except OSError:
        return False

def main():
    with open(MANIFEST, newline="", encoding="utf-8") as f:
        tests = list(csv.DictReader(f))

    completed = load_completed_tests()

    print(f"Manifest tests: {len(tests)}")
    print(f"Already completed: {len(completed)}")

    remaining = [
        item for item in tests
        if (
            item["project_url"],
            item["sha"],
            item["flakesync_test"],
        ) not in completed
    ]

    if "--single" in __import__("sys").argv:
        remaining = [x for x in remaining if x["project_name"] == "jnr-posix" and x["flakesync_test"] == "jnr.posix.FileTest#closeTest"][:1]

    print(f"Remaining: {len(remaining)}")

    for index, item in enumerate(remaining, 1):
        print(
            f"[{index}/{len(remaining)}] "
            f"{item['project_name']} :: {item['flakesync_test']}",
            flush=True,
        )

        result = process_test(item)
        save_result(result)

        print(
            f"  -> {result['final_status']} "
            f"({result['total_seconds']}s)",
            flush=True,
        )


if __name__ == "__main__":
    main()
