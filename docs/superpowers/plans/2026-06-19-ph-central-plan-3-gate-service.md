# PH Central Plan 3: GateService + Gate Tools

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Central validates and enforces phase gates, records decisions in a custody chain, and stores results submitted by local skills.

**Architecture:** GateRecord model for custody chain, SubmittedResult model for local skill outputs, GateService composing PhaseEngine + GitRepoReader for gate evaluation, three new MCP tools (ph_request_gate, ph_submit_results, ph_get_history).

**Tech Stack:** Python 3.11+, SQLAlchemy, pytest

## Global Constraints

- Working branch: `feature/ph-central-registration`
- MCP tools create their own `SessionLocal()`
- Tests use SQLite in-memory with fastmcp mock from conftest
- All models use UUID primary keys and timezone-aware datetimes

---

### Task 1: GateRecord and SubmittedResult Models + Migration

### Task 2: GateService — Gate Evaluation and Recording

### Task 3: ph_request_gate, ph_submit_results, ph_get_history MCP Tools
