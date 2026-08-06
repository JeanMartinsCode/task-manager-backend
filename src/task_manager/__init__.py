"""Task Manager - Task Management System with Automatic Priority Escalation."""

from dotenv import find_dotenv, load_dotenv

# Load .env before anything else in the package runs. Several modules resolve
# their configuration at *import* time -- database.DATABASE_URL,
# rate_limit.RATE_LIMIT_WRITE, body_limit.MAX_BODY_BYTES -- and
# security.require_api_key reads API_KEY per request. Doing this in the
# package __init__ is the only placement that holds for every entry point,
# since uvicorn, alembic/env.py and the test suite all reach the config by
# importing some task_manager submodule, which runs this first.
#
# `usecwd=True` resolves .env relative to the working directory the process
# was started from (walking upwards), which is what "cd into the project,
# cp .env.example .env, run it" implies -- and unlike the default lookup, it
# also works when the package is installed non-editable.
#
# load_dotenv does not override variables already present in the real
# environment, so CI and production deployments that inject configuration
# directly stay authoritative over any stray local .env.
load_dotenv(find_dotenv(usecwd=True))

__version__ = "0.1.0"
