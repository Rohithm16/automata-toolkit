from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict

try:  # pragma: no cover - import fallback for direct script execution
    from .automata import DFA, NFA, nfa_to_dfa, regex_to_nfa
    from .graph_gen import generate_dfa_dot, generate_nfa_dot
except ImportError:  # pragma: no cover - allows `python app.py` from the package folder
    from automata import DFA, NFA, nfa_to_dfa, regex_to_nfa
    from graph_gen import generate_dfa_dot, generate_nfa_dot

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
TEMPLATES_DIR = PROJECT_ROOT / 'templates'
STATIC_DIR = BASE_DIR / 'static'

logger = logging.getLogger(__name__)

app = FastAPI(title='Automata Toolkit', version='1.0.0')
app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


class AutomatonPayload(BaseModel):
    model_config = ConfigDict(extra='ignore')

    states: str | list[str] | None = None
    alphabet: str | list[str] | None = None
    transitions: str | list[str] | None = None
    start: str | None = None
    final: str | list[str] | None = None
    type: str | None = None
    regex: str | None = None


def render_page(request: Request, template_name: str, page_title: str) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context={'page_title': page_title},
    )


def error_response(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={'error': message})


def parse_csv(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(',') if item.strip()]


def parse_transitions(value: Any) -> list[str]:
    if not value:
        return []
    return [line.strip() for line in str(value).split('\n') if line.strip()]


def parse_transition_line(line: str) -> tuple[str, str, str]:
    if ':' not in line or '->' not in line:
        raise ValueError(f"Invalid transition format: '{line}'. Use state:symbol->target")
    src_part, rest = line.split(':', 1)
    symbol_part, dst_part = rest.split('->', 1)
    src = src_part.strip()
    symbol = symbol_part.strip()
    dst = dst_part.strip()
    if not src or not symbol or not dst:
        raise ValueError(f"Invalid transition format: '{line}'. Use state:symbol->target")
    return src, symbol, dst


def infer_automaton_parts(
    transitions: list[str],
    start: str,
    final: list[str],
) -> tuple[list[str], list[str], str | None]:
    states = set(final)
    alphabet = set()
    first_source = None

    for transition in transitions:
        src, symbol, dst = parse_transition_line(transition)
        if first_source is None:
            first_source = src
        states.update([src, dst])
        if symbol != 'ε':
            alphabet.add(symbol)

    resolved_start = start or first_source
    if resolved_start:
        states.add(resolved_start)

    return sorted(states), sorted(alphabet), resolved_start


def resolve_automaton_input(data: dict[str, Any]) -> dict[str, Any]:
    transitions = parse_transitions(data.get('transitions'))
    final = parse_csv(data.get('final'))
    start = (data.get('start') or '').strip()
    explicit_states = parse_csv(data.get('states'))
    explicit_alphabet = parse_csv(data.get('alphabet'))

    inferred_states, inferred_alphabet, inferred_start = infer_automaton_parts(
        transitions,
        start,
        final
    )

    states = sorted(set(explicit_states)) if explicit_states else inferred_states
    alphabet = sorted(set(explicit_alphabet)) if explicit_alphabet else inferred_alphabet
    start_state = start or inferred_start

    if not states:
        raise ValueError('Could not infer states. Provide transitions or states.')
    if not start_state:
        raise ValueError('Could not infer start state. Provide transitions or start state.')
    if start_state not in states:
        states.append(start_state)

    return {
        'states': states,
        'alphabet': alphabet,
        'transitions': transitions,
        'start': start_state,
        'final': final
    }


def serialize_dfa(dfa: DFA) -> dict[str, Any]:
    transition_list = []
    for src in sorted(dfa.transitions):
        for sym in sorted(dfa.transitions[src]):
            transition_list.append(f"{src}:{sym}->{dfa.transitions[src][sym]}")
    return {
        'states': sorted(dfa.states),
        'alphabet': sorted(sym for sym in dfa.alphabet if sym != 'ε'),
        'transitions': transition_list,
        'start': dfa.start_state,
        'final': sorted(dfa.final_states)
    }


