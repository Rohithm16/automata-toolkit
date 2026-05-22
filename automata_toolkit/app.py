from flask import Flask, render_template, request, jsonify
from pathlib import Path
from automata import NFA, DFA, nfa_to_dfa, regex_to_nfa
from graph_gen import generate_nfa_dot, generate_dfa_dot

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

app = Flask(
    __name__,
    template_folder=str(PROJECT_ROOT / 'templates'),
    static_folder=str(BASE_DIR / 'static')
)

def parse_csv(value):
    if not value:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(',') if item.strip()]


def parse_transitions(value):
    if not value:
        return []
    return [line.strip() for line in str(value).split('\n') if line.strip()]


def parse_transition_line(line):
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


def infer_automaton_parts(transitions, start, final):
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


def resolve_automaton_input(data):
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


def serialize_dfa(dfa):
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


def serialize_nfa(nfa):
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


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/simulate-tool')
def simulate_tool():
    return render_template('simulate.html')


@app.route('/convert-tool')
def convert_tool():
    return render_template('convert.html')


@app.route('/regex-tool')
def regex_tool():
    return render_template('regex.html')


@app.route('/convert', methods=['POST'])
def convert():
    data = request.json or {}
    try:
        resolved = resolve_automaton_input(data)
        nfa = NFA(
            resolved['states'],
            resolved['alphabet'],
            resolved['transitions'],
            resolved['start'],
            resolved['final']
        )
        dfa, state_map = nfa_to_dfa(nfa)
        mapping = {name: ','.join(sorted(nfa_set)) for nfa_set, name in state_map.items()}
        return jsonify({
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
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/regex_convert', methods=['POST'])
def regex_convert():
    data = request.json or {}
    regex = (data.get('regex') or '').strip()
    if not regex:
        return jsonify({'error': 'Regex is required'}), 400

    alphabet_text = (data.get('alphabet') or '').strip()
    alphabet = parse_csv(alphabet_text) if alphabet_text else None

    try:
        nfa = regex_to_nfa(regex, alphabet)
        dfa, state_map = nfa_to_dfa(nfa)
        subset_map = {name: ','.join(sorted(nfa_set)) for nfa_set, name in state_map.items()}
        return jsonify({
            'regex': regex,
            'nfa': serialize_nfa(nfa),
            'dfa': serialize_dfa(dfa),
            'subset_map': subset_map
        })
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/graph', methods=['POST'])
def graph():
    data = request.json or {}
    try:
        automaton_type = (data.get('type') or 'dfa').lower()
        resolved = resolve_automaton_input(data)

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
            return jsonify({'error': "Type must be 'dfa' or 'nfa'"}), 400

        return jsonify({'dot': dot})
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


if __name__ == '__main__':
    app.run(debug=True)