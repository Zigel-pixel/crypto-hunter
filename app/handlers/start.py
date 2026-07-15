import logging
import time
from collections.abc import Awaitable
from typing import TypeVar

import aiosqlite
from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import ReplyKeyboardMarkup

from app.handlers.common import user_main_keyboard
from app.keyboards.main import (
    build_main_keyboard,
    build_stopped_keyboard,
    control_labels,
)
from app.services.live_market_service import live_chart_manager
from app.services.settings_service import get_setting, resolve_user_language
from app.services.user_service import activate_user, stop_user
from app.utils.i18n import DEFAULT_LANGUAGE, normalize_language, translate

router = Router()
logger = logging.getLogger(__name__)
START_DB_TIMEOUT_SECONDS = 0.5
_T = TypeVar("_T")


def _log_start_timing(operation: str, started_at: float, outcome: str) -> None:
    duration_ms = max(0.0, (time.monotonic() - started_at) * 1000)
    logger.info(
        "start_path operation=%s duration_ms=%.3f outcome=%s",
        operation,
        duration_ms,
        outcome,
    )


async def _timed_await(operation: str, awaitable: Awaitable[_T]) -> _T:
    started_at = time.monotonic()
    try:
        result = await awaitable
    except Exception:
        _log_start_timing(operation, started_at, "error")
        raise
    _log_start_timing(operation, started_at, "ok")
    return result


async def _answer_start(
    message: types.Message,
    text: str,
    reply_markup: ReplyKeyboardMarkup | None = None,
) -> None:
    started_at = time.monotonic()
    _log_start_timing("first_answer_send_start", started_at, "started")
    try:
        if reply_markup is None:
            await message.answer(text)
        else:
            await message.answer(text, reply_markup=reply_markup)
    except Exception:
        _log_start_timing("first_answer_send", started_at, "error")
        raise
    _log_start_timing("first_answer_send", started_at, "ok")


@router.message(CommandStart())
@router.message(lambda message: message.text in control_labels("controls.start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    handler_started_at = time.monotonic()
    handler_outcome = "ok"
    _log_start_timing("handler_entry", handler_started_at, "started")
    _log_start_timing("user_session_read", handler_started_at, "bypassed")
    try:
        language_started_at = time.monotonic()
        try:
            language = await resolve_user_language(
                message.from_user.id,
                timeout_seconds=START_DB_TIMEOUT_SECONDS,
            )
        except aiosqlite.Error:
            language = DEFAULT_LANGUAGE
            handler_outcome = "language_fallback"
            logger.warning("Start language resolution failed; using the safe default")
            _log_start_timing(
                "settings_database_read",
                language_started_at,
                "database_error",
            )
            _log_start_timing(
                "language_resolution",
                language_started_at,
                "database_error_fallback",
            )
        else:
            _log_start_timing("settings_database_read", language_started_at, "ok")
            _log_start_timing("language_resolution", language_started_at, "ok")

        persistence_started_at = time.monotonic()
        _log_start_timing(
            "normalization_persistence",
            persistence_started_at,
            "not_required",
        )
        await _timed_await("fsm_clear", state.clear())
        await _timed_await("live_stop", live_chart_manager.stop(message.chat.id))

        activation_started_at = time.monotonic()
        try:
            await activate_user(
                message.from_user.id,
                timeout_seconds=START_DB_TIMEOUT_SECONDS,
            )
        except aiosqlite.Error:
            handler_outcome = "session_unavailable"
            logger.warning("Could not activate user session due to a database error")
            _log_start_timing(
                "user_activation",
                activation_started_at,
                "database_error",
            )
            await _answer_start(message, translate("session.unavailable", language))
            return
        _log_start_timing("user_activation", activation_started_at, "ok")

        keyboard_started_at = time.monotonic()
        keyboard = build_main_keyboard(language)
        _log_start_timing("keyboard_build", keyboard_started_at, "ok")
        await _answer_start(
            message,
            translate("session.started", language),
            keyboard,
        )
    except Exception:
        handler_outcome = "error"
        raise
    finally:
        _log_start_timing("handler_total", handler_started_at, handler_outcome)


@router.message(Command("restart"))
@router.message(lambda message: message.text in control_labels("controls.restart"))
async def restart_session(message: types.Message, state: FSMContext) -> None:
    language = normalize_language(await get_setting(message.from_user.id, "language"))
    await state.clear()
    await live_chart_manager.stop(message.chat.id)
    try:
        await activate_user(message.from_user.id)
    except aiosqlite.Error as exc:
        logger.exception("Could not restart user session: %s", exc)
        await message.answer(translate("session.unavailable", language))
        return
    await message.answer(
        translate("session.restarted", language),
        reply_markup=await user_main_keyboard(message.from_user.id),
    )


@router.message(Command("stop"))
@router.message(lambda message: message.text in control_labels("controls.stop"))
async def stop_session(message: types.Message, state: FSMContext) -> None:
    language = normalize_language(await get_setting(message.from_user.id, "language"))
    await state.clear()
    await live_chart_manager.stop(message.chat.id)
    try:
        await stop_user(message.from_user.id)
    except aiosqlite.Error as exc:
        logger.exception("Could not stop user session: %s", exc)
        await message.answer(translate("session.unavailable", language))
        return
    await message.answer(
        translate("session.stopped", language),
        reply_markup=build_stopped_keyboard(language),
    )