def serialize_nfa(nfa: NFA) -> dict[str, Any]:
    transition_list = []
    for src in sorted(nfa.transitions):
        for sym in sorted(nfa.transitions[src]):
            for dst in sorted(nfa.transitions[src][sym]):
                transition_list.append(f"{src}:{sym}->{dst}")
    return {
        'states': sorted(nfa.states),
        'alphabet': sorted(sym for sym in nfa.alphabet if sym != 'ε'),
        'transitions': transition_list,
        'start': nfa.start_state,
        'final': sorted(nfa.final_states)
    }


@app.get('/', response_class=HTMLResponse, name='index')
def index(request: Request) -> HTMLResponse:
    return render_page(request, 'index.html', 'Automata Toolkit')


@app.get('/simulate-tool', response_class=HTMLResponse, name='simulate_tool')
def simulate_tool(request: Request) -> HTMLResponse:
    return render_page(request, 'simulate.html', 'DFA Tool - Automata Toolkit')


@app.get('/convert-tool', response_class=HTMLResponse, name='convert_tool')
def convert_tool(request: Request) -> HTMLResponse:
    return render_page(request, 'convert.html', 'NFA Tool - Automata Toolkit')


@app.get('/regex-tool', response_class=HTMLResponse, name='regex_tool')
def regex_tool(request: Request) -> HTMLResponse:
    return render_page(request, 'regex.html', 'Regex - Automata Toolkit')


@app.post('/convert')
def convert(payload: AutomatonPayload) -> JSONResponse:
    try:
        resolved = resolve_automaton_input(payload.model_dump())
        nfa = NFA(
            resolved['states'],
            resolved['alphabet'],
            resolved['transitions'],
            resolved['start'],
            resolved['final']
        )
        dfa, state_map = nfa_to_dfa(nfa)
        mapping = {name: ','.join(sorted(nfa_set)) for nfa_set, name in state_map.items()}
        return JSONResponse({
            'dfa_states': sorted(dfa.states),
            'dfa_alphabet': sorted(sym for sym in dfa.alphabet if sym != 'ε'),
            'dfa_transitions': [
                f"{src}:{sym}->{dst}"
                for src, trans in sorted(dfa.transitions.items())
                for sym, dst in sorted(trans.items())
            ],
            'dfa_start': dfa.start_state,
            'dfa_final': sorted(dfa.final_states),
            'mapping': mapping
        })
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception('Unexpected error while converting NFA to DFA')
        return error_response(str(exc), status_code=500)


@app.post('/regex_convert')
def regex_convert(payload: AutomatonPayload) -> JSONResponse:
    regex = (payload.regex or '').strip()
    if not regex:
        return error_response('Regex is required')

    alphabet_text = (payload.alphabet or '').strip() if isinstance(payload.alphabet, str) else ''
    alphabet = parse_csv(alphabet_text) if alphabet_text else None

    try:
        nfa = regex_to_nfa(regex, alphabet)
        dfa, state_map = nfa_to_dfa(nfa)
        subset_map = {name: ','.join(sorted(nfa_set)) for nfa_set, name in state_map.items()}
        return JSONResponse({
            'regex': regex,
            'nfa': serialize_nfa(nfa),
            'dfa': serialize_dfa(dfa),
            'subset_map': subset_map
        })
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception('Unexpected error while converting regex')
        return error_response(str(exc), status_code=500)


@app.post('/graph')
def graph(payload: AutomatonPayload) -> JSONResponse:
    try:
        automaton_type = (payload.type or 'dfa').lower()
        resolved = resolve_automaton_input(payload.model_dump())

        if automaton_type == 'dfa':
            automaton = DFA(
                resolved['states'],
                resolved['alphabet'],
                resolved['transitions'],
                resolved['start'],
                resolved['final']
            )
            dot = generate_dfa_dot(automaton)
        elif automaton_type == 'nfa':
            automaton = NFA(
                resolved['states'],
                resolved['alphabet'],
                resolved['transitions'],
                resolved['start'],
                resolved['final']
            )
            dot = generate_nfa_dot(automaton)
        else:
            return error_response("Type must be 'dfa' or 'nfa'")

        return JSONResponse({'dot': dot})
    except ValueError as exc:
        return error_response(str(exc))
    except Exception as exc:
        logger.exception('Unexpected error while generating graph')
        return error_response(str(exc), status_code=500)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='127.0.0.1', port=8000)