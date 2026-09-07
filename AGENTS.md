# Agent Harness Lab — Project Instructions

## Purpose

This repository is a didactic laboratory, not a production agent framework.

## Core rule

Do not add a harness primitive before a scenario demonstrates the concrete failure that motivates it.

## Engineering bias

Prefer the smallest implementation that exposes the concept clearly.

Avoid:
- premature abstractions;
- framework dependencies;
- production-hardening unless the current lesson requires it;
- feature parity with frontier harnesses.

## Documentation rule

For each stage, record:
1. the attempted task;
2. the observed failure;
3. why the current harness could not overcome it;
4. the next primitive introduced;
5. what changed after introducing it.
