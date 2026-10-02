# Flaky Test Detection Results

This repository contains results from running **iDFlakies** and **NonDex** on 100 successfully analyzed Java/Maven projects selected from the IDoFT dataset.

## Results

Across the 100 projects:

- iDFlakies detected **47** unique flaky tests.
- NonDex detected **1,008** unique flaky tests.
- **0** exact tests were detected by both tools.
- **1,055** unique flaky tests were detected across both tools.

## Comparison with IDoFT

The detected tests were compared against the existing IDoFT dataset using the repository URL and fully-qualified test name.

- Of the 47 iDFlakies detections, **14** were already present in IDoFT and **33** were newly detected.
- Of the 1,008 NonDex detections, **0** were already present in IDoFT and **1,008** were newly detected.
- In total, **1,041 unique flaky tests** were not already present in IDoFT.

## Files

The `100ProjectsResults` directory contains:

- `daniel_watson_idflakies.csv` — iDFlakies results for the 100 projects.
- `daniel_watson_nondex.csv` — NonDex results for the 100 projects.
- `new_flaky_tests.csv` — the 1,041 detected tests not already present in IDoFT.
- `already_in_idoft.csv` — the 14 detected tests that matched existing IDoFT entries.
- `report.txt` — summary of the experiment and final counts.

## Tools

- **iDFlakies** — used to detect order-dependent flaky tests through randomized test execution.
- **NonDex** — used to detect tests that depend on unspecified or nondeterministic Java behavior.
- **IDoFT** — used as the existing flaky-test dataset for comparison.

## Comparison Method

A detected test was considered already known if its **repository URL** and **fully-qualified test name** matched an entry in the current IDoFT dataset. The commit SHA was not required to match, since the same flaky test may have been recorded by IDoFT at a different revision.
