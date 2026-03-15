# Testing

## Purpose

This document defines how tests should be written and organized in this repository.

## Test Types

### Unit Tests

Unit tests verify deterministic logic in isolation.

Target areas:

- strategy rules
- risk rules
- portfolio calculations
- pure application logic that does not require external IO

Rules:

- keep unit tests fast
- avoid network and database access
- prefer explicit inputs and outputs
- do not depend on wall-clock timing when it can be avoided

### Integration Tests

Integration tests verify boundaries between modules and adapters.

Target areas:

- API routes
- database repositories
- application service orchestration
- paper execution flow

Rules:

- use local test doubles or isolated local resources
- do not hit real exchanges or external services
- keep setup minimal and deterministic

## Required Coverage By Change Type

- strategy changes: unit tests for entry and exit behavior
- risk changes: unit tests for approval and rejection behavior
- API changes: route tests and response validation
- repository changes: integration tests for persistence behavior
- execution changes: tests covering success and failure paths
- schema or database scaffolding changes: tests for table creation or model registration where practical

For risk policy changes, cover:

- approval path
- each rejection rule
- deterministic quantity calculation

For paper execution changes, cover:

- order creation
- trade creation
- position updates
- realized PnL behavior
- rejection or invalid-state paths

## Test Boundaries

- `domain` should be tested primarily with unit tests
- `application` should be tested with unit tests or focused integration tests, depending on IO involvement
- `infrastructure` should be tested with integration tests and fakes where practical
- `interfaces` should be tested through API-level tests, not by testing framework internals

## External Dependencies

- no real network calls in automated tests
- no real exchange credentials in tests
- no live trading in any automated test path

## Test Organization

- keep tests under `tests/`
- name files `test_<behavior>.py`
- group tests by domain behavior or interface boundary, not by implementation detail alone
- prefer file-backed SQLite or explicit test resources over hidden shared global state for persistence tests

## Tooling

- run tests with `make test`
- `pre-push` runs `pytest`
- format and lint should pass before tests are considered complete

## Practical Rule

When in doubt, test the business rule directly before testing the framework around it.
